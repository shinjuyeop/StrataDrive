# ADR-0062: Host Central–Front/Rear SOME/IP owner separation

Date2026-10-22. **Accept the documented Normal FIFO Host functional SIL profile**.
[Evidence](../test-plan/evidence/m5_someip_rear_adapter/README.md),
[wire/ownership contract](../icd/someip_rear_adapter.md). This extends ADR-0061's
accepted Central–Front host10-v1 path; it does not resolve historical DDS defects.

Central retains real session/RunLease issuance and allocation. Front uniquely owns
FrontZone/Steering/Brake. A separate Rear process uniquely owns RearZone/Drive/BMS/
Power. Their real8-role controls/ACKs, original permissions/credits/commands/results/
Actual/health/protection cross distinct SOME/IP TCP services in separate netns.
Existing owner-wire/CAN/P05 and Front result→Rear command ordering remain. No direct
call/shared-memory control bypass, fabricated ACK, replacement transport or SDK
redesign is introduced. Common transport/Zone endpoints avoid copying adapters.

Keep actual host10-v1 periods, original source/expiry and next-release+8ms support,
20ms envelope, queues8 and2ms/4ms watch. Observed placement is Central1/FIFO11,
Front2/FIFO18, Rear7/FIFO18, plant3/FIFO19, independent monitors0/FIFO20,
SDK4/5/6 OTHER0, plant auxiliary14 OTHER0. Existing OTHER7ms/10ms load applies to
CPU1/2/7. Qualification is2540ms after readiness plus actual NormalStop/HV-off tail;
this is not an indefinite scheduling guarantee or physical fault isolation.

Protected rejoin closes/counts old ingress during graph retirement/durable Epoch IO.
It never clears overflow or renews messages. Surviving processes stay alive and all
actual participants handshake in a new Epoch before credit/arm. Remote wrappers
respect the existing Prepare Ready quiescence; old credit cannot repeatedly advance
the retired actor across agreed INIT. Real Abort/session faults still protect.

Final implementationa790032: Normal FIFO10/10, ASan/UBSan2/2, TSan1/2. Full C++
Normal/ASan987/987 each; original983 tests retained. Small real-owner INIT repro
FAIL→PASS. Normal4 runs have minimum Steering/Brake/Drive renewal margin
7.766637/7.764243/7.163085ms; post-rejoin minima6.378692/6.376290/5.576097ms.

**TSan normal window remains FAIL/incomplete**, with original short-support→expiry
protection and a secondary TX/probe overflow latch; TSan Rear rejoin passed, actual
memory/UB/race warnings0. Under the user-approved criteria, sanitizer wall timing
is separate from Normal operating performance. Do not promote that FAIL to PASS
or claim full-window TSan qualification. Preserve OPEN-SOMEIP-REAR-01 and all41
raw attempts (34 PASS/7 FAIL); only the fixed Normal FIFO profile is accepted.

Rear Host connection is complete in this finite scope. SIL physics/sensors/trusted
scenario inputs remain fixtures. The old detailed Central watch CSV alias on rejoin
is a recorded observation limitation; crash snapshots/events/new-generation records
are retained. SDK-wide safety, cross-machine clock sync, actual NIC/CAN, Jetson,
M6 and whole-system/M4 closure are not established. DDS gate remains CLOSED and its
FAIL/OPEN records unchanged. M6 model/scenario boundary design is a next candidate,
not work started by this decision.
