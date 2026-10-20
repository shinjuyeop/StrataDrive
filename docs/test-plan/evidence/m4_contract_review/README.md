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
