# Fixed kernel campaign and sudo boundary

Review base `1a4afe5`. Application binary unchanged:
`4736b40e8b5b2b67c4cf603ff96a7b1516d619541fdb10a8de80ff01b8f76347`.
Current state is maintained in [project status](../../../project_status.md).
The [prospective protocol and exact sudo command](../../m4_kernel_capture.md)
fix OTHER1 + FIFO10 OFF/ON pairs, normal build, no retries.

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
