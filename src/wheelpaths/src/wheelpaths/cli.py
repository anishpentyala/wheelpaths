"""Machine-readable exit codes: 0 no modeled collision, 1 collisions, 2 invalid."""
import argparse
import json
import sys
from .planner import audit, InvalidPlan


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidPlan('duplicate JSON key: ' + key)
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scheme', required=True,
                        help='JSON file with explicit absolute POSIX scheme paths')
    parser.add_argument('wheels', nargs='+')
    args = parser.parse_args(argv)
    try:
        with open(args.scheme, encoding='utf-8') as f:
            scheme = json.load(f, object_pairs_hook=no_duplicates)
        result = audit(args.wheels, scheme)
    except (InvalidPlan, ValueError, OSError) as exc:
        print(json.dumps({'schema': 1, 'status': 'INVALID', 'error': str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 1 if result['conflicts'] else 0


if __name__ == '__main__':
    sys.exit(main())
