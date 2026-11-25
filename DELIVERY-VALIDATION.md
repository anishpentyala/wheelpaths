# Output delivery correction, November 24, 2026

Base: 57575268be459ee301bdc56f23af33c8f9eb18bf.

Baseline regression suite: 39 failures, 22 passes. Report streams returning a
short/non-integer count were accepted; parser help/usage failures escaped the
report-output boundary or became exit 120 during interpreter shutdown.

Correction: one checked text writer for report/help/usage. Parsing alone has a
delivery exception boundary. Unexpected planner AttributeError remains visible.
The process wrapper catches normal parser SystemExit and checks stdout/stderr
flushes. Embedded main never closes, replaces or inspects caller descriptors.
No report fields, ordering, collision semantics, version or package release
changes. No installer or safety claims.

Final actual Python 3.10.12, 3.13.18, 3.15.2: 290 passed each. Two expected
zipfile duplicate-member fixture warnings each. Built sdist and wheel; neutral
installed-wheel test from /tmp under Python 3.15.2: 290 passed. Baseline and all
final logs accompany review packet.

New tests include report counts 0/1/None/True/-1/string, caller stream preservation,
help/usage destinations with write/flush/closed/None failures, actual module and
console help/usage to /dev/full and closed pipes, both shutdown stream flushes,
unchanged normal output, and unexpected planner-error scope. Existing tests
cover normal complete reports, missing stdout at interpreter startup, installed
module/console output, nested scheme decode rejection and forced-color help.

Four single-fault mutants killed: count-check bypass, standard argparse bypass,
writer flush omission, process shutdown-flush omission. Source restored after
each run. No public action before independent review.
