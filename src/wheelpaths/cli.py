"""Machine-readable exit codes: 0 no modeled collision, 1 collisions, 2 invalid."""
import argparse
import json
import sys
from functools import partial
from .planner import audit, InvalidPlan, Limits, _read_regular

MAX_SCHEME_BYTES = 1024 * 1024


def _write_text(stream, text):
    if stream is None:
        raise OSError('output stream is unavailable')
    written = stream.write(text)
    if type(written) is not int or written != len(text):
        raise OSError('output stream did not accept complete text')
    stream.flush()


_DEFAULT_DESTINATION = object()


class _ArgumentParser(argparse.ArgumentParser):
    def _print_message(self, message, file=_DEFAULT_DESTINATION):
        if message:
            _write_text(sys.stderr if file is _DEFAULT_DESTINATION else file, message)


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidPlan('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _execute(argv=None):
    parser = _ArgumentParser(
        description=__doc__,
        **({"color": False} if sys.version_info >= (3, 14) else {}),
        **({"formatter_class": partial(argparse.HelpFormatter, color=False)}
           if sys.version_info[:2] == (3, 14) else {}))
    parser.add_argument('--scheme', required=True,
                        help='JSON file with explicit absolute POSIX scheme paths')
    parser.add_argument('wheels', nargs='+')
    for name, value in vars(Limits()).items():
        parser.add_argument('--' + name.replace('_', '-'), type=int, default=value)
    try:
        args = parser.parse_args(argv)
    except (OSError, ValueError, AttributeError):
        return 2, True
    try:
        raw_scheme = _read_regular(args.scheme, MAX_SCHEME_BYTES)
        if len(raw_scheme) > MAX_SCHEME_BYTES:
            raise InvalidPlan('scheme JSON exceeds 1 MiB byte limit')
        try:
            scheme = json.loads(raw_scheme.decode('utf-8'), object_pairs_hook=no_duplicates)
        except RecursionError as exc:
            raise InvalidPlan('scheme JSON exceeds decoder nesting limit') from exc
        result = audit(args.wheels, scheme, limits=Limits(**{
            name: getattr(args, name) for name in vars(Limits())}))
    except (InvalidPlan, ValueError, OSError) as exc:
        result = {'schema': 1, 'status': 'INVALID', 'error': str(exc)}
        code = 2
    else:
        code = 1 if result['conflicts'] else 0
    try:
        _write_text(sys.stdout, json.dumps(result, sort_keys=(code != 2)) + '\n')
    except (OSError, ValueError, AttributeError):
        return 2, True
    return code, False


def main(argv=None):
    """Return the report exit code without redirecting caller-owned streams."""
    return _execute(argv)[0]


def entrypoint():
    """Process runner: stop failed output from failing again at shutdown."""
    try:
        code, _ = _execute()
    except SystemExit as error:
        code = error.code
    for name in ('stdout', 'stderr'):
        stream = getattr(sys, name)
        if stream is None:
            continue
        try:
            stream.flush()
        except (OSError, ValueError, AttributeError):
            # Only process wrappers own shutdown. Embedded main leaves streams
            # untouched even after failed delivery.
            setattr(sys, name, None)
            code = 2
    return code


if __name__ == '__main__':
    sys.exit(entrypoint())
