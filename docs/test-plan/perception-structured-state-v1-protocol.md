# M10 structured-state V1: remove internal JSON roundtrips

The state-path V3 failure remains: first protection5.474s, HV dependency30.629ms,
contemporaneous all-core low clocks and longer owner CPU execution. This new
candidate reduces CPU work without changing5ms physics,320 vehicle substeps,
native2/4ms, HV30ms, perception100ms or any original source/expiry/permission.
It does not diagnose the host power/cooling cause or enable native perception.

Add nonvirtual object-returning physics/work methods while retaining the original
FString API and identical constructor/solver validation bodies. Keep class data,
virtuals and generated reflection unchanged. Opt in with `--structured-state` in
bounded endurance only. Direct internal admission uses the same parsed-request
logic and original auth/session/packet/admission checks. The known ASCII envelope
uses a conservative4096-byte overhead plus exact packet hex/null lengths; larger
or noncanonical envelopes take the original16384-byte text parser path. External
RPC size, null-byte and parser checks are unchanged. No snapshot caching or
timestamp refresh. Final original receipts stay immutable.

Before native START, the actual UE JSON implementation must roundtrip4096 finite
double patterns, including signed zero/subnormal/boundary values, bit-exactly;
check nested types/strings and deliberate mutations, and one actual static physics
snapshot. Check nine generated internal envelope sizes, roundtrip equality and
oversize/noncanonical fallback. Reject the candidate before control starts if any
check fails. Keep the result/event timestamp in the capture. This preflight is
not part of measured control timing. Isolated module compilation and source-body/
class-layout checks, complete Python and frozen boundary tests precede live.
The native binary is unchanged; retain its40 boundary tests and30/300s allocation/
start/stop preflight, checking its exact hash.

Freeze source/protocol/runner/runtime before any live case. Use the previously
declared warm-cache condition, the same Host V1 placement and F/G/H settings:
2K/Epic/D-FINE-M960, camera100ms model, renderer20Hz wall, parked preparation,
passive ORT, CUDA blocking, NVMe raw BGRA, same original180s readiness/30s shutdown.
No separate cache preparation, host setting/privilege change or board optimization.
Require CPU≤70°C within180s, RAM≥4GiB, and each volume free≥existing horizon's
stored bound plus4GiB, with unchanged2GiB live reserves. No build/compression live.

Sequence: one30s case, a second30s only if the first original joint/shadow/exact
replay/state-path/structured-state checks all pass, then one300s only if both30s
cases pass. Stop on the first failure; preserve it, do not retry or weaken bounds.
Source generation, startup, image recording, shutdown and archive integrity all
count. For a completed case with any failed audit, do not escalate its horizon.

Compare owner stage wall/thread-CPU and source→publication→native distributions.
Separately compare original tickets200–900 (701 normal moving intervals) with
state-path V3; do not compare its short moving prefix to a candidate's mostly
stationary/protected aggregate. Missing/non-normal tickets invalidate that prefix
comparison. Record host clocks/temperature and limits on between-run attribution.
Keep the original acquisition/application/HV sources and exact native replay;
perception admission remains zero even if finite concurrency passes.

Restore original CARLA/DXC/INI after every case. Chain every actual image from
15205 prior exclusions; independently verify all raw BGRA/RGB and reproduce the
original frozen verdict before removing duplicate NVMe spools. Lossless archive
compaction occurs only afterward, with expanded whole-tar byte checks. Git retains
review evidence and source snapshots; raw/run archives stay local and ignored.
Any passes are limited to these finite scenarios. Earlier failed configurations,
full visual state, independent quality, each Jetson deployment and M10 remain
separate; do not claim the host clock-drop root cause is fixed.
