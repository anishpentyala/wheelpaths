"""Machine-readable exit codes: 0 no modeled collision, 1 collisions, 2 invalid."""
import argparse
import json
import os
import sys
from .planner import audit, InvalidPlan, Limits


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidPlan('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _execute(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scheme', required=True,
                        help='JSON file with explicit absolute POSIX scheme paths')
    parser.add_argument('wheels', nargs='+')
    for name, value in vars(Limits()).items():
        parser.add_argument('--' + name.replace('_', '-'), type=int, default=value)
    args = parser.parse_args(argv)
    try:
        with open(args.scheme, encoding='utf-8') as f:
            scheme = json.load(f, object_pairs_hook=no_duplicates)
        result = audit(args.wheels, scheme, limits=Limits(**{
            name: getattr(args, name) for name in vars(Limits())}))
    except (InvalidPlan, ValueError, OSError) as exc:
        result = {'schema': 1, 'status': 'INVALID', 'error': str(exc)}
        code = 2
    else:
        code = 1 if result['conflicts'] else 0
    try:
        sys.stdout.write(json.dumps(result, sort_keys=(code != 2)) + '\n')
        sys.stdout.flush()
    except (OSError, ValueError, AttributeError):
        return 2, True
    return code, False


def main(argv=None):
    """Return the report exit code without redirecting caller-owned streams."""
    return _execute(argv)[0]


def entrypoint():
    """Process runner: stop a failed stdout from failing again at shutdown."""
    code, output_failed = _execute()
    if output_failed:
        # A failed buffered flush is retried during interpreter shutdown,
        # which otherwise replaces the intended exit 2 with exit 120.
        try:
            stdout_fd = sys.stdout.fileno()
            null_fd = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(null_fd, stdout_fd)
            finally:
                if null_fd != stdout_fd:
                    os.close(null_fd)
        except (OSError, ValueError, AttributeError):
            sys.stdout = open(os.devnull, 'w')
    return code


if __name__ == '__main__':
    sys.exit(entrypoint())
