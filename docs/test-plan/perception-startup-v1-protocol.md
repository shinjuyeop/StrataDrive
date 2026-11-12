# M10 startup scheduling correction V1

Declared before the new live attempt. Preserve the previous failed trial and
its inputs. No quality/holdout,20Hz optimization, Required promotion or Target work.

TC-PER-091: replay all775 original native service times and3 solver receipts from
`m10_live_shadow_v1/run-01`. The instrumented original policy must reproduce every
native CSV field exactly. Fixed owner-local startup observations record original
INIT enable/acceptance, first scheduled opportunity, dependency times, first ECU
body/fault and dependency wait counts; no hot-loop IO or timestamp replacement.

TC-PER-092: execute ECU bodies at the original10ms/20ms releases while startup
energy dependencies are unavailable. A pre-INIT BMS cohort is explicitly unavailable
in InitialChecks; all original fields remain unretimed. The existing >30ms startup
missing-dependency protection remains checked on every service opportunity after
the first due release. After startup readiness, ordinary input validity/expiry and
latched protection remain authoritative. No replayed ECU jobs or extra budget.
Check delayed energy, permanent absence, existing missing receipt/rejoin/fault and
control regressions, plus ASan/UBSan. Frozen retained-data replay is not live success.

TC-PER-093: after freezing final sources/runtime hashes and a separate archive
rebuild, execute one new `startup-fixed-01` live trial. Same existing owned server,
Town03_Opt spawn0,150 passive pre-camera settling ticks,200 physical interval target,
2K2560×1536/FOV90/Epic/D-FINE-M960 FP32, source and receipt100ms,20ms publisher,
native10ms model/HV30ms/320 solver substeps and original authority/watchdogs.
Use the previously corrected teardown order. Startup180s, client900s, native
observation18s, shutdown30s,96 raw frame slots. No hidden retry or changed rendering.

Record native startup observations, original Actual, raw camera/model calls,
original source/receipt times, server events and solver work. Every received RGB
enters future quality exclusion (prior8976). Separate: startup correction, fresh
shadow delivery, normal driving and lifecycle. A new failure stays failed even if
the preceding ControlDeadline is fixed. Restore module/INI after the owned trial.
