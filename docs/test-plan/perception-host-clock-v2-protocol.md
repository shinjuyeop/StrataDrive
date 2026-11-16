# M10 bounded host boost-cap V2

V1 preserved a first30s PASS and a second pre-native FAIL. Its second synthetic
preparation call took131.980159ms, including110.766417ms preprocessing and
20.824539ms CUDA inference, exceeding the unchanged100ms settled-probe gate.
Model construction and the owner inference worker inherited observer CPUs0,8;
the declared OpenCV override was applied only to the renderer model. Wall-stage
times do not establish how much was computation versus descheduling.

V2 changes that placement: while constructing the model and starting its worker,
the calling thread uses the declared pipeline CPUs (renderer CPUs4–7,12–15 for
Host V1), then restores its observer placement. Newly created ORT/inference
threads inherit the pipeline set. Apply the existing CV4/resize4 overrides after
backend initialization. Record actual preparation affinity and both overrides.
No scheduler, model, tensor arithmetic, 10s/3-call/last-two<100ms preparation
gate, publication authority or live deadline changes. Three predeclared
synthetic CUDA preparations passed at the original100% host cap, with settled
calls33.7–37.0ms; this is not a concurrent physical or70% cap acceptance test.

Also correct two post-live orchestration defects. Relocated audit failures must
match exactly after replacing only the quoted, declared run-root prefix;
different missing members or any other field still fail. Cleanup may skip an
installer only when the installed file already has its original SHA. A known
candidate is restored through the unchanged strict installer; unknown bytes
are rejected. Verify all six shared runtime files afterward. V1 original
sequence errors remain unchanged and its independent restoration is recorded.

All other conditions in [V1](perception-host-clock-v1-protocol.md) remain:
explicit temporary70% maximum request,16% minimum,turbo enabled, no SMM polling;
2K/Epic/D-FINE-M960/CUDA, camera100ms, renderer/query20Hz, selected Host V1,
guarded structured build04, tested native-postfix, passive ORT/CUDA blocking,
physics5ms/320steps/native2/4ms/HV30ms/perception100ms. Startup180s,
shutdown30s, CPU<=70C preflight, memory/disk reserves and original audits remain.

Before freeze: all Python501 and focused frozen85 tests, the unchanged native
207-test result and30/300 allocation checks, V1 complete observer/sensor-cost
checks, three synthetic preparation checks. Freeze protocol, source, runners,
restoration guard and helper. Verify runtime restoration before operator action.
The same narrow privileged helper requires a fresh owner PID; the previous
lease has already restored100% and cannot be reused. Maximum lease1800s.

New sequence: one30s, a second30s only after complete original/frozen/audit PASS,
and one300s only after both pass. Stop on first failure; no reruns of V1 or V2
cases. No build/test/archive work during the live sequence, except its own
post-case sealing after servers stop. Chain raw exclusions from16067. Retain all
images and failures, and independently verify archives before compaction.
The brake/hold scenario, finite results, and observational clock samples do not
close long-term stability, native perception, scene fidelity, quality, Jetson
deployment or M10. No board-specific optimization is added.
