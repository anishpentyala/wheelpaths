# Offline wheel destination planning, November 11, 2026

Tool built after source comparison. The real problem is established;
conflict detection is not novel. ModuleGuard covers module conflicts, individual
wheel linters cover archive structure, and installers/package managers have
related overwrite checks. This candidate's useful bounded workflow is a JSON
path-projection report for an explicitly chosen wheel set and POSIX destination
scheme, including non-module data and generated command paths, without installs.

The prototype is not a full installation simulation. It deliberately reports all
exclusions, rejects unsupported headers/layouts, and calls a clear result
NO_COLLISIONS_IN_MODEL rather than safe/compatible. Script-generation assumptions, directory projections, malformed inputs,
and boundaries against existing tools are important limits to inspect.

Real jwt/PyJWT wheel overlap reproduced offline and checked against actual pypa
installer writes in disposable staging. Synthetic relocation/script mechanism
negative controls fail as expected. Local tests and examples are not evidence of upstream adoption.
