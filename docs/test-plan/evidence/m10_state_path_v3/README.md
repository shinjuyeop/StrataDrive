# M10 state-path V3: valid instrumentation, physical failure reproduced

Executed2026-11-16 under the [prospective V3 protocol](../../perception-state-path-v3-protocol.md).
The corrected diagnostic path preserves original cached receipts and joins HV to
its original actuator/coil inputs. It uses the explicitly declared warm-cache
condition from V2. V1 startup failure, V2 instrumentation failures and the earlier
300s stability failure remain retained. No control deadline or source timestamp
was changed. The second case is `NOT_RUN_STOP_ON_FIRST_FAILURE`.

## Result

| Measurement | Original result |
| --- | --- |
| Joint / physical audit | **FAIL / NOT_ACCEPTED**: original native physical acceptance |
| Physical receipts / wall duration | 6000 /30.001094s |
| Normal / INIT / protection | 928 /162 /4910; normal model time4.640s |
| First native protection | 5.474012s after initial; original multi-leaf fault retained |
| HV source / dependency age at protection | 6.834 /30.629ms; dependency limit30ms |
| Native slots | 150000 eligible,0 missing,0 late; maximum body0.259ms |
| State-path integrity | PASS:29997 native calls,6000 receipts,6000 HV derivations |
| Exact native replay | 29997 calls,6000 receipts,0 differences; original source fields equal |
| Frozen archive check | PASS reproducing the original FAIL and checking all287 raw BGRA/RGB images |
| Camera / inference | 287 raw /283 outputs; no recorder overflow;9.400Hz physical-span callbacks |
| Scene→result median /p95 /max | 76.813 /84.369 /154.619ms;4 above100ms |
| Physical-span temperature / throttling | Peak95°C; package counter+10, core0 counter+0 |
| Shutdown | Renderer1.617s, owner1.016s; both exit130, no force |
| Runtime restoration | Original CARLA, DXC, INI and recorded engine identities match |

The runner completed; the physical test did not pass. Most of the run is protected
operation, so aggregate video/CPU values do not describe30s normal driving.
Shadow integrity passed with native perception acceptance0. The physical audit
preserves the commanded protection and subsequent stop; it does not accept this
as the declared normal case. `physical-detail.json` retains the complete result.

## What the new timing shows

The last normal receipt (ticket1090) still carried an actuator dependency already
23.796ms older than its acquisition. It reached native with that dependency
27.635ms old. No replacement arrived before the dependency reached30.629ms and
the native gate closed. Its younger6.834ms wheel/HV source did not refresh the
older actuator input. This is why inspecting only camera frequency or the latest
wheel state would miss the fault.

Before fault, normal owner pre/post-physics median wall/CPU is0.957/0.940ms.
Tickets1089/1090 rise to4.525/4.466ms and4.271/4.235ms. Their staging costs about
1.302ms, state acquisition0.939–0.957ms, and solver-work formatting/validation
1.865–2.038ms. Wall and thread-CPU times are close in these intervals. The shared
receipt publication itself takes approximately0.002ms. Acquisition→native
delivery rises to3.535–3.840ms, including the work done before publication.
The next receipt follows a19.420ms source-end gap, including10.509ms between
the prior completion and next admission; it completes after protection.

Two50ms samples report all16 logical CPUs≤850MHz at5.451793s and5.501940s,
straddling the5.474012s fault. The first sample is22.219ms before protection.
In the surrounding151ms bracket,17 physical intervals show pre/post-physics
median wall3.387ms and CPU3.345ms. Package/core0 thermal counters do not increase
inside that bracket. Energy counters are inaccessible and remain unknown.
Sequential sysfs readings show a contemporaneous low-clock event, not its exact
onset or power/thermal cause. The earlier V2 diagnostic also saw an all-core
low-clock event without protection, so the observation alone is not a sufficient
failure condition.

The measured slowdown is largely added owner CPU execution time, not a large
measured owner-thread wait. Native scheduled slots themselves have no missing or
late completion. This narrows the next software work to reducing CPU work in the
authoritative state path while retaining original freshness/protection rules.
The current code serializes and reparses physics state and solver work, and
serializes the internally built admission request before immediately parsing it.
Removing those internal conversions is a concrete candidate; numerical/state
equivalence and a newly declared live comparison are required before claiming
improvement. The320-substep numerical profile, physics5ms, native2/4ms, HV30ms and
perception100ms remain unchanged. Cooling/power attribution is still unresolved.

The fast observer collected599 physical samples (median interval50.079ms,
maximum50.988ms), no read errors, and consumed0.00507 core averaged across the
whole run. This cost is distinct from the older process-tree profiler.

## Instrumentation corrections and evidence

- CARLA/native clocks use preallocated bounded records. Post-run `state_path`
  belongs beside the immutable receipt; original acquisition stamps are reused,
  never replaced. `original-receipt-identity.json` checks every cached query for
  exact equality and verifies no diagnostic field entered the original receipt.
- HV provenance uses the unchanged physical audit's work-end/acquisition and
  minimum original actuator/coil time rule, including application-time bootstrap
  fallback. All29997 native calls are checked. State-path PASS is separately
  reproduced from the extracted frozen source and does not override physical FAIL.
- The isolated candidate module is
  `0406068ebaf3b3b2012919456563f3a3f0fde21444fdc5dcc884d25988b55f59`.
  The1421-file source/runtime freeze predates live. Python482, frozen focused66,
  native boundary40 and the unchanged native30/300s allocation/start/stop preflight
  pass. The quiet clock benchmark p95 is1.959µs for11 paired diagnostic stamps plus
  measurement stamps; it is not a live-overhead guarantee.
- [State path](normal-30s-01/state-path.json), [stage/clock analysis](normal-30s-01/path-analysis.json),
  [first fault](normal-30s-01/fault-analysis.json), [profile](normal-30s-01/profile-analysis.json),
  [original audits](normal-30s-01/audit.json), [replay](normal-30s-01/replay.json)
  and [archive check](normal-30s-01/archive-validation.json) retain distinct verdicts.
  Analysis, receipt-check and review-packaging scripts are explicitly post-run.
- Future exclusions grow14918→15205. Every original image is retained; raw/run
  archives stay local and ignored. Lossless compaction verifies expanded whole-tar
  bytes before replacing raw transports. `retained-metadata.tar.gz` provides
  checked metadata/native traces and unchanged first-fault trace rows, with all
  original member hashes in its manifest. Follow the [artifact policy](../../artifact-storage.md)
  for full raw reproduction; Git alone is not a raw backup.

M10 remains OPEN: this resolves instrumentation defects and localizes a live
failure. It does not resolve the300s fault, cold-start/thermal issues, complete
wheel/bone/material scene, native perception control, independent model quality
or each Jetson deployment.

Storage closeout verifies and removes457,196,041bytes of duplicate run/source
extractions across V1–V3. V2/V3 lossless raw compaction saves4,804,231,333bytes;
all original image content stays retained. V3's17 raw transports shrink from
4,514,293,760 to2,103,549,431bytes, and its6,865,081byte review archive keeps24
original members plus90 unchanged first-fault rows. Observed free space after
closeout is70.249GB on NVMe and439.815GB on `/d`. Full raw verification requires
the retained local archives; `SHA256SUMS` includes them despite Git ignoring them.
