"""Conflict admission counts references, not unique claims or conflicts."""
import json
from dataclasses import replace
from unittest.mock import patch

import pytest

from wheelpaths import InvalidPlan, Limits, audit
from wheelpaths.cli import main
from test_planner import SCHEME, wheel


def fixture(tmp_path):
    a = wheel(tmp_path, files={'node': 'file', 'node/child': 'child'})
    b = wheel(tmp_path, 'beta', {'node': 'other', 'node/child': 'other child'})
    return [a, b]


def references(report):
    return sum(len(c['claims']) for c in report['conflicts'])


def test_exact_boundary_same_target_and_ancestor_conflicts(tmp_path):
    wheels = fixture(tmp_path)
    report = audit(wheels, SCHEME)
    assert [c['type'] for c in report['conflicts']] == ['same-target', 'same-target', 'file-directory']
    assert references(report) == 8
    assert report == audit(wheels, SCHEME, limits=Limits(max_conflict_claims=8))
    with pytest.raises(InvalidPlan, match='conflict claim reference'):
        audit(wheels, SCHEME, limits=Limits(max_conflict_claims=7))


def test_budget_counts_repeated_references_not_unique_claims(tmp_path):
    wheels = fixture(tmp_path)
    report = audit(wheels, SCHEME)
    assert len({(r['input'], r['member']) for c in report['conflicts'] for r in c['claims']}) == 4
    with pytest.raises(InvalidPlan, match='conflict claim reference'):
        audit(wheels, SCHEME, limits=Limits(max_conflict_claims=4))


def test_high_fanout_refused_but_claims_admitted(tmp_path):
    a = wheel(tmp_path, files={'node': '', **{'node/c%s' % i: '' for i in range(100)}})
    report = audit([a], SCHEME, limits=Limits(max_claims=103))
    assert len(report['claims']) == 103
    assert references(report) == 200
    with pytest.raises(InvalidPlan, match='conflict claim reference'):
        audit([a], SCHEME, limits=Limits(max_claims=103, max_conflict_claims=199))
    assert audit([a], SCHEME, limits=Limits(max_claims=103, max_conflict_claims=200)) == report


def test_no_conflicts_shared_directories_and_budget_reset(tmp_path):
    a = wheel(tmp_path, files={'namespace/': '', 'namespace/a.py': ''})
    b = wheel(tmp_path, 'beta', {'namespace/': '', 'namespace/b.py': ''})
    limits = Limits(max_conflict_claims=1)
    assert audit([a, b], SCHEME, limits=limits)['conflicts'] == []
    for _ in range(2):
        assert audit(fixture(tmp_path), SCHEME, limits=Limits(max_conflict_claims=8))['status'] == 'COLLISIONS'


@pytest.mark.parametrize('value', [True, False, 0, -1, 1.5, '2', None, 10**12 + 1])
def test_invalid_reference_caps_fail_before_archive_io(value):
    with patch('builtins.open', side_effect=AssertionError('no reads')):
        with pytest.raises(InvalidPlan):
            replace(Limits(), max_conflict_claims=value)


def test_cli_budget_failure_is_invalid_not_truncated_collisions(tmp_path, capsys):
    wheels = fixture(tmp_path)
    scheme = tmp_path / 'scheme.json'
    scheme.write_text(json.dumps(SCHEME))
    args = ['--scheme', str(scheme), '--max-conflict-claims', '7', *map(str, wheels)]
    assert main(args) == 2
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'INVALID'
    assert 'conflicts' not in report and 'claims' not in report
    args[args.index('7')] = '8'
    assert main(args) == 1
    assert json.loads(capsys.readouterr().out) == audit(wheels, SCHEME)


def test_rejection_precedes_combined_claim_list_allocation(tmp_path):
    from collections import defaultdict

    class NoConcatenation(list):
        def __add__(self, other):
            raise AssertionError('conflict claims concatenated before admission')

        __radd__ = __add__

    a = wheel(tmp_path, files={'node': '', 'node/child': ''})
    with patch('wheelpaths.planner.defaultdict', return_value=defaultdict(NoConcatenation)):
        with pytest.raises(InvalidPlan, match='conflict claim reference'):
            audit([a], SCHEME, limits=Limits(max_conflict_claims=1))
