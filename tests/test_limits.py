"""Exact admission boundaries, bounded reads and collision report compatibility."""
import json
import os
from dataclasses import replace
from unittest.mock import patch

import pytest

from wheelpaths import InvalidPlan, Limits, audit
from wheelpaths.cli import main
from test_planner import SCHEME, wheel


def test_default_limits_ordinary_report_exact_and_explicit_large_caps(tmp_path):
    a = wheel(tmp_path, files={'shared.py': 'one'})
    b = wheel(tmp_path, 'beta', {'shared.py': 'two'})
    original = audit([a, b], SCHEME)
    assert original == audit([a, b], SCHEME, limits=Limits())
    assert original == audit([a, b], SCHEME, limits=Limits(1000, 10**10, 10**7, 10**7))
    assert original['status'] == 'COLLISIONS'
    assert set(original) == {'schema', 'status', 'scheme', 'wheels', 'claims', 'conflicts', 'scope', 'excluded'}


def test_wheel_limit_before_any_file_open_and_boundary(tmp_path):
    a = wheel(tmp_path)
    assert audit([a], SCHEME, limits=Limits(max_wheels=1))['status'] == 'NO_COLLISIONS_IN_MODEL'
    with patch('builtins.open', side_effect=AssertionError('must not open')):
        with pytest.raises(InvalidPlan, match='wheel count'):
            audit([a, a], SCHEME, limits=Limits(max_wheels=1))


def test_total_archive_bytes_exact_boundary_and_repeated_inputs_count(tmp_path):
    a = wheel(tmp_path)
    size = a.stat().st_size
    assert audit([a, a], SCHEME, limits=Limits(max_total_archive_bytes=2 * size))['status'] == 'COLLISIONS'
    with pytest.raises(InvalidPlan, match='total archive byte'):
        audit([a, a], SCHEME, limits=Limits(max_total_archive_bytes=2 * size - 1))


def test_second_archive_read_only_remaining_budget_plus_one(tmp_path):
    a = wheel(tmp_path)
    b = wheel(tmp_path, 'beta', {'payload': 'x' * 10000})
    size = a.stat().st_size
    observed = []
    real_fdopen = os.fdopen

    class ReadSpy:
        def __init__(self, stream):
            self.file = stream

        def __enter__(self):
            return self

        def fileno(self):
            return self.file.fileno()

        def __exit__(self, *args):
            self.file.close()

        def read(self, count):
            observed.append(count)
            return self.file.read(count)

    def op(fd, *args, **kw):
        is_second = os.fstat(fd).st_ino == b.stat().st_ino
        stream = real_fdopen(fd, *args, **kw)
        return ReadSpy(stream) if is_second else stream

    with patch('os.fdopen', op):
        with pytest.raises(InvalidPlan, match='total archive byte'):
            audit([a, b], SCHEME, limits=Limits(max_total_archive_bytes=size + 7))
    assert observed == [8]


def test_zero_remaining_accepts_eof_only_and_rejects_next_archive(tmp_path):
    a = wheel(tmp_path)
    with pytest.raises(InvalidPlan, match='total archive byte'):
        audit([a, a], SCHEME, limits=Limits(max_total_archive_bytes=a.stat().st_size))


def test_total_member_cap_counts_directory_and_metadata_entries(tmp_path):
    a = wheel(tmp_path, files={'pkg/': '', 'pkg/a.py': ''})
    assert len(audit([a, a], SCHEME, limits=Limits(max_total_members=8))['claims']) == 8
    with pytest.raises(InvalidPlan, match='total ZIP member'):
        audit([a, a], SCHEME, limits=Limits(max_total_members=7))


def test_generated_console_and_gui_claims_have_independent_cap(tmp_path):
    a = wheel(tmp_path, files={'alpha-1.0.dist-info/entry_points.txt': '[console_scripts]\na = alpha:run\nb = alpha:run\n[gui_scripts]\nc = alpha:run\n'})
    assert len(audit([a], SCHEME, limits=Limits(max_claims=6, max_total_members=3))['claims']) == 6
    with pytest.raises(InvalidPlan, match='projected claim'):
        audit([a], SCHEME, limits=Limits(max_claims=5))


def test_skipped_relocation_directory_members_still_count_as_members(tmp_path):
    a = wheel(tmp_path, files={'alpha-1.0.data/': '', 'alpha-1.0.data/data/': '', 'alpha-1.0.data/data/x': ''})
    assert len(audit([a], SCHEME, limits=Limits(max_total_members=5, max_claims=3))['claims']) == 3
    with pytest.raises(InvalidPlan, match='total ZIP member'):
        audit([a], SCHEME, limits=Limits(max_total_members=4))


def test_claim_cap_is_cumulative_across_wheels_and_no_state_leak(tmp_path):
    a = wheel(tmp_path)
    assert len(audit([a, a], SCHEME, limits=Limits(max_claims=4))['claims']) == 4
    with pytest.raises(InvalidPlan, match='projected claim'):
        audit([a, a], SCHEME, limits=Limits(max_claims=3))
    assert len(audit([a], SCHEME, limits=Limits(max_claims=2))['claims']) == 2
    assert len(audit([a], SCHEME, limits=Limits(max_claims=2))['claims']) == 2


@pytest.mark.parametrize('field', list(vars(Limits())))
@pytest.mark.parametrize('value', [True, False, 0, -1, 1.5, '1', None, 10**12 + 1])
def test_invalid_cap_types_and_ranges(field, value):
    with pytest.raises(InvalidPlan):
        replace(Limits(), **{field: value})


@pytest.mark.parametrize('value', [{}, 1, True, 'limits'])
def test_invalid_limits_object(tmp_path, value):
    with pytest.raises(InvalidPlan, match='Limits instance'):
        audit([wheel(tmp_path)], SCHEME, limits=value)


def test_member_limit_enforced_before_metadata_reads(tmp_path):
    a = wheel(tmp_path)
    with patch('zipfile.ZipFile.open', side_effect=AssertionError('metadata not admitted')):
        with pytest.raises(InvalidPlan, match='total ZIP member'):
            audit([a], SCHEME, limits=Limits(max_total_members=1))


@pytest.mark.parametrize('option,value', [('--max-wheels', '1'), ('--max-total-archive-bytes', '1'), ('--max-total-members', '1'), ('--max-claims', '1')])
def test_cli_late_or_early_budget_error_is_invalid_not_partial(tmp_path, capsys, option, value):
    a = wheel(tmp_path)
    scheme = tmp_path / 'scheme.json'
    scheme.write_text(json.dumps(SCHEME))
    assert main(['--scheme', str(scheme), option, value, str(a), str(a)]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'INVALID'
    assert 'claims' not in report and 'conflicts' not in report and 'wheels' not in report


def test_cli_raise_cap_preserves_collisions_exit_one(tmp_path, capsys):
    a = wheel(tmp_path)
    scheme = tmp_path / 'scheme.json'
    scheme.write_text(json.dumps(SCHEME))
    assert main(['--scheme', str(scheme), '--max-wheels', '2', '--max-claims', '4', str(a), str(a)]) == 1
    assert json.loads(capsys.readouterr().out) == audit([a, a], SCHEME)


def test_previous_per_archive_member_limit_still_applies(tmp_path, monkeypatch):
    a = wheel(tmp_path)
    monkeypatch.setattr('wheelpaths.planner.MAX_MEMBERS', 1)
    with pytest.raises(InvalidPlan, match='wheel exceeds member'):
        audit([a], SCHEME, limits=Limits(max_total_members=1000))
