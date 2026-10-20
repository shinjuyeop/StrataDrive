# M4 remote contract review follow-up

Baseline: `4a399af`, clean worktree. Original 948-test evidence, timing failures,
TSan failures and M4 NOT CLOSED are retained in `../m4_followup/`.
These are Host component tests; system/Target NOT RUN and learner review pending.

## Latest completed boundary (2026-10-20)

Current implementation/test source: **1989477d28cc3c170ebb454325b43abd1d7662c6**.
Source SHA256: `406544adfcf04bf5c36fec93cb00cde4ae868d11884bee2f37e9cf224a79b8fc`
(the existing runner's source directory fingerprint, not the documentation commit).
Linux6.8.0-138-generic/x86_64, GCC11.4.0, CMake4.3.2, Python3.10.12,
16 allowed CPUs0–15. [Environment constraints](environment-limits.json) retain
RT priority limit20, perf_event_paranoid4, tracefs EACCES, absent cargo/rustc.
`project_status.md` remains the current-state authority.

| Execution / source | Actual result | Evidence |
| --- | --- | --- |
| First whole run /57457e6 | Normal962 PASS/1 FAIL of963; sanitizer NOT RUN (fail-fast) | `expiry-observation/` |
| Corrected contracts /c4195a6 | Normal963/963, ASan/UBSan963/963; boundary TSan64/64 | `correction-boundary/verification.tar.gz`, metadata/results/JUnit |
| Trace addition /f895dc6 | Normal964/964, ASan/UBSan964/964; separate fixed40 diagnostic40/40 | `trace-boundary/verification.tar.gz`, `native-diagnostic/` |
| Final whole regression /1989477 | **Normal966/966, ASan/UBSan966/966**; unit798/logical159/wall9 | [results](final/results.json), [test names and verdicts](final/tests.csv), `final/verification.tar.gz` |
| Final changed-boundary TSan /1989477 | **67/67 PASS**, runtime.wall **9/9 PASS**, warnings0 | [boundary](tsan/boundary.xml), [wall](tsan/wall.xml), `tsan/raw.tar.gz` |
| Final guard timing /1989477 | **41 PASS/7 FAIL/0 BLOCKED of48**, FIFO23/24, all setup/load/grid/growth controls48/48 | [all48](final/timing-results.csv), [owner distributions](final/owner-timing.csv), `timing/` |
| Setup smoke /1989477 | OTHER quiet1 + FIFO quiet1 PASS; separate from48 | `timing/smoke-results.json`, `timing/smoke-raw.tar.gz` |
| Static analysis /1989477 | Changed production4 files clang-analyzer + cppcheck PASS | `static/results.json` and exact logs |

The original948 names/assertions remain; new18 = old-Epoch3 + envelope/integration7
+ ACK5 + trace equivalence1 + logical result-delay2. [86 component mappings](final/component_results.csv)
link requirement → implementation → actual GTest → oracle → both-build verdict.
Runtime fault artifacts33 per build and durable rejoin CLI both pass.
[37 logical physical CSV hashes](physical-equivalence.json) equal the5eb1b3b baseline;
this is not wall-time equivalence. Current [normal response](final/logical-normal.csv),
[normal plot](final/logical-normal.svg), [normal Stop](final/logical-normal-stop.csv),
[partial failure](final/logical-partial-front.csv), [Drive stop](final/drive-stop.svg)
and [overflow/rejoin](final/overflow-rejoin.svg) come from the new source.

Original948 results, d7115ff native8/9, wrapper TSan4 FAIL/SDK-rebuilt DDS2 FAIL
and timing12fc4a5(41/7),603fe24(42/6),77d411c(42/6) remain separate histories.
No old timing is attributed to1989477. **M4 NOT CLOSED; M5 control adapter not started.**

## Issue 1 — old Epoch negative reply

The existing public test requires a negative response, so this correction retains
that compatibility instead of silently discarding. Epoch/token/operation are copied
from the original request. The old-Epoch branch runs before current credit polling;
Zone already ignores non-current Epoch results before touching pending state.

New parameterized regression: `FrameArmStop/RemoteOldRequestTest.RejoinedLeafReplyCannotPoisonCurrentZonePendingArm/{0,1,2}`.
Real Leaf INIT 42 → protect → INIT 43, old 42 Frame/Arm/Stop, current Zone 43 pending
arm, duplicate/delayed negative reply, actual current-session completion and negative
Frame protection. Input histories, gate, pending completion and received commands
are checked. Baseline + new tests: **0/3 PASS**; correction: **22/22 PASS** selected
existing/new tests (3 new). Original names/assertions unchanged.

```sh
cmake --build build/m4-readiness --target remote_leaf_test async_owner_test -j4
build/m4-readiness/remote_leaf_test --gtest_filter='FrameArmStop/*'
ctest --test-dir build/m4-readiness -R 'RemoteLeafTest|RemoteOldRequestTest|AsyncZoneOwner|AsyncOwnerTest' --output-on-failure
```

`issue1/before.{log,xml}` and `after.{log,xml}` are actual pre/post-fix output.

## Issue 2 — delivery envelope versus inner validity

Baseline for correction: `7396b2d`. New logical integration's first three tests
failed **0/3** before correction: initial real Power/permission envelopes were
49.800001ms, rejected before reaching arm. The actual producer is AsyncZoneOwner;
all five Leaf endpoints have private gates/queues. Same canonical codec in both
directions preserves all bytes, parent/command/stop context and original Actual.

After correction the new seven tests and existing selected tests pass **63/63**.
This includes exact exclusive expiry, uint64 overflow bounds, actual Stop/HV off,
Power/permission/Arm/Stop late rejection and old replies while Stop is pending.
A draft added assertion incorrectly required a parent even for safe Inhibit;
it was corrected to the existing AllowNormal/NormalPath authority contract.
No baseline test names or assertions were changed.

```sh
cmake --build build/m4-readiness --target remote_leaf_test async_owner_test m4_async_runtime_test -j4
ctest --test-dir build/m4-readiness -R 'Remote|AsyncZoneOwner|AsyncOwnerTest|M4AsyncRuntime' --output-on-failure
```

`issue2/before.xml` and `after.xml` retain actual results. Normal/ASan full regression
and new-source timing are performed at the completed correction boundary, not inferred
from prior commits' cohorts.

## Issue 3 — interleaved protection identities

Baseline implementation `9e96182`, final five regressions: **1 PASS/4 FAIL**.
After correction: **5/5 PASS** and selected existing/new regression **68/68 PASS**.
`issue3/before-final.xml` was run with the original cpp/hpp restored temporarily
and the final tests; the fixed implementation was restored and rebuilt for
`after-final.xml`. The draft wrong-route test was corrected to assert codec
rejection directly rather than treating that expected encoder rejection as a
fixture error. All original 948 assertions remain unchanged.

Issuer/Epoch/token records are bounded to8 per issuer and retained until new INIT,
including expired identity tombstones. No monotonic-token assumption or overwrite.
At capacity protection remains selected but no new ACK is synthesized. Duplicate
ACK keeps first selection/request bytes; altered token contents and expired replay
are rejected. Central/assigned Zone records and new-Epoch reset are tested.

```sh
cmake --build build/m4-readiness --target remote_leaf_test -j4
build/m4-readiness/remote_leaf_test --gtest_filter='RemoteLeafTest.Protection*:RemoteLeafTest.ExpiredProtection*:RemoteLeafTest.FullProtection*'
```

## Whole-regression finding — accepted command expiry observation

First full run at `57457e6`: **normal 962 PASS/1 FAIL out of963**. Existing
`M4FaultRuntime.AcceptedCommandExpiresAtItsOriginalContextDeadline` detected that
`valid-input.deadline_ns` still used the now-shorter transport envelope rather than
the accepted command's original context expiry. No control condition was relaxed:
accepted-input observation now records inner authority expiry; send/delivery fault
observations continue to record envelope expiry. Existing assertion passes unchanged
(1/1 focused). The fail-fast runner did not start ASan/UBSan in this first attempt;
that scope is NOT RUN for57457e6. A fresh full run follows this correction.

## Corrected contract boundary

`c4195a6`: normal **963/963**, ASan/UBSan **963/963**, changed-boundary TSan
**64/64** (Remote/PeerFixture/AsyncOwner/AsyncZone). Original948 names remain;
15 added tests. Unit798 / integration.logical156 / runtime.wall9. Existing runtime
fault/recovery artifacts33 per build; durable rejoin CLI both PASS. First962/963
normal attempt remains separate. See `correction-boundary/` metadata/results/JUnit;
raw `build/m4-contract-corrected/`, exported `build/m4-contract-corrected-evidence/`.

```sh
python3 tests/integration/runtime/check_m4_faults.py --raw-dir build/m4-contract-corrected --output build/m4-contract-corrected-evidence
cmake -S . -B build/m4-tsan -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_TSAN=ON
cmake --build build/m4-tsan --target remote_leaf_test remote_contract_test async_owner_test -j4
setarch x86_64 -R ctest --test-dir build/m4-tsan -R 'Remote|PeerFixture|AsyncZoneOwner|AsyncOwnerTest' --output-on-failure
```

## Native diagnostic observation

`TransportTrace` is an optional single-owner port. Each owner logs into its own
preallocated16384-row sink; storage is read only after join, overflow is reported.
Disabled trace does not decode CAN or acquire additional diagnostic timestamps.
`trace-transport` CLI / test `STRATADRIVE_M4_TRANSPORT_TRACE=1` opts in. Rows correlate
Epoch/token, original root and CAN source, command expiry, first sent/envelope bound,
Zone dispatch/completion and Central receipt. Leaf completion means controller
handling, not a fabricated physical response; existing physical CSV remains separate.
A new logical test compares complete physical response with trace off/on and follows
each actual command transaction. Native diagnostics use the fixed separate20+20
protocol and do not replace the48-run guard cohort or historical TSan failure.

## Native no-reproduction and distinct logical causal probes

Fixed native cohort at `f895dc6`: normal20/20 and TSan20/20 PASS, settings40/40,
full trace40/40, race warnings0. Raw `build/m4-contract-delivery-cohort/`.
This does **not** resolve the original d7115ff CommandDelivery incident.

Two prospective logical conditions distinguish failure paths using actual owners:

- Both Command TX results delayed12ms: original Rear applied command expires at
  elapsed1011.000001ms; its next service1011.2ms protects. Front result returns
 1017.4ms, while the new command remains live until1031.000001ms, but the closed
  gate correctly rejects Rear enqueue. First hypothesis expected a busy-submit
  fault and failed; `causal/overlap-hypothesis.xml` preserves that incorrect
  hypothesis. The regression now checks the observed original-authority path.
- Rear Command TX result only delayed19.8ms: root1001ms → CAN source1005.2ms →
  Rear enqueue1005.4ms → Zone/Leaf completion1005.6ms → next allocation1025.2ms
  finds the previous transaction pending → CommandDelivery protection. Its
  envelope deadline is1025.4ms and inner expiry1031.000001ms. Result arrival at
  exactly1025.4ms is subsequently rejected by exclusive expiry. A draft assertion
  incorrectly assumed the **final** transport fault would remain None after that
  late reply; `causal/causal-draft.xml` retains the failure. The final test asserts
  absence of transport rejection **before** the busy-submit event, preserving the
  later rejection as distinct behavior. Both final logical tests pass unchanged
  control logic/limits; this demonstrates a delay-only path, not a memory race or
  a confirmed reconstruction of the historical untraced native failure.

New logical regressions bring the full test set to966 (original948 + contracts15
+ trace equivalence1 + causal2), traceability86. Final full normal/ASan·UBSan results
are recorded above; prior964 results retain their own source identity.

The native40 cohort's [metadata](native-diagnostic/metadata.json) pins **f895dc6**
and digest `e7173e045e4c4be29470734717544ed439c196ae6971529f441d854b0aa754de`.
All40 have correct OTHER/0/affinity, full trace, zero warning and no trace overflow.
The [per-trial latency CSV](native-diagnostic/latencies.csv) and
[plot](native-diagnostic/latencies.svg) show maximum command enqueue→accepted result
of0.440508ms normal/0.465624ms TSan; maximum Zone queue delay0.240683/0.255778ms,
result enqueue→Central receive0.227272/0.177041ms. These measured samples are not
WCET or proof that TSan cost caused the historical failure.
All40 original logs/JUnit/physical/event/transport/transaction chains are in
`native-diagnostic/raw.tar.gz`; trial01 for each profile is also directly browsable.

The two [logical timelines](causal/timeline.csv) and [pending-result plot](causal/timeline.svg)
use the final1989477 owners with deterministic logical time. Initial clock is1s;
the prose times above are elapsed time, CSV times are absolute nanoseconds.
`causal/raw.tar.gz` contains control and both delayed-result conditions, including
physical outputs; `causal/causal-final.xml` records the focused2/2 PASS.
These tests show correct protection under two deliberate delays without a data race;
they do not establish whether the old native incident was caused by scheduling,
insufficient normal settlement margin, or a different concurrency/contract problem.
The original trace is absent, so that exact incident cannot be reconstructed.
The next contract review must cover sequential Front→Rear completion versus the
next20ms allocation and old command expiry, without simply increasing timeouts.

## New-source timing: all48 and the additional FIFO failure

The [fixed protocol](../../m4_contract_review_protocol.md) was selected before execution.
Same48-run conditions: normal/ASan, CPUs0/1, OTHER/FIFO, quiet or7ms/10ms contention,
normal/Drive pause/Monitor6ms overrun, three repetitions,2.54s duration,
2ms opportunities/4ms completion deadlines,1211 slots per owner (12110/run).
Transport trace OFF, no parallel build/test. The [cohort](timing/cohort.json) and
metadata preserve all commands, actual scheduler/CPU/load/grid/allocation controls.
The separate two setup smokes do not replace failed cohort members.

Six loaded OTHER normal runs fail with314/271/276 normal and259/289/285 sanitized
missed opportunities; completed body maxima0.021–0.075ms are below4ms.
The seventh failure is **normal-3-fifo-0-monitor-overrun**:

| Observation | Actual value / interpretation |
| --- | --- |
| Unexpected missing execution | Front and Rear slot281, release662ms, deadline666ms |
| Independent Monitor detects | 666.004077ms; deadline +0.004077ms |
| Physical applies override | 666.009677ms; detection +0.005600ms |
| Central reports fault | 667.608042ms; first-active0, no normal command batches |
| Planned Monitor injection | Starts1200.002597ms; Physical detects1204.003144ms; returns1206.004918ms |
| Overall run | FAIL,6 deadline misses/5 skipped; actual FIFO/CPU setup correct |

The planned injection happened **after** the unexpected early fault, so detecting
it does not make the run PASS. [Fourteen neighboring execution rows](timing/fifo-new-window.csv)
show Rear slot280 CPU1.107494ms and wall1.117555ms; next observed slot282 starts
2.151891ms after its requested wake (Front2.265989ms). The common release grid is
correct; the prior fixed1.528ms phase issue is not present. Extra CPU/wake delay
is observed, but timer/kernel/IRQ/preemption/host competition attribution is not
established without the blocked trace/perf capture. This is a normal-build FIFO
failure, not a TSan-only effect.

FIFO therefore passes **23/24** (normal11/12, sanitized12/12). Among the23 passing
intentional-fault trials, deadline→detection is0.003316–0.118481ms and detection→
physical override0.000989–0.986818ms. Failed runs stay in the48-run denominator.
All7 failures' full raw files, three passing FIFO representatives, all48 settings/
result JSON and cohort metadata are in `timing/representatives-and-all-failures.tar.gz`.
The complete uncompressed48 raw directories remain at `build/m4-contract-timing/`.
No scheduling/deadline acceptance threshold was relaxed.

## Middleware and remaining conditions

[Preserved SDK stack/source analysis](middleware/analysis.md) and
[version URLs/SHA256](middleware/sources.json) distinguish wrapper-owned memory
from DDS bucket GC/read and Rust task handoff. DDS11.0.1's vendor atomic helpers
explicitly exclude TSan instrumentation even in the prior SDK-wide rebuild.
This is a concrete visibility gap, not proof of a false positive or safe lifetime.
Zenoh release-level source cannot attest the saved binary's exact lock/build flags;
Rust standard library/dependency instrumentation and symbols remain unavailable.
No SDK warnings were suppressed, no SDK synchronization algorithm was patched,
and no new SDK runtime cohort was executed.

OPEN-M4-TIM-01, OPEN-M4-TSAN-01, OPEN-M4-MWTSAN-01 and existing M3 exceptions remain.
Host IO/FIFO-only technical acceptance is still a proposal: the new early FIFO
miss must be explained and retested under fixed conditions; normal pending-result
settlement and SDK sanitizer evidence also need review. Requested next conditions
are same-Host timer/wakeup/switch/TID/IRQ capture permission, supported DDS atomic/
reclamation instrumentation, and compatible instrumented Rust/toolchain provenance.
No support profile is narrowed automatically. [Exit review](../../../m4_exit_review.md)
keeps M4 NOT CLOSED and M5 not started.

NOT RUN in this follow-up: full966 TSan, new middleware runtime tests, full Rust TSan,
kernel trace/perf, vCAN re-execution, Release-without-tests rebuild, Target/PREEMPT_RT,
full remote control deployment, system32 requirements/29 TC, learner direct reproduction.
Earlier successful executions of those limited scopes remain historical evidence.

## Reproduction and artifact integrity

Use a fresh output directory for every new execution. Existing runners reject or
fingerprint-check reuse; do not overwrite historical raw results. Build before timing
cohorts, with no parallel compile/test during measurement. The native40 cohort must
be rerun atf895dc6 in a separate checkout to reproduce that exact source identity;
running it at the latest source creates a distinct new cohort.

```sh
# Final whole regression (1989477 source; latest docs-only commit has the same digest)
python3 tests/integration/runtime/check_m4_faults.py \
  --raw-dir build/repro-contract-final --output build/repro-contract-evidence

# Changed concurrent boundaries and existing wall tests
cmake -S . -B build/m4-tsan -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_TSAN=ON
cmake --build build/m4-tsan -j4
STRATADRIVE_M4_RESULTS="$PWD/build/repro-contract-tsan" STRATADRIVE_M4_TRANSPORT_TRACE=1 \
  setarch x86_64 -R ctest --test-dir build/m4-tsan \
  -R 'Remote|PeerFixture|AsyncZoneOwner|AsyncOwnerTest|TransportTraceCorrelates|DelayedFrontResult|PendingRearResult' \
  --output-on-failure --output-junit "$PWD/build/repro-contract-tsan-boundary.xml"
STRATADRIVE_M4_RESULTS="$PWD/build/repro-contract-tsan" STRATADRIVE_M4_TRANSPORT_TRACE=1 \
  setarch x86_64 -R ctest --test-dir build/m4-tsan -L runtime.wall \
  --output-on-failure --output-junit "$PWD/build/repro-contract-tsan-wall.xml"

# Existing48-run protocol, transport trace OFF, fresh result directory
python3 tests/integration/runtime/check_m4_faults.py --reuse \
  --raw-dir build/repro-contract-final --output build/repro-contract-complete \
  --run-timing --timing-dir build/repro-contract-timing

# Fixed native20 + TSan20 diagnostic, at the source identity being investigated
cmake --build build/m4-readiness --target m4_async_runtime_test -j4
cmake --build build/m4-tsan --target m4_async_runtime_test -j4
python3 tests/integration/runtime/check_m4_delivery_trace.py build/repro-contract-delivery
```

`final/verification.tar.gz` retains whole-suite build/configure/CTest/JUnit and
durable CLI logs. `tsan/raw.tar.gz` retains final boundary/wall output and trace.
`correction-boundary/` and `trace-boundary/` retain earlier actual full-suite outputs.
`draft-attempts.tar.gz` preserves added-test fixture/draft failures separately from
the final pre-fix reproducers. No original assertion was weakened.
`SHA256SUMS` covers this evidence directory except itself; verify from this directory
with `sha256sum -c SHA256SUMS`. Archives have relative paths, no external symlinks.
The original source fingerprint is independent of artifact/archive checksums.
