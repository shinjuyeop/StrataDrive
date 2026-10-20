# M4 remote contract review follow-up

Baseline: `4a399af`, clean worktree. Original 948-test evidence, timing failures,
TSan failures and M4 NOT CLOSED are retained in `../m4_followup/`.
These are Host component tests; system/Target NOT RUN and learner review pending.

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
