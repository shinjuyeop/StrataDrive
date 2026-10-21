# Prospective follow-up after cohort-v1 — 2026-10-21

New evidence, not a blind retry: A1/A2/A3 fail17 initial envelopes each, B3 fails17.
A1 zone trace first user DATA reports `no heartbeat seen yet`; first NACK at
1792554861.863245, next at1792554861.963297 retransmits sequence1. Other samples
wait behind the hole. First application receive age100.784ms; write max0.149ms.
Pinned ddsi_receive.c explicitly drops reliable Cyclone DATA before first heartbeat.
Matching a writer does not establish bidirectional data readiness. Historical-data
wait in this pin returns immediately for VOLATILE; empty wait-for-acks is not a
substitute. Do not change heartbeat timing/SDK synchronization.

Add opt-in `SD_TRANSPORT_READY=1` **normal diagnostic only**. After both local
writer and reader match, each side sends one distinct16-byte diagnostic readiness
record (magic, role, epoch). Each must receive the other exact record before
publishing its ready marker; runner releases go only after both markers. It uses
the same endpoints, public write/take, and original10s setup cap, no fixed warm-up,
new command, discard of command samples or deadline renewal. All60 owner messages
are generated only after go and still must be accepted/echoed within20ms. This is
a transport bootstrap check, not durable Epoch/session/INIT/arm/control readiness.
Legacy defaults and fault scenarios stay unchanged; raw cold-start failures remain.

Before execution: Normal A(full/CPU1+1/5ms) with readiness **3 repetitions**, compare
with cohort-v1 A3. Candidate D(minimal/CPU1+2/20ms) with readiness **one ASan and one
TSan**. Same35s case/600s campaign/512MiB cap, no parallel builds/tests. Any warning
remains FAIL. Separately exercise readiness timeout with two real DDS processes:
one peer deliberately consumes but withholds its readiness record; same10s setup
cap must fail and emit no owner command. **One Normal run**, no retries.

Related sanitizer protection regression (after DDS timing, no product rebuild):
existing remote_contract_test and remote_leaf_test, only original expiry/late ACK,
armed actor composite expiry, stop/protection expiry and bounded FIFO latch cases;
one invocation per binary per ASan/TSan profile,30s cap. Logical component results
are separate from DDS wall-time rejection; no remote physical ACK is synthesized.

Intentional peer SIGKILL prevents complete sanitizer teardown checking. Preserve
cohort-v1 raw verdicts; add an explicit sanitizer INCOMPLETE classification for the
ASan/TSan peer-kill rows. Absence of a warning before SIGKILL is not sanitizer PASS.
