# Fixed kernel campaign and sudo boundary

Review base `1a4afe5`. Application binary unchanged:
`4736b40e8b5b2b67c4cf603ff96a7b1516d619541fdb10a8de80ff01b8f76347`.
Current state is maintained in [project status](../../../project-status.md).
The [prospective protocol and exact sudo command](../../../archive/m4-test-protocols.md#m4_kernel_capture)
fix OTHER1 + FIFO10 OFF/ON pairs, normal build, no retries.

Latest: the separate `d3e7f6d` campaign **213425 completed11/11 valid pairs**.
OTHER2 FAIL, FIFO20 PASS, no FIFO pre-injection deadline misses; historical
FIFO cause remains OPEN. [Full result, causal timeline and reproduction](completed_213425/README.md).
The preparation and212418 failure below are historical records, not replaced.

## Preparation actually executed

- `sudo -n true`: exit1, password required. [Environment](preparation/environment.json).
- Original agent user UID1000, OTHER0, affinity0–15, RTPRIO20/20.
- [sudo PAM configuration](preparation/pam-sudo.txt) invokes `pam_limits.so`;
  [limits configuration](preparation/user-limits.txt) grants20/20 specifically to
  alswoghd. Existing sudo workers recorded0/0. Selecting `Popen(user=1000)` changes
  credentials but does not reload that user's login limits. The observed lost
  budget crosses the sudo launch boundary; these files alone do not identify
  which sudo/PAM internal call reset it.
- New child-only setrlimit-before-setuid regression against old `1a4afe5`:
  [1 ERROR, missing restoration helper](preparation/before-child-limit-test.log).
  This is a code regression, not a privileged runtime reproduction.
- `python3 -m unittest discover -s tests/unit -p '*_test.py'`:
  [104/104 PASS](preparation/python.log), original97 names/assertions retained +7.
  Coverage includes limit/credential order, live ancestor checks, fixed denominator,
  budgets, collection failure/continue, prerequisite failure/NOT RUN, actual
  nonroot refusal exit2, existing marker error export/cleanup/interrupt tests.

## State

Latest root campaign, actual restored20/20 FIFO launch, marker headroom/error
path on tracefs: **NOT RUN at preparation** (password required). Existing valid
OTHER case and EBADF/dropped-event originals remain in
[prior evidence](../m4_kernel_valid/README.md). No new kernel cause or FIFO fix is
claimed. M4 NOT CLOSED; Target/system/learner state unchanged.

Actual child identity logging changes diagnostic Python only. No C++ runtime,
control timing, SDK algorithm, safety threshold, default scheduling or M5 change.
Existing973-per-build and48-run timing results remain results of their original
commits, not reruns of this tooling.

## Follow-up diagnostic validation

The offline campaign analyzer writes a **new output directory**, retaining raw
capture inputs. It uses actual `overrun-injected` events, not assumed1200ms, to
separate missed deadlines preceding injection from subsequent misses. A late
detection of a pre-injection expired slot remains unexpected.

```bash
python3 tools/m4_kernel_campaign_analysis.py \
  build/m4-kernel-fixed-<timestamp> build/m4-kernel-analysis-<timestamp>
```

Final Python [108/108 PASS](preparation/python-final.log) includes another4
regressions: pre-injection deadline grouping, absent injection, atomic epoch
file rename during budget scan, and conflict→STOPPED/all NOT RUN. The scan's
previous `is_file`/`stat` race is reproduced as
[1 ERROR before correction](preparation/before-rename-test.log). No privileged
capture failure is claimed for that synthetic case.

A separate original-user (no sudo, no kernel trace) smoke executed exactly two
workloads with the unchanged normal application binary. OTHER loaded FAIL:
273 missed/skipped opportunities. FIFO monitor-overrun PASS:4 missed/3 skipped,
deadline→detect0.003216ms, detect→physical override0.001157ms. Both identity and
setup controls PASS, actual child UID1000/capabilities0/RTPRIO20/20.
This verifies the new child identity logging and user-mode launch, **not** the
sudo restoration or fixed11-pair campaign. Complete results are preserved in
`user-smoke-raw.tar.gz` (local originals: `build/m4-kernel-user-smoke/`).

The new analyzer was also executed as an actual process against a fixture that
references the existing historical VALID OTHER pair and10 NOT RUN entries.
[Check/command](offline-fixture-check.json), [results](offline-fixture-results.json):
exit2 as required, historical pair remains valid,10 missing entries do not become
PASS, original kernel trace SHA256 unchanged. This creates no new kernel or FIFO
execution evidence. The original-user smoke and this offline fixture do not count
toward the prospective22 privileged workloads.

## First privileged fixed campaign: 2026-10-20 21:24:18

Source `cfeda3459cf446ed9f4f7b1f7de86e36da90b3ab`, captured digest
`5213dabc9850586ff77634b800102d5da9ad9f9e04b35003f83f973441e1d89e`.
The binary hash above is unchanged. User ran the documented360s command with
`--user-parent "$$"`; this was one planned11-pair campaign, not repeated until success.
See [original campaign](buffer_followup/original-campaign.json) and
[complete raw archive](buffer_followup/original-212418.tar.gz)
(local original `build/m4-kernel-fixed-20261020-212418/`).

- **2/22 workloads executed:** OTHER OFF FAIL180 misses/skips, ON FAIL320.
  Neither reached active operation. FIFO20 workloads are **NOT RUN** because the
  initial OTHER trace prerequisite failed. All11 planned entries are preserved.
- ON parsed753170 events with0 unparsed lines, but **CPU9 dropped1963 events**.
  Its requested256KiB ring recorded265192 bytes. Other15 CPU rings reported0
  drops/overruns. The kernel's allocated payload size can differ from requested
  KiB; the loss counter, not a byte-size estimate, establishes actual loss.
  [Per-CPU recorded usage and new allocation](buffer_followup/buffer-usage.csv).
- Both begin/end markers were stored, no EBADF/marker errors, trace was enabled
  before stop, text was not truncated. The instance was removed and global
  settings unchanged. This verifies the successful marker/cleanup path once;
  it does not prove the historical EBADF cause or the real marker-error path.
- Parent actually had RTPRIO20/20; root collector recorded0/0. Both workers and
  actual runtime/load children were UID1000/capabilities0/RTPRIO20/20.
  Setup/load/grid/growth/identity controls passed. Original OTHER0 and CPUs0/1
  were retained. **sudo budget restoration is now observed**, but actual FIFO
  launch through this campaign remains NOT RUN.
- The whole trace remains **INVALID** and11790 derived chains **UNTRUSTED**.
  CPU9 being outside owner CPUs does not justify ignoring its loss: cross-CPU
  wake sources are captured too. No causal timing result is accepted from it.

`collection_exit: 2` was therefore correct. The generic `analysis: pending`
message hid the already-known prerequisite failure; the console now reports
status, reason, pair status counts and per-mode analysis errors.
[New console formatter applied to the saved result](buffer_followup/console-after.json)
is an offline check, not a new privileged run.

The old non-owner256KiB allocation was insufficient in this observed window.
The correction assigns up to1MiB per background CPU from the existing64MiB
budget, retaining CPU0=16MiB, CPU1=32MiB and marker CPU2=2MiB. This16-CPU Host
requests63MiB total; other CPU counts are bounded and actual kernel allocation
is still checked before enabling capture. All CPUs/events stay traced, overwrite
stays disabled, all original workload/deadline/file/time/storage limits remain.
Buffer sufficiency under a fresh kernel run is **NOT RUN**, not assumed PASS.

Verification (diagnostic tools only, no application/runtime change):

- New regressions before correction: [41 tests,1 FAIL/2 ERROR](buffer_followup/before-python.log)
  (missing headroom, missing console formatter);38 PASS.
- After correction: [112/112 Python PASS](buffer_followup/after-python.log),
  previous108 +4. One existing allocation assertion changes256→1024 to reflect
  the new layout; integrity/safety assertions are retained, including a new
  background-CPU-loss→UNTRUSTED check.
- Actual offline analyzer process: **exit2**,11 entries,1 INVALID/10 NOT RUN,
  original file hashes all unchanged. [Command and checks](buffer_followup/reanalysis-check.json),
  [JSON](buffer_followup/reanalysis-results.json), [CSV](buffer_followup/reanalysis-summary.csv),
  [original file hashes](buffer_followup/original-sha256.json).
- Agent `sudo -n true` still exits1/password required. New root collection/FIFO
  runs are NOT RUN. C++/sanitizer/native40/timing48 are not repeated for this
  collector-only change and retain their original source/denominators.

Reproduce after extracting the archive under `build/` (use a new analysis output):

```bash
python3 -m unittest discover -s tests/unit -p '*_test.py'
python3 tools/m4_kernel_campaign_analysis.py \
  build/m4-kernel-fixed-20261020-212418 build/m4-kernel-212418-review
# Expected exit2; original trace loss must remain INVALID.
```

For the corrected collector, run the same [fixed sudo command](../../../archive/m4-test-protocols.md#m4_kernel_capture)
once into a new timestamped directory. It is a **separate campaign**, not a
replacement for these2 failed workloads/20 NOT RUN entries. M4 stays NOT CLOSED;
historical FIFO/native/DDS issues and Target/system/learner status remain open.
