# Complete snapshot writes, November25,2026

Base main122a404a31b918bf82403e3c2fd56bb150802444. _wheel_snapshot ignored the
return value of snapshot.write(chunk), then hashed source bytes and parsed the
snapshot. Reproduced clear report with source-hash receipt when storage wrapper
drops first1MiB of a wheel prefixed with1MiBX bytes. ZIP accepts prefix data, so
remaining suffix still parses, proving parse success cannot stand in for complete
copy detection. This is injected storage failure, not claimed observed data loss
on an ordinary built-in TemporaryFile.

Require exact integer chunk-write return; refuse before hashing that chunk or
ZIP parsing on failure. Existing audit invalid-output and snapshot/source context
cleanup preserved. No report schema/model/normal archive hash/version changes.
No retry of short writes: fail the whole operation, never issue a partial plan.

305 pytest cases PASS actual3.10.12,3.13.18,3.15.2; original290 retained.
14 new refusal cases cover7badreturnvalues (0,1,None,True,-1,string,intsubclass) through API
and CLI, forbid ZIP parsing on failed copy, check one write and snapshot closure.
Successful prefixedZIP control preserves projected paths and binds everyreceipt
to full source SHA256. Original suite still covers chunked short source reads,
readlimits, mutation-after-snapshot, tempIOerrors, descriptorleaks, collision
oracles and CLI outcomes. Newfile against base:14fail1pass.
Count-check mutant fails6cases. Type-check removal initially survived; added
an exact-length int-subclass adversarial return, and it now fails2cases. Source restored. Sdist/wheelbuildPASS, neutral
fresh3.15 builtwheel all305PASS from/tmp. Two inherited zipfixtureduplicate-name
warnings remain. No test weakened, no intentionalskip, no publication yet.

Reviewfocus: failclosed temporary write boundary, complete hash/snapshot relation,
cleanup, directAPI/CLI INVALID, unchanged successful behavior, clear synthetic
failure framing and no disk-integrity overclaim. No public action beforePASS.
