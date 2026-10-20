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
