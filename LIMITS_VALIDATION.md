# Invocation-wide limits validation

The change adds explicit admission caps to an offline planner. It does not claim
that old behavior accepted corrupt wheels or produced incorrect collision
reports; the missing behavior was an invocation-wide bound.

The existing 72 parameterized tests remain unchanged. New controls check exact
cap equality/overflow, repeated inputs, aggregate rather than per-file counts,
bounded second-file reads, no file open for over-limit wheel lists, no metadata
read before member admission, generated console/gui claims, skipped relocation
directories, per-call budget reset, existing per-archive caps, bad types/ranges,
CLI INVALID with no partial plan and preserved collision exit/report behavior.
All 124 parameterized cases (72 existing plus 52 new) pass on actual Python
3.10, 3.13 and 3.15, matching the existing workflow matrix. Two expected ZIP
warnings come from existing deliberate duplicate-member fixtures. One hundred
seeded valid wheel-set reports match unchanged released local source exactly in
separate processes, including hashes, claims/order and conflicts. This sampled
parity does not prove equality for every possible input.

Four production mutants are caught: disabled wheel count cap (2 failures),
disabled aggregate byte-cap check (3), reset member budget per wheel (1), and
omitted generated-script claim counting (1). Restored tests pass. Some disabled
byte-check cases still fail later as truncated ZIP input: the negative control
checks the explicit aggregate-cap contract, not a claim that every mutant would
produce a falsely clear collision plan.

A fresh neutral installed-wheel Python3.13 run passes all124 cases with isolated
imports outside the checkout. Source/wheel/installed bytes and packaged README/
validation text are checked in the review packet. No hosted checks, performance
claim, external adoption or new original is claimed.
