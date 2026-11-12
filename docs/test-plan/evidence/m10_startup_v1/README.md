# M10 startup scheduling correction V1

2026-11-12. **Original ControlDeadline cause reproduced and corrected; continuous
wall driving remains FAIL/OPEN.** Same 2560×1536/FOV90/Epic, D-FINE-M960 FP32,
original source/receipt100ms and vehicle authority/deadlines. This is startup
correctness work, not a new quality evaluation,20Hz tuning or Jetson optimization.

## Cause and correction

The previous failed trial's775 native service times and3 physical receipts reproduce
every native CSV field exactly with the instrumented original owner. The common
startup dependency wait suppressed all five ECU bodies until energy had a post-INIT
source. Four bodies then first ran at enable+30.008980ms, exceeding their original
30ms tick-gap limit; Steering/Brake/Drive/Power reported ControlDeadline. Their first
scheduled opportunity was10.005651ms; BMS's was20.000492ms. INIT delivery itself was
1.012811ms after the original enable. This distinguishes an ECU scheduling gap from
the separate wall execution watchdog, which had reported no job overrun.

ECU bodies now run at their original10ms/20ms releases while observing unavailable
startup dependencies. Held pre-INIT BMS data is marked unavailable in InitialChecks;
its source/identity fields are not changed. The existing >30ms missing-dependency
protection is checked on each service opportunity, even between ECU releases. Once
startup dependencies become ready, ordinary input validation and latched protection
remain authoritative. No timestamp renewal, catch-up jobs or extra deadline budget.

With the same retained history, first bodies now equal first due opportunities,
all five first-body faults are0, and the previous protection point disappears.
Later Drive LocalInputsUnavailable remains because the frozen input ends after
three receipts. This replay supplies no fictional additional physics.

## Separately declared live attempt

[Protocol](../../perception-startup-v1-protocol.md) declared one `startup-fixed-01`
trial after freezing1,296 source/build inputs and rebuilding them elsewhere. The
same200-interval target used an owned server,150 passive pre-camera settling ticks,
native10ms model/320 substeps/HV30ms and96 raw frame slots. No hidden live retry.

- All five INIT deliveries were5.939µs after original enable. First bodies ran at
  **10.000005ms** (Steering/Brake/Drive/Power) and **20.006173ms** (BMS), with0 faults.
  Thus the original ControlDeadline failure is corrected in the actual process.
- Only2 physical intervals completed;0 normal intervals and no arm. Post-INIT
  power/electrical dependencies never arrived, and existing protection selected at
  **enable+30.005207ms**, initial+64.009916ms. This attempt stays **FAIL**.
- Server status reports a **64.766699ms gap between PumpWall calls**. No admission
  wait was reported before protection; afterward it reports
  `native_protection_authority`. RPC max at the first gap report was0.118503ms.
  This localizes the next investigation to the server execution gap. The available
  record does not identify whether rendering, driver waits or scheduling caused it;
  it is not evidence of an admission deadlock or an inference-induced delay.
- The first actual model call began21.896390ms **after** protection. One camera
  frame200/one empty detection result was retained. Both actual world snapshots
  preceded native enable, so the2K receiver correctly never initialized from them:
  40 native reads,0 fresh reads,0 accepted results. The prior trial's one successful
  shadow delivery remains valid for that trial; this new one demonstrates none.
- Native wall watch:3,950 jobs,0 detected overruns. Original P05 Actual packets
  decoded: Steering2, Brake2, Drive37. This does not establish a full physical stop.
- Server SIGINT exit130/native exit0; pause/reset/close succeeded. The earlier
  cleanup correction now completed live: camera destroyed after ownership release,
  no cleanup errors. Original module and GameUserSettings were restored exactly.

[Audit](startup-fixed-01/audit.json), [timeline](timeline.json), original
[startup observations](startup-fixed-01/capture/native-startup.json), and
[server lifecycle](startup-fixed-01/server.json) keep these separate verdicts.

## Verification and preservation

- **181 C++ regression tests PASS**, including2 startup regressions and existing
  asynchronous runtime, faults, remote leaves, recovery and2K control SIL.
- **67 ASan+UBSan tests PASS**. The20 M4 logical tests exclude the2 separate wall
  tests; this is not a claim that an unrun wall suite passed.
- Archived1,296 files rebuilt before live: original/fixed retained replay exactly
  reproduced,38 wheel/clock C++ and4 cleanup Python tests passed.
- New live replay: all **789 service rows/2 receipts** and every startup observation
  exactly match using the archived corrected binary. Replay is not another live run.
- Frozen shadow auditor reproduced the failed live audit. Post-run startup checks
  rejected13 mutations covering timings/dependencies, wire fields, Actual CRC, raw
  omission/corruption and a false cleanup claim.
- Initial instrumentation compile warning and two initial regression fixture
  failures are kept in `checks/`. The fixture's9ms acquisition-to-apply interval
  prevented the intended INIT path; correcting it to the original trial's1ms
  relationship allowed the targeted regression. These are development failures,
  not discarded live attempts.
- Original compressed BGRA is Git LFS `raw-startup-fixed-01.tar` (7,147,520bytes),
  with archive/member/BGRA/RGB hashes checked. All received frames retained, no
  warmup exclusion. Future quality exclusion **8,976→8,977**, no holdout access.

Rebuild the frozen original/corrected sources and replay the previous trial:

```bash
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_startup_v1/check-evidence.py \
  --work build/m10-startup-v1/reproduce-NEW
```

Verify this failed live trial and mutations (hydrate the raw Git LFS archive first):

```bash
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_startup_v1/check-live.py \
  --work build/m10-startup-v1/audit-NEW
```

The source archive is the immutable pre-live input. The evidence manifest and
post-run checker additionally cover outcomes; they are not retrospectively claimed
as live inputs. Next: add bounded server timing around PumpWall, game/render waits
and sensor handoff to locate the64.77ms gap before proposing an execution change.
Keep physics source freshness, original protection and shadow-only authority.
