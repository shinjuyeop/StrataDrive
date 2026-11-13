# M10 paired V4: visible walker, original physical audit fails

2026-11-13. One prospectively frozen normal attempt corrected the nearby walker
placement using an actual pre-bind SDK snapshot. All36 diagnostic model calls
detected a person, and inspection confirmed a walker in the front-right view.
This is a scene sanity observation, not an independent detector-quality result.

The original physical audit is **FAIL**: normal HV dependency age reached
30.333704ms against the unchanged30ms bound.400 receipts completed, with231
normal and3 protected intervals. The conditional renderer stop/crash case was
not run. V3's earlier finite concurrency pass is retained separately and does
not override this failure.

The first violating native sample is CSV index1991, now1566585006652320,
HV source1566584994883826 and dependency1566584976318616. Before protection,
the physical owner reported `native_command_interval_or_causal` waiting.
Maximum native service gap was1.044538ms. A157.088ms acquisition gap occurs
after protection and is not the initiating event. The receipt RPC before failure
included about5.26ms after the preceding native GET, but this includes queue
waiting and does not establish RPC serialization or rendering as the cause.

All2162 native service rows and400 original receipts replay exactly. Both server
processes exited130 without forced shutdown (renderer2.769s, owner2.070s), and
the original settings were restored. The failed safety audit remains decisive.

The1341-file source freeze passes43 focused checks and456 regression tests.
All69 raw images and36 numerical outputs are retained losslessly. Future
evaluation exclusion increases from9100 to9169. No holdout was accessed.
Actor-root rendering still lacks full bone/wheel/material state; no image or
inference result is available for control and native perception acceptance is0.

V5 separately tests20Hz scene observation instead of50Hz, retaining all physical
and safety settings. It is a workload comparison, not a waiver or a claimed
root-cause fix. `check-live.py` re-extracts the original sources and evidence and
requires the same original audit failure to reproduce.
