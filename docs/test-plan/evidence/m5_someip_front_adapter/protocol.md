# Host Central–Front adapter prospective protocol

2026-10-21, starting clean HEAD/origin/main 771cf86. Preserve all older DDS and
SOME/IP attempts. No external posting or security changes. Raw results never rewritten.

## Stage A: binding and bookkeeping corrections

Before changing ingress: add one `binding-invalid` real-SDK normal case. After eight
normal pairs send a fresh valid owner request on unregistered method0x21. Expect
protocol rejection and no additional CAN frames. Existing code is expected to fail.
Then require exact service/instance/interface/message type/method/payload matching;
exercise every readiness byte, truncated/extended probes, wrong method/type/version,
status request and owner-payload mismatch. Normal + binding-invalid once per build,
15s supervisor/3s discovery/1s diagnostic response (unchanged command20ms).
Python bookkeeping tests run once in a real fresh checkout without build/ after fixes.

## Stage B: real owners

Two network vECU processes: Central (Rear/Drive/BMS/Power/CentralIngress local)
and Front (FrontZone/Steering/Brake local). A persistent SIL physical-model sidecar
is permitted solely for sensor/actuation IO, retains physical history across ECU
restart, owns no controller/session and carries no network control results/ACKs.
Use existing SessionCoordinator, RunLeaseIssuer, real participants/owners, actual
sensor model and feedback validators. All eight real Release ACKs required.
Durable local EpochStore issues epochs; no file grant, invented ACK or RUNNING.
Host same-kernel monotonic agreement, CPU1/2 OTHER0, original owner periods,
Central20ms, exclusive transport20ms and all original inner deadlines retained.
Async bounded8 ordinary lanes, separately bounded authority/protection lanes.
Local owner polling must proceed during network backpressure and expiry.

First normal integration once per explained implementation revision (20s case cap).
A failed baseline permits a rerun only after recorded concrete correction/hypothesis.
Do not expand SDK scope or retry unexplained failures. Final completed-source suite:
normal x3 normal build / x1 ASanUBSan and TSan fixed-layout; late, ready-timeout,
invalid, delay, command-loss, result-loss, status-loss, lease-loss, overflow,
close-full, restart-live and central-stop x1 each build (20s case cap; 3s readiness).
Normal requires actual arm, fresh allocation/results/Actual and no expiry/loss/fault.
Fault cases require intended rejection/protection, original expiry, no reopen in old
Epoch. Restart requires durable larger epoch and all eight actual ACKs/arm again.
Full-close requires observed queue8 while consumer paused, bounded live sender,
pending accounting, protection, SDK stop+join and subsequent new-process cleanup.
Kill/timeout is only forced cleanup or explicitly injected crash, never orderly stop.
All unexpected SDK errors, sanitizer reports, missing outcomes/timeouts => exit1.
Normal performance and sanitizer memory/race verdicts remain separate.

## SDK warning observation

Use pinned3.7.6 unmodified default dependency. If needed a separate build with a
minimal logging-only patch at tcp_server_endpoint::wait_until_sent records error,
is_sending, queue and branch. Record hypothesis/patch before comparison, one normal
and one close-full case; warning text stays. Compare send attempts, peer receptions,
SDK stop and join. This cannot establish general drain or SDK-wide safety.

No full timing campaign by inertia. Decide based on changed shared code and native
execution structure; full related regression required for common behavioral changes.

### Stage B correction 1 (before attempt-02)

Attempt-01 reached all eight Release ACKs and actual arm, then the new diagnostic
compared a pre-step timestamp with the newer arm timestamp using unsigned subtraction.
Underflow immediately triggered the 500ms coverage assertion with zero command batches.
Fix diagnostic elapsed measurement to sample after step. No controller/deadline change.
Run normal once; same coverage criteria. Also buffer bounded transport trace in memory
as required by TransportTrace, flush only after owners stop.

### Stage B fault implementation check (before attempt-03)

Attempt-02 normal passed: all8 ACK mask255, actual arm,24 settled batches,50 Front
results,384 actual/health packets,24 Steering+24 Brake commands. Add fixed fault
hooks only after10 real settled batches, separate diagnostic pending accounting,
full-close consumption hold and persistent Central recovery. Check each of normal,
invalid, command/result/status/lease loss, delay, overflow, close-full, restart-live,
central-stop once in normal build,20s cap. Preserve any failure; this is development
boundary validation, not the final same-source sanitizer cohort.

### Stage B correction/observation 2 (before attempt-04)

Attempt-03:7/11 raw PASS. command-loss/lease-loss/delay reached Front protection,
but runner stopped Central before it observed that failure. Wait for both observed
protection transitions (within existing1s diagnostic bound), not an arbitrary sleep.
Full-close did prove queue8,8 unprocessed negative results, API stop/join while peer
alive;16 diagnostic sends=2 received negative+14 expired. Overflow accounting will
also wait for all pending diagnostic outcomes before declaring completion.
Restart had SDK target-replaced errors for reused client0x1422 and missing remote
Prepare ACKs. Configure restarted Front with distinct transport client0x1423 (still
unrelated to application Epoch), preserve old-error logs. Add phase-only receive/ACK
flush and orderly failure cleanup to distinguish physical preparation from transport
loss. One repeat of four failed cases; no timeout/deadline change.

### Completed-source closure extension

Normal-final15/15 passed. C++ sources/binaries are now frozen for the three-profile
qualification. Extend only the close-full runner sequence: after actual stop/join,
restart both ECU processes in the same netns/veth while the SAME SIL physical model
and durable EpochStore remain alive. Require newEpoch2,8 actual ACKs and normal
control again. One extra normal close-full; include extension in ASan/TSan matrices.
This closes a missing cleanup/restart check, not a repeat until success. Original
normal-final15 results and plan hashes stay unchanged. Normal timing48 remains NOT
RUN: no shared owner/session/controller behavior changed and that campaign exercises
the separate native IO/FIFO executable; it cannot qualify this new network scheduler.
The new adapter's original20ms, input/lease expiry and10/20ms owner grids are tested
here. No hard-real-time or whole-M4 acceptance is inferred.

### ClockError correction (before completed-source campaign2)

Completed-source campaign1: normal15/15 plus full-close/reopen1/1, ASan12/13,
TSan fixed-layout13/13. ASan restart actually reached newEpoch2/all8ACK/arm and
6 batches, then failed CoordinatorFault::ClockError (no sanitizer report). Adapter
passed the same pre-call `t` to receive_vehicle after receive_lifecycle advanced the
coordinator through its actual port checkpoint. This is our adapter scheduling bug,
not an SDK race or permission to relax a clock assertion. Keep both roots' original
source/expiry; pass fresh observation time to each API, and sequence feedback read
before tick time as existing Network does. Rebuild all three profiles; normal1 plus
ASan restart1 first to check the concrete fix, then the fixed full campaign15/13/13
on the final identical C++ sources. Preserve all original campaign1 outcomes.

### SIL IO observability/configuration correction

Clock-fix normal1 PASS; ASan restart1 FAIL on a DIFFERENT path: plant process exited1
(`physical model failure`), fresh physical evidence disappeared, session Prepare
could not complete. No sanitizer report. Retained plant.bin last sensor526097469689237;
PCAP-derived wall/monotonic offset and plant stderr mtime place failure approximately
61.34ms after that sample (conversion uncertainty about0.37ms). Existing model max
step is20ms. Exact failed submodel/step gap was not logged, so timing is a hypothesis,
not established root cause. A recursive workspace metadata search overlapped this
attempt; this uncontrolled interference is recorded, not erased from failures.

The new SIL IO bus incorrectly used a workspace regular file for synchronous
pread/pwrite on each owner poll. Move ONLY this physical sensor/output bus to a
caller-owned tmpfs shared by both vECUs and the model (not the per-vECU DDS/SOME/IP
IPC dirs); copy its final snapshot back for evidence. Network controls/ACKs/results
stay exclusively on IP. Add bounded physical step before/after trace and always dump
model fault/trace on failure. No model/owner deadline, source/expiry, SDK, CPU policy
or queue limit change. This removes filesystem writeback from the SIL IO path but
does not prove that writeback caused the old61ms incident; keep that event OPEN.
Run the predefined final15/13/13 once, no heavy parallel build/search during execution.
This is the last environment hypothesis in this task; unresolved failures block
unconditional adoption rather than trigger repeated trials.

### Application fixes from campaign2 (before campaign3)

Campaign2 normal13/15, ASan13/13, TSan12/13; sanitizer reports0. Normal#3 lost
progress after10 batches (Central ordinary queue8/overflow; Front protected first),
while plant max gap0.737ms. Code review found control-established/protection marker
files were truncated/written EACH poll; make transition recording one-shot in memory.
This is a definite observability defect, not proof that it explains all Host stalls.

Normal and TSan restart both filled the NEW Front authority queue8 BEFORE INIT,
with delayed previous-session traffic from the reconnecting SDK. Publish an atomic
queue-admission Epoch cache only when the actual local participant produces a positive
INIT ACK, before enqueueing that ACK. Drop unbound/wrong-Epoch or expired RunLease,
stale session Control and expired ProtectionRequest BEFORE the bounded inbox. The
existing participant/RunLeaseGate still performs every authoritative check; cache
neither opens a gate nor synthesizes an ACK. Keep new-process overflow FAIL traces.
Add max owner poll gap. No extra environmental hypothesis, queue increase or wait.

Rebuild once; run the same fixed15/13/13 cases on these completed sources. Do not
repeat unexplained failures. Run the logging-only SDK normal+full-close comparisons
after this, and preserve all failure denominators. The old physical61ms event remains
OPEN even if this campaign passes.

### Exact SDK request/response-cache finding and supported application change

Campaign3 normal15/15, ASan13/13, TSan12/13. TSan restart DID complete Epoch2,
8ACK/arm/25batches, rejected old packet, no race warning, but SDK logged two
`set_client_target Target replaced` errors on readiness method0x10. Keep FAIL.
Pinned tcp_server_endpoint_impl.cpp:688–698 records targets only for MT_REQUEST;
server_endpoint_impl.cpp:121–123 key contains service/method/client, not Session ID.
Central's reconnecting TCP port changed even though its application/client survived.
Distinct Front client IDs alone cannot eliminate this request/response-cache path.

Use supported MT_REQUEST_NO_RETURN in BOTH directions for adapter readiness, like
all its existing asynchronous control/result traffic. Version2 probe is exact16
bytes: 53 44 00 02, kind1=query/2=reply, origin0=Central/1=Front, lane0/1,
reserved0, nonzero uint64 little-endian nonce. Reply echoes origin/lane/nonce and
must match the current outstanding probe within1s; rejoin creates fresh probes.
This avoids the SDK response-target cache by API choice, not warning suppression
or SDK mutation. No permission is derived from probe. Legacy component pilot retains
exact4-byte v1 and gains full owner-payload-kind filtering before its queue.
Run final15/13/13 on the completed adapter sources; no retry without new evidence.

Logging-only isolated SDK comparison BEFORE this readiness change: normal1/full-close1
both PASS. Six observed warning branches had sending0,error125(operation_aborted),
queue_bytes0,train_bytes0,dispatched_trains0,reschedule0. Thus those six warnings were
not evidence of a send timer expiration. Preserve original warnings and API/PCAP
records; this does not prove general send drain or resolve all SDK shutdown paths.

### Fault bookkeeping correction, no adapter/source/dependency change

Campaign4: normal15/15, ASan13/13, TSan12/13 raw. Remaining TSan restart's actual
processes all succeeded (newEpoch2,255ACK,24 batches,old rejection); no race warning.
It failed solely on the intentional peer SIGKILL's
`tcei::write_completion_condition: Connection reset by peer(104) bytes transferred:0
bytes to sent:101 remote:10.88.0.2:30502 (1311): [5345.0050.0140]`.
101 bytes is the original RunLease wire payload plus SOME/IP header. The pinned SDK
write completion path reports the socket error from an outstanding asynchronous send.
This is an expected injected lease transmission loss, not normal delivery success.

Keep that raw exit1. Classify ONLY this exact role/socket/service/method/size/reset
when tied to declared Front SIGKILL within100ms, a logged live original lease,
observed Central protection within100ms, and successful real new-session recovery.
Every other SDK error, any sanitizer output, missing outcome and timeout remains
exit1. Store all log lines plus separate expected/unexpected classifications. Test
the actual saved error line and negative contexts; no suppression or time-only waiver.
Run affected restart-live once per profile after runner correction; C++ binaries stay
identical to campaign4. Do not repeat the entire unaffected41-case workload.
