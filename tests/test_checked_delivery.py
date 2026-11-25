"""All user-visible text must be delivered before returning a normal verdict."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from wheelpaths import cli
from test_output import COMMANDS, args_for


@pytest.mark.parametrize('status', ['clear', 'collision', 'invalid'])
@pytest.mark.parametrize('accepted', [0, 1, None, True, -1, 'all'])
def test_short_or_invalid_write_is_not_a_delivered_report(tmp_path, monkeypatch, status, accepted):
    class Stream(io.StringIO):
        def write(self, text):
            super().write(text[:1])
            return accepted
    stream = Stream()
    monkeypatch.setattr(sys, 'stdout', stream)
    assert cli.main(args_for(tmp_path, status)) == 2
    assert sys.stdout is stream and not stream.closed


@pytest.mark.parametrize('arguments', [['--help'], [], ['--unknown']])
@pytest.mark.parametrize('destination', ['stdout', 'stderr'])
@pytest.mark.parametrize('failure', ['write', 'flush', 'short', 'closed', 'none'])
def test_parser_delivery_failure_returns_2_without_touching_streams(monkeypatch, arguments,
                                                                destination, failure):
    class Stream(io.StringIO):
        def write(self, text):
            if failure == 'write':
                raise OSError('write failed')
            if failure == 'short':
                return 0
            return super().write(text)
        def flush(self):
            if failure == 'flush':
                raise OSError('flush failed')
            return super().flush()
    out, err = io.StringIO(), io.StringIO()
    target = Stream()
    if failure == 'closed':
        target.close()
    if failure == 'none':
        target = None
    if destination == 'stdout':
        out = target
    else:
        err = target
    monkeypatch.setattr(sys, 'stdout', out)
    monkeypatch.setattr(sys, 'stderr', err)
    # Only the actual destination failing should change parser behavior.
    affected = destination == ('stdout' if arguments == ['--help'] else 'stderr')
    if affected:
        assert cli.main(arguments) == 2
    else:
        with pytest.raises(SystemExit) as caught:
            cli.main(arguments)
        assert caught.value.code == (0 if arguments == ['--help'] else 2)
    assert sys.stdout is out and sys.stderr is err


@pytest.mark.parametrize('command', COMMANDS)
@pytest.mark.parametrize('arguments', [['--help'], [], ['--unknown']])
@pytest.mark.parametrize('sink', ['full', 'closed_pipe'])
def test_process_parser_output_failure_is_2(command, arguments, sink):
    destination = 'stdout' if arguments == ['--help'] else 'stderr'
    if sink == 'full':
        if not Path('/dev/full').exists():
            pytest.skip('requires /dev/full')
        with open('/dev/full', 'wb') as target:
            result = subprocess.run(command + arguments, **{destination: target},
                                    **{('stderr' if destination == 'stdout' else 'stdout'):
                                       subprocess.PIPE})
    else:
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            result = subprocess.run(command + arguments, **{destination: write_fd},
                                    **{('stderr' if destination == 'stdout' else 'stdout'):
                                       subprocess.PIPE})
        finally:
            os.close(write_fd)
    assert result.returncode == 2
    if destination == 'stdout':
        assert result.stderr == b''
    else:
        assert result.stdout == b''


def test_successful_report_is_identical(tmp_path, capsys):
    args = args_for(tmp_path, 'clear')
    assert cli.main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'NO_COLLISIONS_IN_MODEL'


@pytest.mark.parametrize('exception', [OSError, ValueError, AttributeError])
def test_unexpected_planner_failure_is_not_output_failure(tmp_path, monkeypatch, exception):
    def broken(*args, **kwargs):
        raise exception('planner defect')
    monkeypatch.setattr(cli, 'audit', broken)
    # Existing input boundary intentionally converts OSError/ValueError to
    # INVALID JSON. AttributeError is an unexpected defect, never delivery.
    if exception is AttributeError:
        with pytest.raises(AttributeError, match='planner defect'):
            cli.main(args_for(tmp_path, 'clear'))
    else:
        assert cli.main(args_for(tmp_path, 'clear')) == 2


@pytest.mark.parametrize('name', ['stdout', 'stderr'])
def test_process_wrapper_checks_last_flush(monkeypatch, name):
    class LateFailure(io.StringIO):
        def flush(self):
            raise OSError('late flush')
    stream = LateFailure()
    monkeypatch.setattr(sys, name, stream)
    monkeypatch.setattr(cli, '_execute', lambda: (0, False))
    assert cli.entrypoint() == 2
    assert getattr(sys, name) is None
    assert not stream.closed
