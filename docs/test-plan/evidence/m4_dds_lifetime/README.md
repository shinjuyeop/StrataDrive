# DDS lifetime investigation and M4 decision evidence

2026-10-20; baseline `c52445a`, runner correction `1677f85`.
**DDS sanitizer acceptance remains FAIL/OPEN; M4 NOT CLOSED.**
No runtime/scheduler/authority/SDK algorithm or default dependency change.
The new SDK build is an isolated ASan/UBSan build of the same11.0.1 source,
not an upgrade. [Metadata](metadata.json), [source/loader hashes](provenance.json),
[raw commands/logs/cache](raw.tar.gz), [artifact audit](audit.json),
[Host acceptance proposal](../../../m4_host_acceptance_review.md).

## What was actually corrected

`tests/integration/middleware/run_probe.py` ignored its child's FAIL return and
the aggregate main returned0 after failed cases. It also did not make sanitizer
warnings an explicit failure. Before correction, the new8 process-level tests
produce **2 PASS/5 FAIL/1 ERROR**; afterward **8/8 PASS**. Full Python is
**120/120** (previous112+8), not additional C++ tests.
[Before](runner-before.log), [after](runner-after.log), [full suite](python-final.log).

The child now persists its verdict and returns1 on FAIL/warning/exception. The
aggregate persists each of the original36 planned cases, continues after missing
or malformed results/launch failure/timeout, checks stderr and process exit, and
returns nonzero if any case fails. A30s diagnostic process cap kills its owned
process group; this is not a changed command/network deadline. The real timeout
unit case retains pre-timeout output and returns124. All-pass still returns0.
The fixed36-run protocol's previous raw results were rechecked offline:
[36 remain PASS](baseline36-recheck.json); no SDK workload was rerun for that audit.

Actual original two-process wrapper normal/overflow once each with the existing
fully instrumented TSan SDK now returns **1/1**,2/4 warnings, probe exits66/66
in each case. Normal sends100 and accepts100/rejects3/echoes103 correctly;
sanitizer failure is retained. New full ASan/UBSan SDK + instrumented wrapper
normal/overflow once each returns **0/0,2 PASS**, no sanitizer diagnostics.
Overflow retains86 accepted/17 rejected and13 channel failures; this is the
intended overflow oracle. [TSan](wrapper-results.json), [ASan](wrapper-asan-results.json).
These four runs validate exit handling and exercise network teardown under ASan;
they are not a fresh36-run middleware/timing acceptance cohort.

## Existing warnings grouped by ownership path

The official-option4-run cohort had29 warnings, not29 independently established
defects. [Grouping](warning-groups.json) retains each original file/index/summary
and log SHA. These are analysis families, not a claim of one cause per family.

| Family/count | Creation/owner and readers | Lifetime/ordering and destruction | Present finding |
| --- | --- | --- | --- |
| PUB-BUCKET /3 | `ddsrt_chh_resize` allocates/initializes a bucket array; receive/event/API threads lookup through entity index | Full vendor fence then pointer publication; old array is separately queued for GC | `no_sanitize` loads/stores hide publication from TSan. No claim that every compiler/interleaving is proven safe |
| GC-BUCKET /7 | Entity index owns hash storage; awake lookup threads may retain the previous array | `gc_buckets` snapshots awake-thread vtimes after replacement; `gc_buckets_cb` frees after progress | Actual bucket-array reclamation not isolated by the Writer test; remains OPEN |
| GC-WRITER-WHC /4 | `ddsi_new_writer` creates Writer; WHC belongs to Writer; receive `handle_AckNack` may use both | Remove GUID, snapshot awake threads, GC `gc_delete_writer` frees WHC then entity/mutex and Writer | Actual Writer/mutex boundary exercised below; AckNack/WHC deferred-list interleavings remain separate |
| PUB-REMOTE-OBJECT /15 | Discovery initializes proxy entities/leases; receive Heartbeat/AckNack reads GUID, parent, lease and entity mutex | Hash publication provides visibility; removal and deferred GC protect later destruction | Original mutex stacks compare lock against allocation/publication, not a recorded destroy. New Writer destroy warning must not be substituted for this family |

The15 remote-object warnings include GUID7, parent/Heartbeat2, lease4 and mutex
publication2. Source functions/lines and exact source hashes are in the grouping
and provenance. Proxy endpoint refs and lease-renewal ownership must be reviewed
with their own callback/reclamation paths; passing local Writer ASan cannot
resolve them. The wrapper holds DDS handles on one application thread, supplies
fixed-size sample storage and calls `dds_delete(participant)` after its loop.
Its source does not expose internal raw entity pointers. New direct test code
bypasses that wrapper and still reproduces actual GC read/free and mutex-destroy
warnings, isolating those boundaries from wrapper call order.

## Actual Writer lifetime experiment

`tests/integration/middleware/dds_writer_lifetime.c` uses the exact11.0.1 private
ABI for diagnostics only. It obtains the real Writer from the entity index in
an SDK awake scope, holds that lookup result while another thread calls
`dds_delete`, reads the immutable GUID and locks/unlocks its real entity mutex,
then ends the scope. The public allocator hook observes entry to the actual
Writer free. It keeps libc allocation behavior and records only that address.
This hook's `free_ns` is entry to free, not completion or a production deadline.

The protocol was fixed before execution in [plan](plan.json). The first harness
waited for `dds_delete` to return before allowing reader progress. All12 initial
attempts hit a2s assertion: **harness setup failures**, retained in
[v1 results](harness-v1-results.json). `dds_writer_close` explicitly waits for
the GC status callback, so that harness created a circular wait. It did not
reproduce an SDK deadlock. The initial source-start hash was not recorded;
original executable hashes/logs/commands remain in the archive.

[v2](harness-v2-plan.json) corrects the harness by using a separate deleter and
waiting for GUID unlink rather than synchronous API return. It repeats the
predeclared three runs per condition in new directories; v1 is not dropped from
the record. Observation flags use relaxed atomics; main waits for free before
joining the reader, avoiding an artificial join→GC happens-before edge.

| v2 condition | Executions | Actual result |
| --- | ---: | --- |
| Correct scope, normal SDK | 3 | 3 PASS/exit0; free after last access/scope end |
| Correct scope, full ASan/UBSan SDK | 3 | 3 PASS/exit0; no memory/undefined/leak diagnostic |
| Correct scope, existing full TSan SDK | 3 | **3 FAIL/exit66**,2 warnings each: real mutex destroy/read and Writer free/read |
| Deliberately retain pointer after asleep, ASan | 3 | 3 positive controls detect heap-use-after-free/exit1; not middleware PASS |

[All12 raw outcomes](lifetime-results.json), [numeric lifetime CSV](lifetime.csv),
[9 correct-scope intervals](lifetime.svg) (rendered by `python3 plot_lifetime.py`).
The chart excludes the three UAF controls that abort before reporting intervals;
TSan warning reporting changes GC timing, so these are not performance samples.
The experimental driver's exit0 means all predeclared diagnostic observations
occurred, including expected sanitizer findings; it is not an SDK PASS. The
per-run `sanitizer_clean=false`/exit66 are preserved as three sanitizer failures.

### Narrow lifetime argument and its limits

1. The reader publishes an awake vtime before lookup and stays awake for every
   GUID/mutex access. The deleter begins only after the reader has obtained the
   object; it removes the index entry before gathering GC dependencies.
2. `ddsi_gcreq_new` captures this awake reader's vtime. `threads_vtime_check`
   cannot release that dependency until vtime advances or the thread leaves the
   domain. The reader's final release fence precedes the asleep/vtime update.
3. GC runs the deletion callback only after that progress check. Writer teardown
   frees WHC, invokes the status callback, destroys entity mutex state and frees
   Writer. `dds_delete` may return after the status callback but before the tail
   of this GC callback; domain teardown drains and joins GC before freeing the
   domain. It is not correct to use that earlier API return as the free timestamp.
4. In all9 correct-scope observations, final access precedes scope end and actual
   allocator entry; no free occurs while held. Breaking the asleep rule produces
   a real ASan UAF in all3 controls, so the memory detector covers the target path.

This connects creation→index lookup→unlink→quiescence→mutex/free for one real
object, beyond a scalar handoff. It supports a missing TSan synchronization edge
for these scoped Writer warnings under the vendor's x86/GCC model. Volatile
helpers and architecture fences do not supply TSan's standard atomic HB events.
It is not a language-memory-model proof of the whole SDK, an ARM64 qualification,
or proof of the other families. **No broad false-positive closure, suppression,
Tsan annotation, stronger-atomic rewrite or SDK patch was applied.**

## Upstream disposition and reproducibility

The [maintainer's GC explanation](https://github.com/eclipse-cyclonedds/cyclonedds/issues/1417#issuecomment-1256352842)
describes remove→awake-vtime snapshot→deferred freeing. In
[issue2039](https://github.com/eclipse-cyclonedds/cyclonedds/issues/2039#issuecomment-2196511627)
the maintainer discusses GC/hash lookup TSan visibility and warns that broad
suppressions can conceal real races. We did not adopt those suppressions.
[PR2162](https://github.com/eclipse-cyclonedds/cyclonedds/pull/2162) is closed,
**not merged**; its wholesale seq_cst conversion and other changes are not a
supported fix to apply here. The official latest release queried remains
[11.0.1/e54e991](https://github.com/eclipse-cyclonedds/cyclonedds/releases/tag/11.0.1).
[Upstream metadata](upstream-review.json) records the inspected statuses. No
matching accepted lifetime fix was established, so the dependency remains pinned.

Extract `raw.tar.gz` into a new directory. It contains `build-plan.json`,
`v2/build-plan.json`, all process commands, original logs, scripts, generated IDL
input, SDK CMake cache/compiler commands and loader/library hashes. The scripts
use this workspace's absolute paths: choose a new output root consistently;
never overwrite an existing cohort. SDK inputs are the same pinned source/install
from the [preceding protocol](../../m4_middleware_probe_protocol_v2.md).
The build sequence instruments a new isolated SDK with `SANITIZER=address,undefined`,
then compiles only the optional probes. The existing normal/TSan installs and
production C++ binaries are reused unchanged. Hold `build/.m4-exclusive.lock`
and run builds before experiments. Exact15s lifetime/30s wrapper caps and settings
are recorded per run; use `setarch x86_64 -R` for these TSan runs, no global ASLR change.

```bash
python3 -m unittest discover -s tests/unit -p '*_test.py'
# 120 PASS; includes real process exit and timeout bookkeeping, not36 SDK runs.
```

[Source/binary reuse](source-reuse.json) confirms all six current normal/ASan/TSan
runtime/test binaries match `97afb35`, and production directories/CMake have no
changes through the reviewed HEAD. Existing48-run results are reused under their
original identity, not relabelled as new timing. [Matched Host cases](host-comparison.csv).
No FIFO recollection, native40 repetition, C++973 full regression, Target/system
execution or M5 implementation occurred in this follow-up. DDS GC-BUCKET,
remote-object publication and full WHC/receive lifetime still block unrestricted
DDS acceptance; the explicit limited-Host proposal does not silently waive them.
