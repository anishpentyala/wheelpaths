# Private qualification, November 11, 2026

## Initial runtime6e5f642

- Actual Python3.10.12,3.11.17 and3.15.1:60passed,zero skips. Two expected
  duplicate-member fixture warnings. Initial logs are in the original packet.
- Initial wheel181b2ffc installed into neutral Python3.12.15:60passed,
  all three package files matched source/wheel/installed bytes.
- Negative control changing only `.data` projection into unrelocated root paths:
  3failed,57deselected. Negative disabling only generated entry-point claims:
  3failed,57deselected. Six corresponding restored tests pass,54deselected.
- Real public jwt/PyJWT wheels, exact downloaded hashes verified:33claims,
  four collisions. pypa installer staged all14first-wheel projected paths and
  refused the second wheel at the predicted jwt/__init__.py collision.
- Independent review reported actual3.10 full60/installed60,source-wheel
  identity,real-wheel/installer witness and both causal negatives reproduced.
  Other interpreter logs inspected,not independently rerun. Additional archive,
  path,CLI and console/gui projection probes passed. Favorable scoped review,
  not maintainer adoption or external audit.

## Runtime follow-ups

- d03cf2e:API nonpath/bytes-pathlike inputs now InvalidPlan. Seven new focused
  cases passed on3.10;old60-test wheel is not this runtime.
- 5fd5694:corrupt deflated WHEEL/METADATA/entrypoints previously raised zlib.error
  and CLI traceback/exit1. Now INVALID/exit2. Metadata compression restricted to
  stored/deflated. Focused3.10:five fail before/five pass after,67deselected.
  Three actual corrupt API+CLI regressions and two new compression-boundary
  guards,not five preexisting defects. Original behavior crashed,not false-clear.
  Focused follow-up review is separate from the initial review described above.

## Current installed artifact, built08:47PST

- Runtime unchanged since5fd5694;source commit9e48f46 includes corpus evidence.
- Fresh wheelSHA256:
  23ba0c3f9ee90b6967bc3f358ab61329ffeda9746f93166912edb9c978608924
- Fresh neutral Python3.12.15 installed artifact:72passed,zero skips,two
  expected duplicate-member fixture warnings. No source checkout on import path.
- All three package files are byte-identical in source,wheel and installation.
- Installed artifact reproduces the exact prior selected ten-wheel report:
  605claims,zero collisions. Provider bytes and169google namespace member
  claims/two generated commands are covered in corpus/;not a dependency solve
  or representative compatibility survey. Previous staging installed all605
  projected paths and two executable commands without overwrite refusal.
- This closes the current installed-artifact gap after runtime edits. It is not
  a repeat of the original interpreter matrix or a new negative-control run.
- These checks were local; they do not establish hosted CI or a package-index release.

Fixtures intentionally include malformed/minimal wheels because this planner
rejects unsupported metadata but does not validate wheel integrity. No finding
is a statement that an unreported wheel is safe or compatible. See LICENSE for the repository license.
