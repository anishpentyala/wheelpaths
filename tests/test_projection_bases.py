"""Projection keeps exact admitted paths without per-member path parsing."""
import pytest
from unittest.mock import patch
from wheelpaths import audit, InvalidPlan
from wheelpaths.planner import destination, wheel_claims
from test_planner import wheel


@pytest.mark.parametrize('base', ['/', '/env/lib', '/α/lib'])
@pytest.mark.parametrize('pure', ['true', 'false'])
def test_validated_bases_keep_exact_targets(tmp_path, base, pure):
    scheme = dict(purelib=base, platlib=base, scripts=base, data=base)
    path = wheel(tmp_path, pure=pure, files={
        'pkg/a.py': '', 'pkg/': '',
        'alpha-1.0.data/purelib/x.py': '',
        'alpha-1.0.data/platlib/y.py': '',
        'alpha-1.0.data/scripts/bin': '',
        'alpha-1.0.data/data/share/a': '',
        'alpha-1.0.dist-info/entry_points.txt': '[console_scripts]\nhello=alpha:main\n',
    })
    with patch('wheelpaths.planner.destination', side_effect=AssertionError('per-member parse')):
        result = audit([path], scheme)
    targets = {r['member']: r['target'] for r in result['claims']}
    for member, relative in [('pkg/a.py', 'pkg/a.py'), ('pkg/', 'pkg'),
                             ('alpha-1.0.data/purelib/x.py', 'x.py'),
                             ('alpha-1.0.data/data/share/a', 'share/a'),
                             ('alpha-1.0.dist-info/entry_points.txt:console_scripts:hello', 'hello')]:
        assert targets[member] == destination(base, relative)


def test_direct_wheel_claims_preserve_normalized_base(tmp_path):
    path = wheel(tmp_path, files={'pkg/a.py': ''})
    for base in ('//', '//server/share', '/env/lib/', '/a//b', '/a/./b', 'relative', '.'):
        scheme = dict.fromkeys(('purelib', 'platlib', 'scripts', 'data'), base)
        _, rows = wheel_claims(path, scheme, 0)
        row = next(r for r in rows if r['member'] == 'pkg/a.py')
        assert row['target'] == destination(base, 'pkg/a.py')


@pytest.mark.parametrize('base', ['//', '/env/lib/', '/a/../b'])
def test_audit_still_refuses_noncanonical_bases(tmp_path, base):
    path = wheel(tmp_path)
    scheme = dict.fromkeys(('purelib', 'platlib', 'scripts', 'data'), base)
    with pytest.raises(InvalidPlan):
        audit([path], scheme)
