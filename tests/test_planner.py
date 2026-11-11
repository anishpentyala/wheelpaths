import json
import stat
import zipfile
from pathlib import Path
import pytest
from wheelpaths import audit, InvalidPlan
from wheelpaths.cli import main

SCHEME = {'purelib': '/env/lib', 'platlib': '/env/lib',
          'scripts': '/env/bin', 'data': '/env'}


def wheel(tmp, name='alpha', files=None, pure='true', version='1.0', extras=None):
    path = tmp / f'{name}-1.0-py3-none-any.whl'
    entries = [(f'{name}-1.0.dist-info/WHEEL',
                f'Wheel-Version: {version}\nRoot-Is-Purelib: {pure}\n'),
               (f'{name}-1.0.dist-info/METADATA', f'Name: {name}\nVersion: 1.0\n')]
    entries += list((files or {}).items()) + (extras or [])
    with zipfile.ZipFile(path, 'w') as z:
        for key, value in entries:
            z.writestr(key, value)
    return path


def collisions(a, b):
    return [x for x in audit([a, b], SCHEME)['conflicts']
            if x['target'].endswith('/shared.py')]


@pytest.mark.parametrize('same', [True, False])
def test_same_destination_even_equal_content(tmp_path, same):
    a = wheel(tmp_path, files={'shared.py': 'one'})
    b = wheel(tmp_path, 'beta', {'shared.py': 'one' if same else 'two'})
    assert collisions(a, b)


@pytest.mark.parametrize('key', ['purelib', 'platlib', 'data'])
def test_spread_and_root_collision(tmp_path, key):
    a = wheel(tmp_path, files={'shared.py': 'one'})
    rel = 'lib/shared.py' if key == 'data' else 'shared.py'
    b = wheel(tmp_path, 'beta', {f'beta-1.0.data/{key}/{rel}': 'two'})
    assert collisions(a, b)


def test_distinct_scheme_does_not_conflate(tmp_path):
    a = wheel(tmp_path, files={'shared.py': 'one'})
    b = wheel(tmp_path, 'beta', {'shared.py': 'two'}, pure='false')
    assert not audit([a, b], dict(SCHEME, platlib='/env/lib64'))['conflicts']


@pytest.mark.parametrize('first,second', [('pkg', 'pkg/a.py'), ('pkg/', 'pkg')])
def test_file_directory_conflict(tmp_path, first, second):
    a = wheel(tmp_path, files={first: ''})
    b = wheel(tmp_path, 'beta', {second: ''})
    assert audit([a, b], SCHEME)['conflicts']


def test_namespace_and_shared_explicit_directories_allowed(tmp_path):
    a = wheel(tmp_path, files={'ns/': '', 'ns/a.py': ''})
    b = wheel(tmp_path, 'beta', {'ns/': '', 'ns/b.py': ''})
    assert not audit([a, b], SCHEME)['conflicts']


@pytest.mark.parametrize('other', ['console_scripts', 'gui_scripts'])
def test_generated_script_and_data_script(tmp_path, other):
    a = wheel(tmp_path, files={'alpha-1.0.dist-info/entry_points.txt':
                             f'[{other}]\nRunner = alpha:main\n'})
    b = wheel(tmp_path, 'beta', {'beta-1.0.data/scripts/Runner': 'anything'})
    report = audit([a, b], SCHEME)
    assert any(x['target'] == '/env/bin/Runner' for x in report['conflicts'])


def test_within_wheel_projection_collision(tmp_path):
    a = wheel(tmp_path, files={'shared.py': '',
                             'alpha-1.0.data/purelib/shared.py': ''})
    assert audit([a], SCHEME)['conflicts']


@pytest.mark.parametrize('name', ['../x', '/abs', 'a/../b', 'a//b', 'a/./b',
                                  'a\\b', 'C:x', 'a\tb'])
def test_bad_members_refused(tmp_path, name):
    with pytest.raises(InvalidPlan):
        audit([wheel(tmp_path, files={name: ''})], SCHEME)


@pytest.mark.parametrize('value', ['1.1', '2.0', '', 'unknown'])
def test_unknown_wheel_version_refused(tmp_path, value):
    with pytest.raises(InvalidPlan):
        audit([wheel(tmp_path, version=value)], SCHEME)


@pytest.mark.parametrize('value', ['True', 'yes', '', 'false\nRoot-Is-Purelib: true'])
def test_invalid_purelib_refused(tmp_path, value):
    with pytest.raises(InvalidPlan):
        audit([wheel(tmp_path, pure=value)], SCHEME)


@pytest.mark.parametrize('files', [
    {'alien-1.0.dist-info/METADATA': ''},
    {'alien-1.0.data/purelib/x': ''},
    {'alpha-1.0.data/headers/x': ''},
    {'alpha-1.0.data/mystery/x': ''},
    {'alpha-1.0.data/purelib': ''},
])
def test_unknown_layout_refused(tmp_path, files):
    with pytest.raises(InvalidPlan):
        audit([wheel(tmp_path, files=files)], SCHEME)


@pytest.mark.parametrize('name,body', [
    ('alpha-1.0.dist-info/WHEEL', 'Wheel-Version: 1.0\nRoot-Is-Purelib: true'),
    ('x.py', 'x'),
])
def test_duplicate_members_refused(tmp_path, name, body):
    a = wheel(tmp_path, files={'x.py': 'x'}, extras=[(name, body)])
    with pytest.raises(InvalidPlan, match='duplicate'):
        audit([a], SCHEME)


@pytest.mark.parametrize('mode', [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR])
def test_special_members_refused(tmp_path, mode):
    a = wheel(tmp_path)
    info = zipfile.ZipInfo('odd')
    info.external_attr = (mode | 0o644) << 16
    with zipfile.ZipFile(a, 'a') as z:
        z.writestr(info, 'value')
    with pytest.raises(InvalidPlan, match='non-regular'):
        audit([a], SCHEME)


@pytest.mark.parametrize('scheme', [None, {}, dict(SCHEME, headers='/env/include'),
                                    dict(SCHEME, purelib='relative'),
                                    dict(SCHEME, data='/a/../b'),
                                    dict(SCHEME, data='/a//b')])
def test_bad_scheme_refused(tmp_path, scheme):
    with pytest.raises(InvalidPlan):
        audit([wheel(tmp_path)], scheme)


def test_cli_exit_codes_and_invalid_never_clear(tmp_path, capsys):
    scheme = tmp_path / 'scheme.json'
    scheme.write_text(json.dumps(SCHEME))
    a = wheel(tmp_path, files={'same.py': ''})
    b = wheel(tmp_path, 'beta', {'same.py': ''})
    for args, code, status in [([str(a)], 0, 'NO_COLLISIONS_IN_MODEL'),
                               ([str(a), str(b)], 1, 'COLLISIONS'),
                               (['missing.whl'], 2, 'INVALID')]:
        assert main(['--scheme', str(scheme)] + args) == code
        assert json.loads(capsys.readouterr().out)['status'] == status
    scheme.write_text('{"data":"/a","data":"/b"}')
    assert main(['--scheme', str(scheme), str(a)]) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'INVALID'


def test_report_binds_exact_archive_and_does_not_import(tmp_path):
    import hashlib
    a = wheel(tmp_path, files={'explode.py': 'raise RuntimeError("not imported")'})
    report = audit([a], SCHEME)
    assert report['wheels'][0]['sha256'] == hashlib.sha256(a.read_bytes()).hexdigest()
    assert 'RECORD integrity and wheel validity' in report['excluded']
    assert report == audit([a], SCHEME)


@pytest.mark.parametrize('member', ['alpha-1.0.dist-info/WHEEL',
                                    'alpha-1.0.dist-info/METADATA'])
def test_required_metadata_missing(tmp_path, member):
    a = wheel(tmp_path)
    with zipfile.ZipFile(a) as z:
        files = [(i.filename, z.read(i)) for i in z.infolist() if i.filename != member]
    with zipfile.ZipFile(a, 'w') as z:
        for key, value in files:
            z.writestr(key, value)
    with pytest.raises(InvalidPlan, match='missing'):
        audit([a], SCHEME)


@pytest.mark.parametrize('body', ['Name: beta\nVersion: 1.0\n',
                                  'Name: alpha\nVersion: 2.0\n',
                                  'Name: alpha\nName: alpha\nVersion: 1.0\n'])
def test_metadata_identity_mismatch(tmp_path, body):
    a = wheel(tmp_path)
    with zipfile.ZipFile(a) as z:
        files = [(i.filename, z.read(i)) for i in z.infolist()
                 if not i.filename.endswith('/METADATA')]
    with zipfile.ZipFile(a, 'w') as z:
        for key, value in files:
            z.writestr(key, value)
        z.writestr('alpha-1.0.dist-info/METADATA', body)
    with pytest.raises(InvalidPlan):
        audit([a], SCHEME)


@pytest.mark.parametrize('contents', ['[console_scripts]\nrun = alpha:main\nrun = beta:main\n',
                                      '[console_scripts]\na/b = alpha:main\n',
                                      '[DEFAULT]\nrun = alpha:main\n',
                                      '[console_scripts]\nrun = \n'])
def test_bad_entrypoints_refused(tmp_path, contents):
    a = wheel(tmp_path, files={'alpha-1.0.dist-info/entry_points.txt': contents})
    with pytest.raises(InvalidPlan):
        audit([a], SCHEME)


def test_gui_and_console_same_name_in_one_wheel(tmp_path):
    a = wheel(tmp_path, files={'alpha-1.0.dist-info/entry_points.txt':
              '[console_scripts]\nrun = alpha:main\n[gui_scripts]\nrun = alpha:main\n'})
    assert any(c['target'] == '/env/bin/run' for c in audit([a], SCHEME)['conflicts'])


def test_bad_zip_and_empty_set_invalid(tmp_path):
    a = tmp_path / 'alpha-1.0-py3-none-any.whl'
    a.write_text('not a zip')
    with pytest.raises(InvalidPlan):
        audit([a], SCHEME)
    with pytest.raises(InvalidPlan):
        audit([], SCHEME)


@pytest.mark.parametrize('name,mode', [('foo/', stat.S_IFREG), ('foo', stat.S_IFDIR)])
def test_directory_type_mismatch_invalid(tmp_path, name, mode):
    a = wheel(tmp_path)
    info = zipfile.ZipInfo(name)
    info.external_attr = (mode | 0o644) << 16
    with zipfile.ZipFile(a, 'a') as z:
        z.writestr(info, '')
    with pytest.raises(InvalidPlan):
        audit([a], SCHEME)


def test_metadata_and_member_limits_fail_closed(tmp_path, monkeypatch):
    import wheelpaths.planner as planner
    a = wheel(tmp_path)
    monkeypatch.setattr(planner, 'MAX_METADATA', 4)
    with pytest.raises(InvalidPlan, match='byte limit'):
        audit([a], SCHEME)
    monkeypatch.setattr(planner, 'MAX_MEMBERS', 1)
    with pytest.raises(InvalidPlan, match='member limit'):
        audit([a], SCHEME)


@pytest.mark.parametrize('value', [1, None, False, b'file.whl', {}, []])
def test_nonpath_api_inputs_invalid(value):
    with pytest.raises(InvalidPlan, match='wheel path'):
        audit([value], SCHEME)


def test_bytes_pathlike_api_input_invalid():
    class BytesPath:
        def __fspath__(self):
            return b'file.whl'
    with pytest.raises(InvalidPlan, match='wheel path'):
        audit([BytesPath()], SCHEME)


@pytest.mark.parametrize('member', ['WHEEL', 'METADATA', 'entry_points.txt'])
def test_corrupt_deflated_metadata_is_invalid_json(tmp_path, capsys, member):
    import struct
    a = tmp_path / 'alpha-1.0-py3-none-any.whl'
    contents = {
        'WHEEL': 'Wheel-Version: 1.0\nRoot-Is-Purelib: true\n',
        'METADATA': 'Name: alpha\nVersion: 1.0\n',
        'entry_points.txt': '[console_scripts]\nrun = alpha:main\n',
    }
    with zipfile.ZipFile(a, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, value in contents.items():
            z.writestr('alpha-1.0.dist-info/' + name, value)
    with zipfile.ZipFile(a) as z:
        info = z.getinfo('alpha-1.0.dist-info/' + member)
    raw = bytearray(a.read_bytes())
    namesize, extrasize = struct.unpack_from('<HH', raw, info.header_offset + 26)
    start = info.header_offset + 30 + namesize + extrasize
    raw[start:start + info.compress_size] = b'\xff' * info.compress_size
    a.write_bytes(raw)
    with pytest.raises(InvalidPlan):
        audit([a], SCHEME)
    scheme = tmp_path / 'scheme.json'
    scheme.write_text(json.dumps(SCHEME))
    assert main(['--scheme', str(scheme), str(a)]) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'INVALID'


@pytest.mark.parametrize('compression', [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA])
def test_unmodeled_metadata_compression_invalid(tmp_path, compression):
    a = tmp_path / 'alpha-1.0-py3-none-any.whl'
    with zipfile.ZipFile(a, 'w', compression=compression) as z:
        z.writestr('alpha-1.0.dist-info/WHEEL', 'Wheel-Version: 1.0\nRoot-Is-Purelib: true')
        z.writestr('alpha-1.0.dist-info/METADATA', 'Name: alpha\nVersion: 1.0')
    with pytest.raises(InvalidPlan, match='compression'):
        audit([a], SCHEME)
