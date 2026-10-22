# ADR-0061: Host Central–Front SOME/IP owner adapter

Date: 2026-10-21. Status: **conditional adoption of the Host functional SIL path**.

Extend the opt-in vSomeIP path from component grants to real SessionCoordinator,
RunLeaseIssuer, eight actual participants, VehicleCoordinator, Front/Rear/Leaf
owners and independently continuing local protection. Central and Front are separate
IP processes. A single persistent SIL model retains physical history. Rear and its
Leaf owners remain local to Central for this phase. The [binding](../icd/someip_front_adapter.md)
preserves owner-wire identity, CAN/P05, original expiry and20ms envelope.

Use separate bounded ordinary and authority TCP lanes, asynchronous owner results,
and nonce-correlated one-way readiness methods in both directions. The latter avoids
vSomeIP3.7.6's request/response target-cache replacement on reconnect using supported
APIs; no SDK behavioral patch, warning suppression or queue growth is adopted.
Discovery/readiness/send-return never authorizes arm or completes a control request.

[Evidence](../test-plan/evidence/m5_someip_front_adapter/README.md) demonstrates real
8-role Release, RunLease/arm, normal control/Actual, rejection, expiry/protection,
full8/8-queue shutdown and new-Epoch recovery while Central survives. Completed C++
campaign raw40/41 plus the runner-only restart correction3/3 are separate denominators;
the original13 failures across201 runtime attempts remain immutable. SDK and project
ASan/UBSan/TSan instrumented builds were exercised; this is not SDK-wide safety proof.

This is an executable functional integration, with fixed trusted demand and SIL
physical/sensor IO still fixtures. The [native follow-up](../test-plan/evidence/m5_someip_native_watch/README.md)
now connects existing2ms opportunities/4ms independent execution monitoring to the
actual grouped Central/Front owners and persistent physical process. Completion
identity uses the original requested wake. SDK send/probes run outside control-owner
work; SDK threads stayOTHER0 on separateCPU4/5, ownersCPU1/2, physicalCPU3 and
monitorsCPU0. Original authority/message/controller deadlines are unchanged.

New Normal FIFO normal quiet/loaded profiles pass3/3 each in a2540ms measured window.
Keep that limited normal-operation evidence separate from adoption: final functional
Normal12/13, ASan13/13, TSan10/13 and actual adapter48=31/48 do not meet all fault/
recovery conditions. **Do not expand conditional adoption to unrestricted operation.**
Original command expiry still protects in some normal runs; the earliest allocation/
gateway cause is partly unresolved. TSan old placement0/13 and all other raw failures
remain. The61ms historical model cause remainsOPEN despite improved observations and
controlled energy.step reproduction. Next correlate permission/allocation phases and
first gateway cause against original Leaf expiry before one targeted correction/test.

Keep the default transport/dependency selection unchanged. DDS control gate remains
CLOSED with all Cyclone DDS FAIL/OPEN records; SOME/IP is a separate conditional
integration route, not a resolution of those defects. M4 remains Host native IO/FIFO
component limited acceptance / whole NOT CLOSED. Rear network, Jetson, real IO and
whole-system validation are NOT RUN. ADR-0060 remains the historical component-pilot
decision; this ADR supersedes only its statement that no real owner adapter exists.


## 2026-10-22 limited FIFO follow-up

[New evidence](../test-plan/evidence/m5_someip_fifo_refresh/README.md): final Normal
FIFO8/8 and ASan/UBSan/TSan SDK boundary2/2 each. User-approved criteria require
Normal FIFO normal/core protection/shutdown/rejoin; OTHER loaded timing is diagnostic,
and sanitizer wall time is separate from Normal performance. Actual memory/UB/race
reports remain failures. Durable Epoch issuance now precedes a generation's native
watch. Allocation readiness checks usable received authority at actual execution time.
No period, expiry, source age, envelope, native deadline, queue or SDK change.

The saved grant is69,603ns short of the next20ms release. Removing the phase check
caused deterministic early command expiry and was rejected. That renewal defect is
not fixed by the narrower readiness/startup corrections or the later passing cohort.
Functional SIL adoption remains conditional; FIFO acceptance expansion and Rear
connection remain blocked on original-deadline renewal. M4 whole/Jetson/system and
all DDS historical FAIL/OPEN remain separate. Do not reintroduce OTHER loaded timing
as a blocker for this user-approved limited scope.
