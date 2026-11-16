# M10 state-path V2: instrumentation failures retained

Executed2026-11-16 under the [V2 protocol](../../perception-state-path-v2-protocol.md).
This explicitly uses a warm-cache condition after one separate empty-renderer
preparation. The preparation reached readiness in97.024s, verified zero vehicles,
sensors and walkers, parked the world, and exited in3.273s without force. It
restored original runtime hashes. Its600s preparation allowance does not change
the measured cases'180s readiness or30s exit limits. The [V1 cold-start failure](../m10_state_path_v1/README.md)
remains open. `retained-preparation.tar.gz` preserves the preparation logs and
individual hashes.

## Original verdict

**FAIL**, with the second case `NOT_RUN_STOP_ON_FIRST_FAILURE`. The first case
completed6000 intervals in30.001075s:5834 normal,166 INIT,0 protection. The unchanged
joint audit reached `cached original receipt unchanged` and failed because the
new trace query appended `state_path` inside the previously exported receipt.
The diagnostic audit separately failed `HV dependency source missing`: it wrongly
assumed each HV dependency was another physical acquisition, although the original
contract derives it from actuator/coil inputs. These are instrumentation defects;
the original audits were not weakened or rerated.

Shadow integrity and exact native replay passed. Both servers exited without
force (renderer1.416s, owner1.267s), and original CARLA/DXC/INI hashes were restored.
Independent frozen-source archive verification reproduced the original FAIL and
checked all285 BGRA/RGB images. Future exclusions grow14633→14918. The frozen
source has1416 files and65 focused tests pass;481 Python tests passed before this
case. Post-run corrected code passes482 and is frozen separately for V3.

## Diagnostic observations, not acceptance

The [post-run analysis](normal-30s-01/path-analysis.json) uses the corrected
actuator/coil join on the untouched original archive and records all native calls
checked. It does not replace `state-path.json`, `audit.json` or their failed verdicts.
`analyze-state-path.py` and `package-review.py` are post-run tools, not frozen V2
acceptance logic.

Normal before/after-physics wall median/p95/max is0.693/1.165/3.078ms, with CPU
0.680/1.142/2.968ms. Acquisition→native receipt median/p95/max is0.854/1.295/2.178ms;
publication→native upper bound is0.599/0.950/1.523ms. The largest original
acquisition-end gap is11.994ms;10.085ms of it precedes the next admission. These
are separate stage distributions, not additive percentile budgets.

Seven consecutive50ms samples at12.242–12.543s report all16 logical CPUs≤850MHz.
In the surrounding0.401s bracket,44 physical intervals have before/after-physics
wall median2.759ms and CPU median2.677ms; apply→acquisition-end median3.693ms.
Two image results end in that bracket with maximum200.738ms latency. Package/core0
thermal counters do not increment in this bracket; throughout the physical run
CPU peaks98°C and the package counter increases16. The strong wall/CPU agreement
shows added owner execution time in this window rather than a large measured
owner wait, but does not prove why clocks dropped or explain the earlier300s
failure. Energy counters are permission-denied and remain unknown.

The fast sampler collected599 physical samples, median interval50.076ms, maximum
50.304ms, no read errors; its whole-run CPU average was0.00474 core. Sequential
sysfs frequency readings are not exact hardware cycle-rate measurements.
Video callback rate is9.366Hz. Scene→result median/p95/max is77.205/87.557/292.300ms;
6 results exceed100ms. This is diagnostic imagery with zero native admission.

## Retention and correction

The17 raw tar streams were independently checked and losslessly compacted:
4,482,836,480→2,089,349,476bytes. Whole expanded-byte hashes and the uncompressed
manifest remain retained. Raw/run archives stay local and ignored by Git.
`retained-metadata.tar.gz` contains24 checked original members and100 unchanged
trace rows around the largest source gap; its manifest identifies the full run.
The source snapshot, case, failures, replay, restoration, profile and hashes are
kept for review under the [artifact policy](../../artifact-storage.md).

[V3](../../perception-state-path-v3-protocol.md) moves diagnostics beside the
receipt and checks HV against the existing work/actuator/coil identity. It retains
all timing limits, runs under a fresh declaration and stops on its first failure.
The earlier300s fault, cold-start failure, native perception, full scene, independent
quality, Jetson deployment and M10 remain OPEN.
