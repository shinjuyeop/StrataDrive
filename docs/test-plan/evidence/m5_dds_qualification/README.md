# M5 gate-closed DDS qualification follow-up

후속: [Host 환경·운용 후보 점검](../m5_dds_operating_profile/README.md)은 별도45 attempts와
진단 수정/비교 근거다. 이 문서의42회23 PASS/19 FAIL·초기 setup 실패·추가 진단·Daybreak
중단 이력을 변경하지 않는다. 후속 후보의 close 미재현으로 이 기록의 close/TSan OPEN을 닫지 않는다.

`658562e` 뒤 [종료·TSan 경로별 후속](../m5_dds_shutdown_followup/README.md)은 원본 GDB와
새 성공 조건을 대조하고 SDK 문의 초안을 보존했다. 잠금 준비 수정 뒤 Python29/29이며,
그 안의 실제 child timeout 검증은 아래 과거 미재현 cleanup 시도와 별개다. 새 SDK 실행은0회다.

2026-10-21. Reference `7bbafc7`; runner fix `9136c1f` plus exact diagnostic
sources in [provenance](provenance.json) and each archived cohort's metadata.
**User approved B: Host native IO/FIFO component LIMITED ACCEPTANCE.**
**M4 whole NOT CLOSED; DDS regular control gate CLOSED; no control adapter.**
[Scope](../../../m4_host_acceptance_review.md), [gate decisions](gate.json).

This work uses unchanged CycloneDDS11.0.1/e54e991, the same normal/full-ASan/
full-TSan SDK libraries as the preceding evidence. No SDK source patch, dependency
upgrade, annotation, suppression or blanket atomic replacement was applied.
Application production directories/CMake and the prior973/48-run evidence are
unchanged; no new973 regression, native40 or timing48 is claimed.

## Runner defect corrected first

A syntactically valid `[]`/`null`/string result used to abort aggregation or an
incomplete dict could pass. `result_schema_errors` now validates root object,
verdict enum, two integer probe exits, nonnegative integer counters and both
complete role summaries. Booleans are not accepted as integer counters. Optional
error lists must contain strings. Nonzero probe/runner exits remain failures.
No absent metric is defaulted to PASS. Original malformed `result.json` remains;
child-generated raw output is copied to `result.original.json` before validation.

Focused22 actual runner-process tests: **before10 PASS/8 FAIL/4 ERROR →22 PASS**.
The original8 names/assertions remain; fixtures now include the required valid
summary fields. Added14 schema/process cases. [Before](runner-before.log),
[after](runner-after.log). [15 retained real process invocations](runner-schema-results.json)
include all-pass and14 invalid cases, each retaining all36 planned mocked
workload outcomes and returning0/1 correctly. They are not540 SDK executions.
Three diagnostic bookkeeping checks test mixed sanitizer/stdout parsing and an
actual compiler-shim failure that retains all24 planned cases as NOT RUN.
Full Python **137/137 PASS** = previous120+14+3; [log](python-final.log).

## Prospective protocols and every execution

The runner writes plans before builds: one repetition per profile/case, per-case
35s cap (standalone lifetime15s), campaign600s/512MiB. Same CPU1/OTHER0 for these
optional middleware diagnostics; this is not a changed Host control FIFO profile
or a performance acceptance workload. Netns/veth uses unprivileged user namespaces,
multicast off, UDP reliable KEEP_ALL/resources8. Ingress/result deques are bounded8.
Every payload uses the real owner codec with original epoch/token/source,
exclusive20ms envelope and30ms inner request expiry. No wall time is virtualized.
Echoed packets are diagnostic results, **not** control ACK/Actual or run permission.
The diagnostic never creates a controller or opens its control gate.

| Cohort / reason fixed before execution | Runs | Normal | ASan/UBSan | TSan |
| --- | ---: | --- | --- | --- |
| v6 initial: bucket plus normal/peer-stop/peer-kill/restart/callback-delete/overflow/partial |24|6 PASS/2 FAIL|6 PASS/2 FAIL|8 FAIL,58 warnings|
| v7: reduced intrusive observer; separately coordinated restart instead of stopping consumption during incoming traffic |6|2 PASS|1 PASS/1 FAIL|2 FAIL,18 warnings|
| v8: real Proxy/lease/mutex identity + WHC scope experiment |6|2 PASS|2 PASS|2 FAIL,7 warnings|
| v9 final: regression after route checks and bookkeeping changes, same lifetime criteria |6|2 PASS|2 PASS|2 FAIL,15 warnings|

These are **42 runtime attempts:23 PASS/19 FAIL**, not a clean qualification.
[Per-run CSV](results.csv), [full raw archive](raw.tar.gz), [analysis](analysis.json).
Five earlier compile/setup attempts v1–v5 never reached runtime; their logs and
NOT RUN notes remain. Causes were missing/private C headers, POSIX feature macro,
GCC optional diagnostic and a binary/output-directory name collision. They are
not SDK runtime failures and are not silently removed as successful retries.
Their input hashes/commands/compiler logs remain, but complete pre-correction
source snapshots for v1–v5 were not captured. Exact source snapshots start at v6;
replayability of those early compile failures is therefore limited.
The v6 TSan bucket oracle was initially unparsed because stderr preceded stdout;
the parser now finds JSON after warnings, without changing its exit66/FAIL.

Normal and ASan v6 normal-all60 failed at original20ms expiry; no deadline was
extended. Reduced-observer v7 normal passed, but ASan normal still missed the
all60 oracle. Therefore observer overhead alone is **not an established complete
cause**. Packet input/receive/original deadline data are in [CSV](packets.csv).
The raw restart close timed out in all3 v6 builds. v7 uses explicit sender
quiescence→150ms drain grace→old peer close→trusted local epoch43 preparation.
The grace does not renew any command. Its contract passes functionally in all3
builds; TSan remains FAIL. New43 rejects the original saved42 packet as old/stale,
accepts fresh43, and still has no normal control authority. This coordinated
contract is narrower than successful deletion under an uncooperative full stream.

The unchanged v6 normal executable was observed once under parent GDB (6s
interrupt,32s outer diagnostic cap). `dds_reader_close` waited for GC; recv was
in `remote_on_delivery_failure_fastpath` retry/sleep on a full reliable RHC;
GC waited for awake-thread progress. The pinned source connects this wait cycle:
`ddsi_delete_reader` queues GC; connections disappear in the GC callback, while
full-cache redelivery retains an awake reader. This establishes the observed
wait locations, not proof that every public-delete interleaving deadlocks.
GDB perturbs scheduling; its extra failure is separate from42 runs.

A further single bookkeeping probe attempted the same timeout without GDB.
It completed (driver0), so the post-check expecting that timeout failed (exit1).
[Original result](cleanup-regression.json), [raw](cleanup-regression.tar.gz).
This **did not exercise** the intended timeout-cleanup branch; no retry occurred.
The old timeout is not resolved by this nonreproduction. Current code retains
all launched process exit codes on errors, and preserves NOT RUN entries on
build failure/time/storage stop. The SDK timeout path's new cleanup branch still
needs a deterministic injected-error check; it is not called verified by this probe.

## What the lifetime evidence establishes

- **Bucket:** real entity-index growth128 Writers replaces the original bucket.
  An SDK awake thread retains/reads its original address while performing actual
  lookups. Real `gc_buckets_cb` frees it after quiescence. Normal/ASan pass; TSan
  reports publication and old-bucket free/read. This extends the prior Writer
  scope study to actual hash storage; no replacement GC model is used.
- **WHC:** opt-in `dds_writer_lifetime --whc` retains the actual Writer-owned WHC
  through index unlink, uses its real `get_state` operation while awake, and
  observes the real allocator free. Original Writer assertions/default mode remain.
  Real network writes expose nonempty WHC and AckNack traffic before teardown.
- **Proxy/lease/mutex:** the private-ABI inspector resolves a matched remote GUID,
  performs the pinned vendor hash lookup, locks the actual Proxy mutex and reads
  its participant and automatic lease. It records last **observed diagnostic**
  access and scope end. SDK allocation/free hooks plus loader maps connect the
  same addresses to constructor/GC frames. The hidden lookup is compiled from
  exact pinned `hopscotch.c` into the diagnostic with function-section GC; it is
  not a patched SDK or a production adapter configuration.

[Object records](objects.json) retain creation/free stack frames and42 observed
object intervals across v8/v9,14 per profile, with no missing allocation/free or
observed scope violation. These observations do not identify the last access by
**all SDK threads**. Mutex addresses are part of Proxy objects; a free timestamp
is not a separately measured mutex-destroy timestamp. Allocator timestamps denote
entry to free. Unwinding/finest logging can add load or synchronization, so TSan
warning absence in one run is not a safety proof.

The source-level awake/vtime argument for scoped bucket/WHC reclamation and
immutable GUID publication is narrower than complete SDK correctness. Remote
lease replacement, all callbacks, deferred AckNack lists and newly observed
TKMAP/other warnings remain individually unqualified. [All warning families](warnings.json)
retain98 occurrences across the4 cohorts; occurrences are not98 independent bugs.
The new traffic reproduces real publication/lease/GC paths beyond scalar helpers.
ASan clean observations do not close any unexplained TSan warning.

## Remaining gate and next action

[Gate](gate.json): communication/close/restart requirements are only partially
met; unexplained memory paths remain. Exact diagnostic SDK/library/build identity
is recorded, but a future actual adapter configuration is NOT BUILT/NOT RUN.
**Do not enable or start the regular control adapter.** Investigate/validate a
supported full-RHC close solution and the remaining lease/proxy/TKMAP paths before
that gate. The source under review still contains the retry logic; no matching
accepted upstream fix was established. The separately found
[upstream2374](https://github.com/eclipse-cyclonedds/cyclonedds/issues/2374)
concerns callback/recursive-lock reports, not an established match for this wait.
No unsupported patch or stronger atomic was applied as a shortcut.

After the user confirmed a Daybreak authentication requirement, additional
investigation was stopped; this is an operational access constraint, not a new
M4 acceptance rule. Completed local results remain preserved. No authentication
workaround or access/model setting change was attempted.

## Reproduction

```bash
python3 -m unittest discover -s tests/unit -p '*_test.py'
python3 tests/integration/middleware/check_dds_lifecycle.py build/m5-dds-new-cohort
python3 tests/integration/middleware/check_dds_lifecycle.py --followup build/m5-dds-new-followup
python3 tests/integration/middleware/check_dds_lifecycle.py --lifetimes build/m5-dds-new-lifetimes
```

Select **new** output directories. Current default and old v6 differ by the
recorded inspector/bookkeeping improvements: replay v6/v7 from their exact
archived `sources/` in a separate checkout, not by relabelling a current run.
The archive includes exact commands, plans, source hashes/snapshots, binary hashes,
loader maps, raw allocation/packet/WHC/SDK/sanitizer logs and GDB stacks. Local
roots are `build/m5-dds-qualification` and the preceding pinned SDK installs;
prepare the same dependencies using their previous protocol, not a new SDK.
Hold `build/.m4-exclusive.lock`; build before testing; do not run timing alongside
builds/other tests. No additional root collection, FIFO kernel cohort, Target,
whole-system or learner review occurred. Reproduction of work that the service
requires Daybreak approval for must wait for that authorization.
