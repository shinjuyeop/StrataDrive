# Host FIFO refresh correction — prospective protocol

2026-10-22; starting HEAD/origin/main e977366d2ecde16bfc3a825f1eea6ffd3a29f6c6;
fetched, clean tree, no intervening commits. User-approved scope: actual eight-role
Host functional SIL Central–Front SOME/IP. Required: Normal FIFO normal operation,
core loss/protection, orderly shutdown, new-Epoch rejoin. OTHER loaded timing is
preserved diagnostic evidence, not a gate for this limited integration. Memory/UB/
race reports remain failures; sanitizer wall time is judged separately. No Rear
implementation, SDK/OS change, new stress matrix or historical denominator rewrite.

Before modifying behavior:
- Add bounded allocation decision and first gateway cause observations, replay the
  saved normal pre-injection expiry timeline in a deterministic unit test. Record
  failed pre-fix assertion and exact grant/source/release/expiry inputs. One optional
  instrumented pre-fix Normal FIFO normal run (2540ms,20s cap) checks observations;
  no repetition for chance reproduction.
- Final Normal FIFO: normal quiet2, existing loaded2 (OTHER7ms busy/10ms on CPU1/2),
  command-loss1, owner-pause1, central-stop1, restart-live1. Fault cases require
  unprotected real normal control first. Same2540ms native guard; owner-pause at1200ms.
  Existing strict runner, original2ms opportunities/4ms deadlines, all real ACKs,
  original20ms envelopes and inner expiry retained. Missing/timeout/SDK errors fail.
- Final changed unit contracts plus full Normal and ASan/UBSan CTest once each if
  shared control is changed. ASan/UBSan and TSan real SDK: normal1 and command-loss1
  each (fixed-layout TSan). These target changed allocation/grant and expiry paths;
  all other sanitizer functions rely only on explicitly identified old evidence.
- No queue/shutdown changes planned, therefore no extra overflow/close campaign,
  old48/native40, all SDK matrix or old model61ms investigation. Additional runs
  require a named observed defect and corresponding correction, logged beforehand.

CPU1 Central FIFO11;CPU2 Front FIFO18;CPU3 physical FIFO19;CPU0 monitors FIFO20;
SDK/sender CPU4/5 OTHER0, model auxCPU6 OTHER0. Require current original-user RT20
and per-thread readback. Exclusive build/.m4-exclusive.lock for builds/runtime;
no build/search while timing. Record source/binary/SDK hashes before execution.
Normal success: full existing observation window, correlated commands/Actual/health,
model response, no unsolicited protection or missing native job. Intended fault
success is separate from normal availability; expiry/protection retain original
clocks. Crash injection is not orderly shutdown; surviving SDK stop/join must return.
Raw exits are immutable; sanitizer-clean is not a wall-time or unexecuted-path PASS.

## Evidence-driven bounded correction

Instrumented pre-fix Normal FIFO normal1 PASS; not an expiry reproduction. It
records repeated source-before-release deferrals despite a validated received grant.
New unit's live-grant readiness assertion FAILS before correction. Its initial
expectation that an expired receiver history disappears was wrong: current_sample
retains history/quality. Correct that fixture assertion to check immutable expiry;
do not alter the receiver. Preserve the original failed unit output.

Remove only the issue-after-release requirement; retain exact received issued grant
identity, in-flight settlement and next20ms support guard. No nominal phase, period,
expiry or age changes. The saved expiry871338563 versus release851408166+20ms is
69,603ns insufficient and MUST STILL DEFER. A separate exact-value replay asserts
that boundary. This correction alone cannot claim to resolve that historical
short-support branch. Final Normal8 and sanitizer4 run once; report that limitation
regardless of new normal successes. Any adoption must account for this remaining
cause, not erase it through a passing sample.

## Reject the early-grant candidate (before further runtime)

Both full regressions:935/980 PASS,45 FAIL. One logical normal trace with the same
binary identifies the causal regression: early command expiry1821000001, next
nominal release1821000000, Front receives the next root at1821200000 and protects
BEFORE handling it. One nanosecond of support past the nominal release cannot
support remote handover. The issue-after-release removal is REJECTED and restored;
no runtime acceptance cohort is run on that candidate. Keep both failed full runs
and the single diagnostic trace. No existing assertion is removed.

A separate confirmed readiness defect: current_sample at grant expiry retains
identity but returns canonical unavailable fields/quality. The old readiness check
compares only identity and can report ready for a delayed release. Add actual-time
expiry and bms_permission_allows_normal checks; preserve original phase and next20ms
support checks. Verify this exact unit assertion once against baseline implementation
then final. This fixes misleading eligibility, NOT the historical normal shortfall.
Final full Normal/ASan each once after this correction (required shared-code
regression); final Normal8/ASan2/TSan2 unchanged. Do not classify the rejected candidate
or subsequent passing runs as resolution of the69,603ns historical shortage.

Trace compatibility correction: the restored-phase full Normal run found4 failures
in existing trace assertions (normal behavior itself restored). New diagnostic rows
reused permission sequence as transaction token, colliding with real requests; the
refactor also omitted historical allocation-deferred rows. Restore those exact
pending-request rows/early return and use token0,operation-1 for nontransaction
permission/allocation diagnostics (peer=permission sequence). Preserve old assertions.
Run affected logical/AsyncOwner tests first, then required full Normal/ASan once on
final compatible source. Prior raw full exits stay FAIL; no SDK cohort has run yet.

## Observed startup failure correction (before final-source comparison)

45a3352 final tests: Normal quiet2/2 loaded2/2; fault cohort2/4 (central-stop,
restart-live PASS; command-loss and owner-pause failed BEFORE injection). ASan and
TSan boundary2/2 each. No sanitizer/SDK warning. Full Normal979/980: separate old
OTHER wall physical-pause failed before active; ASan980/980. No repeat of that old
wall case is planned.

owner-pause: Central watch origin598302757517476, first deadline598302861517476,
detected598302861528057 (Epoch0), Epoch-issued598302941716927. The watch is enabled
before EpochStore.issue(), which performs file+directory fsync. That startup path
contains blocking persistence before the owner loop;184.2ms delay exceeded the100ms
lead. Old logs do not subdivide fsync versus ready-marker IO. Move durable issue
before watch construction, both first startup and protected rejoin; retain durable
store, all8ACKs and original100ms/2ms/4ms schedule once enabled. Add bounded
store-begin/return events and assert return<=watch origin in final records. This is
an execution-order fix, not sleep/timeout extension or exclusion of a running owner.
Record Front leaf fault codes on first local selection to distinguish the separate
arm rejection (both Leaves returned negative before any normal command; zero native
miss; high IO busy count alone is not causal proof).

Because startup/rejoin execution order changed, repeat the SAME specified Normal8
and ASan2/TSan2 once on final adapter source; original12 remain10PASS/2FAIL. No new
fault scenario/load. Shared control/watch sources unchanged from45a3352; their
full Normal979/980 and ASan980/980 apply, no fourth full suite. Additional assertion:
every Central generation's real EpochStore return precedes its guard origin and
all normal authority still follows8ReleaseACKs. No unchanged failing case reruns
beyond this source-change comparison.
