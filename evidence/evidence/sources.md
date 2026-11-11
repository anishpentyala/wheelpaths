# Source ledger, fetched November 11, 2026

1. Python Packaging Authority wheel specification, primary standard:
   https://packaging.python.org/en/latest/specifications/binary-distribution-format/
   Root-Is-Purelib chooses root scheme; .data subtrees relocate to scheme keys;
   installers generate/rewrite scripts and may compile bytecode. High confidence.
2. pip issue4625, user/maintainer discussion:
   https://github.com/pypa/pip/issues/4625
   Documents installed-distribution file overwrites, jwt/PyJWT among examples.
   Evidence of problem, not proof every current pip path behaves identically.
3. pip PR14249, implementation proposal:
   https://github.com/pypa/pip/pull/14249
   Describes installed RECORD dictionary and overwrite warnings after writes.
   No merged/current-runtime claim made from proposal text.
4. uv PR13437, implementation/discussion:
   https://github.com/astral-sh/uv/pull/13437
   Describes top-level __init__.py collision warning with namespace exclusions.
   Overlap acknowledged; no present release-state claim made.
5. check-wheel-contents README, existing tool primary source:
   https://github.com/jwodder/check-wheel-contents
   Individual wheel content checks; W002 is duplicate contents within one wheel,
   not evidence of this candidate's cross-archive projected-target plan workflow.
6. ModuleGuard ICSE2024 paper, research:
   https://arxiv.org/html/2401.02090
   Installation-free module extraction, dependency/module namespace conflicts,
   case-insensitive conflicts. Substantial overlap in general problem, no novelty
   claim for conflict detection. Candidate only lexical path projections.
7. pypa installer API documentation, primary:
   https://installer.pypa.io/en/stable/api/sources/
   https://installer.pypa.io/en/stable/api/destinations/
   Wheel source, explicit scheme destinations, script generation, overwrite flag.
8. pip check command, primary:
   https://pip.pypa.io/en/latest/cli/pip_check/
   Dependency compatibility, not filesystem path plan.
9. pip-conflict-checker, existing tool primary:
   https://pypi.org/project/pip-conflict-checker/
   Installed requirements/version compatibility, not filesystem path plan.
10. wheelaudit source, existing tool primary:
    https://raw.githubusercontent.com/kriskimmerle/wheelaudit/main/wheelaudit.py
    Wheel security/structure scoring, entry points/path traversal/namespace checks.
    Does not justify claiming no similar tools exist; candidate scope remains
    explicit cross-wheel destination planning rather than security scoring.
11. wheel-inspect, existing tool primary:
    https://github.com/wheelodex/wheel-inspect
    Wheel metadata/content JSON extraction. Possible input building block,
    not assumed to emit this candidate's projection/collision verdicts.

Actual real-wheel URLs/hashes come from PyPI's live release JSON and are preserved
in project evidence/downloads.json, then independently matched to downloaded bytes.
