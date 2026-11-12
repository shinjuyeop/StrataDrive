# Native 2K reception, tracking and protection — Host functional evidence

2026-11-12. The opt-in2K boundary is implemented and checked against retained real
camera results and the existing logical vehicle stack. **M10 remains OPEN.** This
is not a new CARLA live-control run, production IPC, independent accuracy evaluation,
wall timing qualification or Jetson deployment. The existing2K camera/model profile
and the original100ms source/receipt lifetimes remain unchanged.

The [contract](../../../interfaces/perception-native-2k-control-v1.md) and
[verification criteria](../../perception-native-2k-control-v1-protocol.md) describe
the single-owner typed boundary. Python exports the original callback receipt under
the owner's existing lock. C++ checks both clocks, state liveness, geometry/model,
all detections, monotonic acquisition, and expiry independently. Bounded image-space
tracking retains only actual observations; unavailability or expired continuity
clears active histories. No metric distance, velocity or obstacle-based command is inferred.

## Retained real-camera replay

| Original run | All consumer rows | Before state init | C++ reads | Fresh reads | Unique accepted frames |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline-01 | 302 | 1 | 301 | 138 | 100 |
| tensor-01 | 299 | 1 | 298 | 141 | 100 |
| balanced-01 | 301 | 1 | 300 | 30 | 27 |
| Total | 902 | 3 | 899 | 309 | 227 |

Every replayed availability decision agrees with the original owner. The three
pre-init reads remain unavailable without invented clocks. Frame/source/expiry,
original model-call receipt and wall expiry are exact. Histories agree with the
existing Python image tracker after lossless2K↔canonical640 coordinate scaling;
this checks implementation consistency, not tracking quality against GT. Same-frame
polls add no history and cannot renew authority.25 semantic and5 parser mutations
are rejected, including source/receipt expiry and geometry/model/session changes.

These denominators include startup and stopped-camera tail. They do not replace
the prior active-window47.74%/48.76%/10.53% statistics. The balanced condition's
original live integration FAIL is preserved. No model was rerun or camera image
added; no holdout was consumed, and the future-image exclusion remains8975.

## Logical vehicle integration

Nine9-second cases use synthetic typed detections with the existing supervised
speed/PI/allocation, Central/Zone/Leaf ownership, P05 feedback and physical plant.
The camera fixture runs at logical20Hz and the availability monitor at logical50Hz.
These are test schedules, not measured processing rates.

- Shadow camera loss leaves command source/expiry and physical torque/brake/speed/
  energy exactly equal to an otherwise identical unconnected run.
- Required healthy empty input keeps the existing control path running. This does
  not assert a clear road or turn availability into permission.
- Camera loss, invalid geometry, expired receipt, wrong epoch, explicit unavailable,
  and an error followed by valid input before the same release select protection.
- Fresh input after4s restores observation availability but keeps normal authority
  latched closed. The recovery case uses a real new global INIT at6.5s and normal
  permission/Actual in epoch2. Image recovery alone never does so.

In the seven protection cases, the RunGate closes in the requesting release,
both Zone ACKs follow after0.4ms of **logical** time, and the first sampled fresh
P05 Actual satisfying |torque|≤0.1Nm and brake≥0.9MPa arrives after200ms. This is
actuator response in the fixture, not full vehicle stop time, wall latency or a
claim that the100ms image lifetime guarantees braking within100ms.

## Checks and provenance

Normal C++:24 new tests plus64 existing receiver/Supervisor/coordinator tests.
ASan+UBSan:24 new tests. Perception Python:385 tests. The legacy640 cross-language
boundary is also rerun. `validation.json` records the final archived-source check,
and `sources.json`/`sources.tar.gz` preserve its source and replay inputs. The archive
is a final functional-verification snapshot, not a retroactive prospective freeze
for the older live camera studies. `logs/` and `sil/` retain test outcomes and original
sampled releases/Actual; `replay/` retains exact C++ fixture input/output.

Development checks found and corrected a manually transcribed C++ model-hash constant.
The first SIL harness also incorrectly stopped observing when protection closed
RunLease; its seven failed cases are retained in `logs/sil-harness-initial-failure.log`.
The observer now continues through protection and only pauses the old-session adapter
during a different pending global INIT. Required criteria were not relaxed.

The new protection adapter records first loss and uses the existing coordinator
protection route. It does not add a perception-specific DTC or a learned planner,
and it is not installed into the default CARLA/SOME-IP runtime. Next is the bounded
live mailbox/IPC connection in CARLA shadow mode, followed by explicit fault/Actual
measurement. Sparse valid observations currently make immediate Required protection
unsuitable as a default continuous-driving mode. Independent quality, long duration,
metric fusion and per-board deployment remain separate.
