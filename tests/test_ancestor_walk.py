"""Canonical projected targets need only a lexical parent walk."""
from pathlib import PurePosixPath
from unittest.mock import patch

import pytest

from wheelpaths import InvalidPlan, Limits, audit
from wheelpaths import planner
from test_planner import SCHEME, wheel


def test_ancestor_walk_does_not_materialize_path_parents(tmp_path):
    class WithoutParents(PurePosixPath):
        @property
        def parents(self):
            raise AssertionError('per-target path parent objects')

    path = wheel(tmp_path, files={'a/b/c.py': '', 'a/': ''})
    expected = audit([path], SCHEME)
    with patch.object(planner, 'PurePosixPath', WithoutParents):
        assert audit([path], SCHEME) == expected


@pytest.mark.parametrize('base', ['/', '/env/lib', '/δοκιμή/space here'])
def test_nested_ancestor_order_and_reference_budget(tmp_path, base):
    path = wheel(tmp_path, files={
        'a': '', 'a/b': '', 'a/b/c': '', 'a/b/c/file.py': ''})
    scheme = dict(SCHEME, purelib=base)
    report = audit([path], scheme)
    target = str(PurePosixPath(base) / 'a/b/c/file.py')
    conflicts = [c for c in report['conflicts']
                 if any(r['target'] == target for r in c['claims'])]
    assert [c['target'] for c in conflicts] == [
        str(PurePosixPath(base) / name) for name in ('a/b/c', 'a/b', 'a')]
    refs = sum(len(c['claims']) for c in report['conflicts'])
    assert audit([path], scheme, limits=Limits(max_conflict_claims=refs)) == report
    with pytest.raises(InvalidPlan, match='conflict claim reference limit'):
        audit([path], scheme, limits=Limits(max_conflict_claims=refs - 1))


def test_sibling_prefixes_are_not_ancestors(tmp_path):
    path = wheel(tmp_path, files={'a': '', 'ab/deep/file.py': ''})
    assert audit([path], SCHEME)['conflicts'] == []
