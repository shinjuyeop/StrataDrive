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
physical/sensor IO still fixtures. It is **not unrestricted Host operational
acceptance**: native IO/FIFO execution-watch integration/load qualification is pending;
an earlier physical-model pause/failure remains OPEN with incomplete original timing
diagnosis. Do not transfer native2ms/4ms acceptance to this polling scheduler. The
next step is to bind this adapter into the existing native execution-watch path and
qualify its original deadlines under the prescribed Host load, retaining all failures.

Keep the default transport/dependency selection unchanged. DDS control gate remains
CLOSED with all Cyclone DDS FAIL/OPEN records; SOME/IP is a separate conditional
integration route, not a resolution of those defects. M4 remains Host native IO/FIFO
component limited acceptance / whole NOT CLOSED. Rear network, Jetson, real IO and
whole-system validation are NOT RUN. ADR-0060 remains the historical component-pilot
decision; this ADR supersedes only its statement that no real owner adapter exists.
