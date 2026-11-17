import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from wheelpaths.cli import main
from test_planner import SCHEME, wheel


def args_for(tmp_path, status):
    scheme = tmp_path/'scheme.json'
    scheme.write_text(json.dumps(SCHEME))
    a = wheel(tmp_path, files={'shared.py': ''})
    b = wheel(tmp_path, 'beta', {'shared.py': ''})
    wheels = {'clear': [str(a)], 'collision': [str(a), str(b)],
              'invalid': [str(tmp_path/'missing.whl')]}[status]
    return ['--scheme', str(scheme)] + wheels


COMMANDS = [[sys.executable, '-m', 'wheelpaths.cli'],
            [str(Path(sys.executable).parent/'wheelpaths')]]


@pytest.mark.parametrize('command', COMMANDS)
@pytest.mark.parametrize('status', ['clear', 'collision', 'invalid'])
@pytest.mark.parametrize('sink', ['full', 'closed_pipe'])
def test_process_output_failure_exit_2(tmp_path, command, status, sink):
    args = args_for(tmp_path, status)
    if sink == 'full':
        if not Path('/dev/full').exists():
            pytest.skip('requires /dev/full')
        with open('/dev/full', 'wb') as target:
            result = subprocess.run(command + args, stdout=target, stderr=subprocess.PIPE)
    else:
        r, w = os.pipe()
        os.close(r)
        try:
            result = subprocess.run(command + args, stdout=w, stderr=subprocess.PIPE)
        finally:
            os.close(w)
    assert result.returncode == 2
    assert result.stderr == b''


@pytest.mark.parametrize('status', ['clear', 'collision', 'invalid'])
@pytest.mark.parametrize('failure', ['write', 'flush', 'closed'])
def test_callable_preserves_caller_stream(tmp_path, monkeypatch, status, failure):
    args = args_for(tmp_path, status)

    class CallerStream:
        def write(self, text):
            if failure == 'write':
                raise OSError('simulated write failure')
            if failure == 'closed':
                raise ValueError('closed output')
            return len(text)

        def flush(self):
            raise OSError('simulated flush failure')

        def close(self):
            raise AssertionError('must not close caller stream')

        def fileno(self):
            raise AssertionError('must not inspect caller descriptor')

    stream = CallerStream()
    monkeypatch.setattr(sys, 'stdout', stream)
    assert main(args) == 2
    assert sys.stdout is stream


@pytest.mark.parametrize('setup', [
    'import io; sys.stdout=io.StringIO(); sys.stdout.close()', 'os.close(1)'])
def test_process_unusable_stdout_exit_2(tmp_path, setup):
    args = args_for(tmp_path, 'clear')
    result = subprocess.run([
        sys.executable, '-c', 'import sys,os; from wheelpaths.cli import entrypoint; '
        + setup + '; raise SystemExit(entrypoint())'] + args, capture_output=True)
    assert result.returncode == 2 and result.stdout == result.stderr == b''


def _close_stdout_at_exec():
    os.close(1)


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX fd inheritance')
@pytest.mark.parametrize('command', COMMANDS)
@pytest.mark.parametrize('status', ['clear', 'collision', 'invalid'])
def test_process_no_stdout_at_interpreter_start(tmp_path, command, status):
    # Unlike os.close(1) after startup, Python initializes sys.stdout to None.
    result = subprocess.run(command + args_for(tmp_path, status),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            preexec_fn=_close_stdout_at_exec)
    assert result.returncode == 2 and result.stdout == result.stderr == b''


@pytest.mark.parametrize('status', ['clear', 'collision', 'invalid'])
def test_callable_none_stdout_returns_2_without_replacing_it(tmp_path, monkeypatch, status):
    args = args_for(tmp_path, status)
    monkeypatch.setattr(sys, 'stdout', None)
    assert main(args) == 2
    assert sys.stdout is None
