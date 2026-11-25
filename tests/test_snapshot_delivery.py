"""Never parse a valid-looking suffix when snapshot storage drops source bytes."""
import hashlib
import json
import tempfile
from unittest.mock import patch

import pytest

from test_planner import SCHEME, wheel
from wheelpaths import InvalidPlan, audit, planner
from wheelpaths.cli import main


@pytest.mark.parametrize('accepted', [0, 1, None, True, -1, 'all', 'int-subclass'])
@pytest.mark.parametrize('invocation', ['api', 'cli'])
def test_incomplete_snapshot_write_refuses_even_valid_zip_suffix(tmp_path, capsys,
                                                               accepted, invocation):
    path = wheel(tmp_path)
    # ZIP accepts prepended data. Dropping this first whole chunk still leaves
    # a parsable ZIP, so parse success cannot detect incomplete snapshot copies.
    path.write_bytes(b'X' * (1024 * 1024) + path.read_bytes())
    real = tempfile.TemporaryFile
    opened = []
    writes = []

    class Storage:
        def __init__(self, *args, **kwargs):
            self.stream = real(*args, **kwargs)
            opened.append(self.stream)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def write(self, data):
            writes.append(len(data))
            if len(writes) == 1:
                if accepted == 'int-subclass':
                    class Count(int):
                        pass
                    return Count(len(data))
                return accepted
            return self.stream.write(data)
        def __getattr__(self, name):
            return getattr(self.stream, name)

    scheme = tmp_path / 'scheme.json'
    scheme.write_text(json.dumps(SCHEME))
    with patch.object(planner.tempfile, 'TemporaryFile', Storage), \
            patch.object(planner.zipfile, 'ZipFile', side_effect=AssertionError('must not parse')):
        if invocation == 'api':
            with pytest.raises(InvalidPlan, match='snapshot.*complete'):
                audit([path], SCHEME)
        else:
            assert main(['--scheme', str(scheme), str(path)]) == 2
            report = json.loads(capsys.readouterr().out)
            assert report['status'] == 'INVALID'
            assert 'claims' not in report and 'wheels' not in report
    assert writes == [1024 * 1024]
    assert opened and all(stream.closed for stream in opened)


def test_complete_prefixed_zip_keeps_exact_report_and_receipt(tmp_path):
    path = wheel(tmp_path, files={'payload': b'x' * 100})
    normal = audit([path], SCHEME)
    path.write_bytes(b'X' * (1024 * 1024) + path.read_bytes())
    report = audit([path], SCHEME)
    expected_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert report['wheels'][0]['sha256'] == expected_hash
    for claim in report['claims']:
        assert claim['sha256'] == expected_hash
    # Only archive receipt changes; projected paths are independent of prefix.
    assert [r['target'] for r in report['claims']] == [r['target'] for r in normal['claims']]
    assert report['status'] == normal['status']
