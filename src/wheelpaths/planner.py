"""Explicit POSIX scheme projections, not an installer or wheel validator."""
import configparser
import hashlib
import io
import os
import re
import stat
import zipfile
import zlib
from collections import defaultdict
from email.parser import Parser
from pathlib import Path, PurePosixPath


class InvalidPlan(ValueError):
    """Input cannot be projected within the supported model."""


KEYS = {'purelib', 'platlib', 'scripts', 'data'}
MAX_METADATA = 1024 * 1024
MAX_MEMBERS = 100000


def relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or
            any(ord(c) < 32 or ord(c) == 127 for c in value) or
            any(p in ('', '.', '..') for p in value.split('/')) or
            value.startswith('/') or ':' in value):
        raise InvalidPlan('unsupported relative POSIX path: ' + repr(value))
    return value


def scheme_paths(scheme):
    if not isinstance(scheme, dict) or set(scheme) != KEYS:
        raise InvalidPlan('scheme must have exactly purelib, platlib, scripts, data')
    for value in scheme.values():
        if not isinstance(value, str) or not value.startswith('/'):
            raise InvalidPlan('scheme paths must be absolute POSIX paths')
        if value != '/':
            relative(value[1:])
    return dict(scheme)


def destination(base, name):
    return str(PurePosixPath(base) / relative(name))


def field(message, name):
    values = message.get_all(name, [])
    if len(values) != 1:
        raise InvalidPlan('metadata needs one ' + name)
    return values[0].strip()


def wheel_claims(path, scheme, index):
    if not isinstance(path, (str, os.PathLike)):
        raise InvalidPlan('wheel path must be text or path-like')
    try:
        path = Path(path)
    except TypeError as exc:
        raise InvalidPlan('wheel path must resolve to text') from exc
    # The filename supplies only the expected metadata directory, never code.
    parts = path.name[:-4].split('-') if path.name.endswith('.whl') else []
    if len(parts) not in (5, 6) or any(not p for p in parts):
        raise InvalidPlan('unsupported wheel filename: ' + path.name)
    prefix = parts[0] + '-' + parts[1]
    relative(prefix)
    dist = prefix + '.dist-info'
    data = prefix + '.data'
    with open(path, 'rb') as source:
        raw = source.read(256 * 1024 * 1024 + 1)
    if len(raw) > 256 * 1024 * 1024:
        raise InvalidPlan('wheel exceeds 256 MiB archive limit')
    owner = {'input': index, 'wheel': path.name,
             'sha256': hashlib.sha256(raw).hexdigest()}
    result = []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        if len(infos) > MAX_MEMBERS:
            raise InvalidPlan('wheel exceeds member limit')
        names = set()
        for info in infos:
            original = info.orig_filename
            name = original[:-1] if original.endswith('/') else original
            relative(name)
            if info.filename != original:
                raise InvalidPlan('ZIP member name was truncated')
            if original in names:
                raise InvalidPlan('duplicate ZIP member: ' + original)
            names.add(original)
            mode = info.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise InvalidPlan('non-regular ZIP member: ' + original)
            if ((info.is_dir() and kind == stat.S_IFREG) or
                    (not info.is_dir() and kind == stat.S_IFDIR)):
                raise InvalidPlan('ZIP directory spelling and type differ')
            if info.flag_bits & 1:
                raise InvalidPlan('encrypted ZIP member')
            top = name.split('/')[0]
            if top.endswith('.dist-info') and top != dist:
                raise InvalidPlan('unexpected metadata directory')
            if top.endswith('.data') and top != data:
                raise InvalidPlan('unexpected data directory')

        def text(member):
            try:
                info = z.getinfo(member)
            except KeyError as exc:
                raise InvalidPlan('missing ' + member) from exc
            if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise InvalidPlan('unsupported metadata compression')
            if info.file_size > MAX_METADATA:
                raise InvalidPlan('metadata exceeds byte limit')
            with z.open(info) as stream:
                raw = stream.read(MAX_METADATA + 1)
            if len(raw) > MAX_METADATA:
                raise InvalidPlan('metadata exceeds byte limit')
            return raw.decode('utf-8', errors='strict')

        wheel = Parser().parsestr(text(dist + '/WHEEL'))
        if field(wheel, 'Wheel-Version') != '1.0':
            raise InvalidPlan('only Wheel-Version 1.0 is modeled')
        pure = field(wheel, 'Root-Is-Purelib')
        if pure not in ('true', 'false'):
            raise InvalidPlan('invalid Root-Is-Purelib')
        root = 'purelib' if pure == 'true' else 'platlib'
        metadata = Parser().parsestr(text(dist + '/METADATA'))
        normalize = lambda s: re.sub(r'[-_.]+', '-', s).lower()
        if (normalize(field(metadata, 'Name')) != normalize(parts[0]) or
                field(metadata, 'Version').replace('-', '_') != parts[1]):
            raise InvalidPlan('filename and metadata identity differ')

        def claim(target, member, kind='file'):
            result.append(dict(owner, target=target, member=member, kind=kind))

        for info in infos:
            name = info.filename.rstrip('/')
            if name == data and not info.is_dir():
                raise InvalidPlan('data root is not a directory')
            if info.is_dir() and (name == data or
                    name in {data + '/' + key for key in KEYS}):
                continue
            if name.startswith(data + '/'):
                bits = name.split('/', 2)
                if len(bits) != 3 or bits[1] not in KEYS:
                    raise InvalidPlan('unsupported data scheme: ' + name)
                key, rel = bits[1:]
            else:
                key, rel = root, name
            claim(destination(scheme[key], rel), info.filename,
                  'directory' if info.is_dir() else 'file')
        ep = dist + '/entry_points.txt'
        if ep in names:
            config = configparser.ConfigParser(interpolation=None, strict=True,
                                                delimiters=('=',))
            config.optionxform = str
            config.read_string(text(ep))
            if config.defaults():
                raise InvalidPlan('entry point DEFAULT values are unsupported')
            for section in ('console_scripts', 'gui_scripts'):
                if not config.has_section(section):
                    continue
                for name, value in config.items(section):
                    relative(name)
                    if '/' in name or not value.strip():
                        raise InvalidPlan('unsupported script entry point')
                    claim(destination(scheme['scripts'], name), ep + ':' +
                          section + ':' + name, 'generated-script')
    return owner, result


def audit(wheels, scheme):
    """Plan one candidate wheel set. Input errors never return a clear plan."""
    scheme = scheme_paths(scheme)
    if not isinstance(wheels, (list, tuple)) or not wheels:
        raise InvalidPlan('at least one wheel is required')
    owners, claims = [], []
    try:
        for index, path in enumerate(wheels):
            owner, rows = wheel_claims(path, scheme, index)
            owners.append(owner)
            claims.extend(rows)
    except (OSError, zipfile.BadZipFile, UnicodeError,
            configparser.Error, RuntimeError, zlib.error, EOFError) as exc:
        raise InvalidPlan(str(exc)) from exc
    groups = defaultdict(list)
    for row in claims:
        groups[row['target']].append(row)
    conflicts = []
    for target in sorted(groups):
        rows = groups[target]
        files = [row for row in rows if row['kind'] != 'directory']
        if len(files) > 1 or (files and len(files) < len(rows)):
            conflicts.append({'type': 'same-target', 'target': target,
                              'claims': rows})
        # Every file also requires all ancestors to be directories. Shared
        # directories alone are valid (including PEP 420 namespace packages).
        for parent in PurePosixPath(target).parents:
            parent_files = [row for row in groups.get(str(parent), [])
                            if row['kind'] != 'directory']
            if parent_files:
                conflicts.append({'type': 'file-directory', 'target': str(parent),
                                  'claims': parent_files + rows})
    return {'schema': 1, 'status': 'COLLISIONS' if conflicts else 'NO_COLLISIONS_IN_MODEL',
            'scheme': scheme, 'wheels': owners, 'claims': claims,
            'conflicts': conflicts,
            'scope': 'POSIX exact lexical paths; candidate wheels only; no installation',
            'excluded': ['existing files', 'filesystem symlink/case/Unicode aliases',
                         'generated bytecode', 'Windows launchers', 'compatibility tags',
                         'dependency resolution', 'RECORD integrity and wheel validity',
                         'import namespace shadowing', 'execution safety']}
