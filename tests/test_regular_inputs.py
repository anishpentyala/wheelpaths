"""Descriptor-bound input admission, with subprocess deadlines for named pipes."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from test_planner import SCHEME, wheel

from wheelpaths import InvalidPlan, audit
from wheelpaths.cli import MAX_SCHEME_BYTES, main
from wheelpaths.planner import _read_regular

HAS_FIFO = hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK")


def run_bounded(command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=3)
    except subprocess.TimeoutExpired:
        pytest.fail("input admission blocked for more than three seconds")


@pytest.mark.skipif(not HAS_FIFO, reason="requires POSIX FIFO and nonblocking open")
@pytest.mark.parametrize("role", ["scheme", "wheel", "later-wheel"])
def test_cli_refuses_writerless_fifo_before_any_plan(tmp_path, role):
    scheme = tmp_path / "scheme.json"
    scheme.write_text(json.dumps(SCHEME))
    good = wheel(tmp_path)
    pipe = tmp_path / "pipe-1-py3-none-any.whl"
    os.mkfifo(pipe)
    args = [sys.executable, "-m", "wheelpaths.cli", "--scheme"]
    if role == "scheme":
        args += [str(pipe), str(good)]
    else:
        args += [str(scheme)]
        if role == "later-wheel":
            args.append(str(good))
        args.append(str(pipe))
    result = run_bounded(args)
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["status"] == "INVALID"
    assert "claims" not in report
    assert "regular file" in report["error"]
    assert "Traceback" not in result.stderr


@pytest.mark.skipif(not HAS_FIFO, reason="requires POSIX FIFO and nonblocking open")
def test_api_fifo_is_invalid_plan_not_blocking(tmp_path):
    path = tmp_path / "pipe-1-py3-none-any.whl"
    os.mkfifo(path)
    command = [sys.executable, "-c", "", str(path)]
    command[2] = (
        "import sys; from wheelpaths import audit,InvalidPlan; "
        "scheme=" + repr(SCHEME) + ";\n"
        "try: audit([sys.argv[1]], scheme)\n"
        "except InvalidPlan: sys.exit(2)\n"
    )
    result = run_bounded(command)
    assert result.returncode == 2
    assert not result.stdout
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("extra", [0, 1])
def test_scheme_exact_byte_boundary_and_refusal_before_wheel(tmp_path, capsys, extra):
    encoded = json.dumps(SCHEME).encode()
    scheme = tmp_path / "scheme.json"
    scheme.write_bytes(encoded + b" " * (MAX_SCHEME_BYTES - len(encoded) + extra))
    target = wheel(tmp_path)
    if extra:
        with patch(
            "wheelpaths.cli.audit", side_effect=AssertionError("must not audit")
        ):
            assert main(["--scheme", str(scheme), str(target)]) == 2
        report = json.loads(capsys.readouterr().out)
        assert report["status"] == "INVALID"
        assert "1 MiB" in report["error"]
    else:
        assert main(["--scheme", str(scheme), str(target)]) == 0
        assert json.loads(capsys.readouterr().out) == audit([target], SCHEME)


def test_regular_helper_reads_only_admission_limit_plus_one(tmp_path):
    path = tmp_path / "input"
    path.write_bytes(b"0123456789")
    assert _read_regular(path, 4) == b"01234"
    assert _read_regular(path, 0) == b"0"


@pytest.mark.skipif(not Path("/dev/null").exists(), reason="requires Unix null device")
def test_device_and_directory_refused(tmp_path):
    with pytest.raises(InvalidPlan, match="regular file"):
        _read_regular("/dev/null", 100)
    with pytest.raises((InvalidPlan, OSError)):
        _read_regular(tmp_path, 100)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="requires symbolic links")
def test_regular_file_symlink_retains_report_and_receipts(tmp_path):
    target = wheel(tmp_path)
    alias = tmp_path / "alias"
    alias.mkdir()
    link = alias / target.name
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symbolic link unavailable")
    assert audit([link], SCHEME) == audit([target], SCHEME)


@pytest.mark.skipif(
    not Path("/proc/self/fd").exists(), reason="requires Linux fd listing"
)
def test_nonregular_refusals_do_not_leak_descriptors():
    before = len(list(Path("/proc/self/fd").iterdir()))
    for _ in range(100):
        with pytest.raises(InvalidPlan):
            _read_regular("/dev/null", 1)
    assert len(list(Path("/proc/self/fd").iterdir())) == before
