"""Private seekable wheel snapshots, exact receipts and bounded source reads."""
import errno
import hashlib
import json
import os
import tempfile
import zipfile
from unittest.mock import patch

import pytest

from test_planner import SCHEME, wheel
from wheelpaths import InvalidPlan, Limits, audit
from wheelpaths.cli import main
from wheelpaths import planner


def test_archive_source_reads_are_chunk_bounded_and_receipt_exact(tmp_path):
    path = wheel(tmp_path, files={'large': b'x' * (3 * 1024 * 1024 + 7)})
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    sizes = []
    real = os.fdopen

    class Spy:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def fileno(self):
            return self.stream.fileno()
        def read(self, size):
            sizes.append(size)
            assert 0 < size <= 1024 * 1024
            return self.stream.read(size)

    with patch.object(planner.os, 'fdopen', lambda *a, **k: Spy(real(*a, **k))):
        report = audit([path], SCHEME)
    assert len(sizes) >= 4
    assert report['wheels'][0]['sha256'] == expected


def test_snapshot_not_reopened_source_supplies_zip_and_hash(tmp_path):
    path = wheel(tmp_path, files={'original': b'yes'})
    expected = audit([path], SCHEME)
    original = planner.zipfile.ZipFile
    seen = []

    def change_source(snapshot, *args, **kwargs):
        path.write_bytes(b'not a zip any more')
        seen.append(snapshot)
        assert not isinstance(snapshot, (str, bytes, os.PathLike))
        return original(snapshot, *args, **kwargs)

    with patch.object(planner.zipfile, 'ZipFile', change_source):
        assert audit([path], SCHEME) == expected
    assert seen[0].closed


@pytest.mark.parametrize('failure', ['create', 'write', 'seek', 'parse', 'metadata'])
def test_snapshot_closed_and_cli_invalid_on_temporary_io_failure(tmp_path, capsys, failure):
    path = wheel(tmp_path)
    scheme = tmp_path / 'scheme.json'
    scheme.write_text(json.dumps(SCHEME))
    real = tempfile.TemporaryFile
    opened = []

    class FailedFile:
        def __init__(self):
            self.stream = real(mode='w+b')
            opened.append(self.stream)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def write(self, data):
            if failure == 'write':
                raise OSError(errno.ENOSPC, 'temporary storage full')
            return self.stream.write(data)
        def seek(self, *args):
            if failure == 'seek':
                raise OSError(errno.EIO, 'temporary seek failed')
            return self.stream.seek(*args)
        def __getattr__(self, name):
            return getattr(self.stream, name)

    def create(*args, **kwargs):
        if failure == 'create':
            raise OSError(errno.EACCES, 'temporary storage unavailable')
        return FailedFile()

    with patch.object(planner.tempfile, 'TemporaryFile', create):
        if failure == 'parse':
            path.write_bytes(b'bad archive')
        if failure == 'metadata':
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('anything', 'missing metadata')
        assert main(['--scheme', str(scheme), str(path)]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'INVALID'
    assert 'claims' not in report
    assert all(stream.closed for stream in opened)


def test_exact_cap_plus_one_snapshot_is_removed_before_refusal(tmp_path):
    path = wheel(tmp_path)
    real = tempfile.TemporaryFile
    opened = []
    def create(*args, **kwargs):
        stream = real(*args, **kwargs)
        opened.append(stream)
        return stream
    with patch.object(planner.tempfile, 'TemporaryFile', create):
        with pytest.raises(InvalidPlan, match='archive byte'):
            audit([path], SCHEME, limits=Limits(max_total_archive_bytes=1))
    assert opened and opened[0].closed


@pytest.mark.skipif(not os.path.isdir('/proc/self/fd'), reason='Linux fd listing')
def test_repeated_success_and_failure_do_not_leak_descriptors(tmp_path):
    good = wheel(tmp_path)
    bad = tmp_path / 'bad-1-py3-none-any.whl'
    bad.write_bytes(b'not zip')
    before = len(os.listdir('/proc/self/fd'))
    for _ in range(20):
        audit([good], SCHEME)
        with pytest.raises(InvalidPlan):
            audit([bad], SCHEME)
    assert len(os.listdir('/proc/self/fd')) == before


def test_short_source_reads_preserve_all_bytes_and_receipt(tmp_path):
    path = wheel(tmp_path, files={'payload': 'abc' * 100})
    expected = audit([path], SCHEME)
    real = os.fdopen
    class ShortReader:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def fileno(self):
            return self.stream.fileno()
        def read(self, size):
            return self.stream.read(min(size, 7))
    with patch.object(planner.os, 'fdopen', lambda *a, **k: ShortReader(real(*a, **k))):
        assert audit([path], SCHEME) == expected
