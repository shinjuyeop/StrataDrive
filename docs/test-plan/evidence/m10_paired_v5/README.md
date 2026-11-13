# M10 paired V5: 20Hz observation diagnostic pass

2026-11-13. One prospective normal attempt capped original receipt queries at20Hz
instead of50Hz. Physical5ms, original native periods/commands, HV30ms, exclusive
100ms freshness,2560×1536/Epic rendering and D-FINE-M960 remain unchanged.
The frozen auditor reports `PASS_DIAGNOSTIC_CASE_ONLY`.

- 400 physical intervals,234 normal,0 protected/fault/late/missing intervals.
  Model2.0s took2.015625 wall seconds; maximum normal HV dependency22.343ms.
- 38 exported scenes and verified renderer ticks;44 actual images,37 mapped
  images and37 numerical inferences, all37 overlapping physical operation.
  Every call detected a person after the corrected pre-bind placement.
- Scene acquisition→result: minimum68.304ms, median82.329ms, p9590.890ms,
  maximum92.517ms. These37 finite diagnostic observations do not establish a
  guaranteed100ms pipeline or long-run20Hz camera/inference throughput.
- 39 receipt RPC brackets: median0.846ms, maximum3.205ms. Brackets include
  queue waiting and do not identify serialization cost alone.
- 2024 native service rows and400 receipts replay exactly. Renderer/owner
  exited130 without forced stop in5.723s/1.417s; settings restored.

The1343-file prospective source freeze passes43 focused archive checks and456
workspace tests. All44 BGRA images and37 numerical outputs are retained losslessly;
future exclusion is9213, with no holdout accessed. Original timestamps, frame
associations, actor/camera matrices, stored hashes and decoded tensors rejoin.

V4's HV30.334ms failure remains FAIL. This changed-workload pass does not prove
that query rate caused that failure or establish repeated-run stability. It permits
one separately declared conditional renderer stop/crash case under this rate.
All visual inputs remain unavailable for control because full bone/wheel/material
state is missing. Native perception acceptance is0; this is neither full M10 nor
independent detector quality, live Required-mode or Jetson deployment acceptance.
