# Three-process SOME/IP Host adapter — prospective protocol

Start2026-10-22: HEAD/origin/main da5a6696caa89f3397cab1231cc8998ffe0c4170,
fetch successful, clean tree, no intervening commits or AGENTS.md found. Preserve
all existing Front qualification, historical failures and DDS OPEN/gate records.

Scope: Central / Front(Steering,Brake) / Rear(Drive,BMS,Power) separate processes,
actual netns/veth IP paths, one persistent existing SIL plant. Real eight session
participants, RunLeaseIssuer, arm, Front result then Rear commands. No shared-memory
inter-ECU control/authority or fake ACKs. Existing physical IO and execution-watch
channels remain their original sensor/actuator/monitor fixtures only.

Implementation: generalize the existing role/transport/Zone endpoint, preserve
legacy two-process mode. Distinct Central↔Rear ordinary and authority services,
per-peer queues8, SDK8192, original codec/route/clock/Epoch/token/source/expiry.
Host10-v1 allocation10ms / support18ms (next release+8ms reserve), VM10ms phase+4ms,
wire20ms, opportunities2ms/deadline4ms remain. No OS/SDK switch or deadline widening.

Placement candidate (physical cores0..7; siblings8..15): Central CPU1 FIFO11,
Front CPU2 FIFO18, Rear CPU7 FIFO18, plant CPU3 FIFO19, monitorsCPU0 FIFO20.
SDK/senders Central4,Front5,Rear6 OTHER0; plant auxiliary CPU14 OTHER0 (SMT sibling
of SDK Rear6; no owner sibling). Actual policies/affinity/RT20/20 read back.
Existing load: OTHER7ms busy/10ms on each control owner CPU1,2,7. No extreme load.

Development: small binding/ownership/oracle contracts; logical Host10 normal-stop
with original controllers; one initial real normal three-process trial once runnable.
Further development executions require an observed defect/correction or stated new
hypothesis, preserving every raw exit. Do not repeat whole regression during development.

Final same source, one frozen campaign:
- Normal FIFO normal quiet2 + existing loaded2.
- Rear command-loss1, Rear owner-pause1, Central crash1, Rear restart-live1.
- Representative Front command-loss1 and Front restart-live1.
- Actual SDK ASan/UBSan normal1 + Rear restart-live1; TSan fixed-layout same2.
- Changed contracts/Python oracle regression; full Normal/ASan C++ each once,
  retain existing983 names/assertions and add only required new tests.

Normal observation2540ms from transport readiness, then real NormalStop request
renewal and original handoff/HV-off state machine, followed by protection/SDK stop/join.
Allow a separately declared2500ms shutdown observation tail (existing controller
shutdown2s timeout unchanged); native4ms guard covers both phases, never relaxed.
Process supervisor20s, original startup3s, existing9s main bound. Crash injection is
explicit kill, never orderly stop. Guarded workload/file-flush separation retained.

Required: actual 8 ACKs/credit/arm, all three Leaf command receipts before previous
original expiry, original envelope/token/Epoch correlation, real feedback/model response,
no normal unsolicited protection/native misses. Faults only after real normal coverage;
independent monitor/physical action while owner stopped, actual surviving-ECU protection,
new durable Epoch/all8 ACKs/arm after restart while other processes retain PIDs.
NormalStop Complete with measured bus<30V, proper handoff and positive API stop/join.
Original pending/rejected/expired accounting remains. Missing data, unexpected SDK or
sanitizer diagnostic, timeout/forced cleanup => saved FAIL/exit1.

Normal availability and intended protection are separate. Sanitizer wall time is not
Normal performance; actual memory/UB/race errors fail. OTHER wall diagnostics are not
new admission gates. No48 matrix/allSDK/compound faults/M6/Jetson or historical OPEN
root-cause research. Qualified finite Host scope may be accepted without closing
unrelated historical exceptions. No external posts/messages.

## Observed correction and bounded comparison (before rerun)

First candidate1145720: Normal quiet2/2, loaded2/2. Rear fault cohort0/4:
command-loss and Central crash were injected after10 batches but before actual
Drive torque appeared; command-loss capture also ended before physical pressure
reached100kPa. Owner pause correctly faulted/overrode before authority-lane RX8
overflow, but the new oracle incorrectly required no overflow for this declared
stopped-consumer fault. Rear rejoin had a real Central ingress overflow: surviving
Front continued feedback while old graph artifact teardown and durable Epoch IO
blocked the quiescent Central owner. These four raw failures remain failures.

Correction: (a) require real validated positive Drive Actual and released Brake
before declaring control-established; no synthetic state, (b) observe actual model
protection before cleanup, original100ms limit remains, (c) allow only target-owner
pause overflow after independently recorded native fault with rejection count>0,
(d) explicitly quiesce/count/reject ingress during protected graph retirement/Epoch
IO, then reopen before the fresh actual session handshake. No queue/deadline change,
no overflow latch clearing, no old command retry. Ready probes continue but grant
no permission. The three-process normal hot loop now checks actual feedback too.

One four-case Rear comparison follows these specific fixes. Final source also
requires quiet2+loaded2 again because the normal loop prerequisite changed; retain
first candidate4/4 separately. Front representatives and sanitizer cases have not
yet run and remain the originally planned counts. No extra fault combinations.
