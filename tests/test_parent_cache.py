"""Shared namespace ancestors must not repeatedly scan the same claim group."""
from unittest.mock import patch

from wheelpaths import audit
from test_planner import SCHEME, wheel


def test_shared_ancestor_claims_scanned_once():
    class CountingRow(dict):
        kind_reads = 0

        def __getitem__(self, key):
            if key == 'kind':
                type(self).kind_reads += 1
            return super().__getitem__(key)

    directories = [CountingRow(target='/env/lib/ns', kind='directory',
                               input=i, member='ns/', wheel='part%s.whl' % i,
                               sha256='synthetic') for i in range(50)]
    children = [CountingRow(target='/env/lib/ns/file%s.py' % i, kind='file',
                            input=0, member='ns/file%s.py' % i,
                            wheel='part0.whl', sha256='synthetic')
                for i in range(200)]
    rows = directories + children
    # Isolate conflict planning from ZIP parsing; all paths and kinds match
    # the claims produced by actual namespace wheels in the next test.
    with patch('wheelpaths.planner.wheel_claims', return_value=({'input': 0}, rows)):
        report = audit(['synthetic.whl'], SCHEME)
    assert report['status'] == 'NO_COLLISIONS_IN_MODEL'
    assert report['claims'] == rows
    # This instrumentation is coupled to the planner's row['kind'] access.
    # A switch to row.get() or another access pattern must update the counter.
    # A pass over each target and a single ancestor-cache pass is linear.
    # The uncached planner reads the shared directory kinds 10,000 times.
    assert CountingRow.kind_reads <= 3 * len(rows)


def test_cache_keeps_directory_and_file_claims_distinct(tmp_path):
    left = wheel(tmp_path, files={'ns/': '', 'ns/a.py': '',
                                 'ns/deep/': '', 'ns/deep/a.py': ''})
    right = wheel(tmp_path, 'beta', {'ns/': '', 'ns/b.py': '',
                                    'ns/deep/': '', 'ns/deep/b.py': ''})
    assert audit([left, right], SCHEME)['conflicts'] == []
    # The same ancestor now also has a file owner. Every child still
    # conflicts, and conflict claim ordering retains the input order.
    blocker = wheel(tmp_path, 'blocker', {'ns': ''})
    report = audit([left, right, blocker], SCHEME)
    conflicts = report['conflicts']
    assert [c['target'] for c in conflicts] == [
        '/env/lib/ns', '/env/lib/ns', '/env/lib/ns', '/env/lib/ns',
        '/env/lib/ns', '/env/lib/ns']
    assert [c['type'] for c in conflicts] == ['same-target'] + ['file-directory'] * 5
    assert [c['claims'][0]['input'] for c in conflicts[1:]] == [2] * 5
    assert all(c['claims'][0]['member'] == 'ns' for c in conflicts[1:])
    # Cache lifetime is one invocation, not a property of a path string.
    assert audit([left, right], SCHEME)['conflicts'] == []
