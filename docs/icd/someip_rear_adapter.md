# Host Central ↔ Front/Rear SOME/IP owner adapter

Implementation candidate: three ECU processes, based on the accepted `host10-v1`
[Front adapter](someip_front_adapter.md). Qualification and exact scope are in
[Rear evidence](../test-plan/evidence/m5_someip_rear_adapter/README.md). This adds
Rear IP separation; it does not replace owner-wire, CAN/P05, the session protocol,
or physical SIL models. SOME/IP is the protocol; vSomeIP3.7.6 is the implementation.

## Ownership and paths

| Process | Sole active owners | CPU/policy candidate |
| --- | --- | --- |
| Central | SessionCoordinator, EpochStore issuer, RunLeaseIssuer, VehicleCoordinator, allocation, CentralIngress | 1 / FIFO11 |
| Front | FrontZone, Steering, Brake, their real session/credit endpoints | 2 / FIFO18 |
| Rear | RearZone, Drive, BMS, Power, their real session/credit endpoints | 7 / FIFO18 |
| Persistent SIL plant | Existing physics/sensor models and independent physical protection | 3 / FIFO19 |

Each ECU's single owner thread runs its existing owner service grids. Independent
monitor threads use CPU0/FIFO20. SDK dispatch/IO/sender threads remain OTHER0,
Central4/Front5/Rear6; plant auxiliary work uses CPU14/OTHER0. Actual readbacks are
required in evidence. The shared model bus carries only sensor/actuator IO and its
existing release fence; watch channels carry only progress/epoch observations.
Neither carries inter-ECU command, permission, credit, ACK, result or feedback.

Central observes actual Front/Rear feedback through existing validators, creates
new original permission and command bytes, and waits asynchronously for the real
Front result before sending Rear allocation. BMS/Power lifecycle, permission
frames, PowerRequest, results, Actual and health use the Rear ordinary lane.
All eight real participants retain Prepare/INIT/Release; positive ACK mask255 is
necessary before original RunLease issuance. Actual readiness/preflight/arm follows.
Each remote Zone uses one shared `RemoteZoneEndpoint`; each local Leaf uses the
existing `RemoteLeafEndpoint`. No second Central controller/participant is active
inside a Zone process. Legacy two-process mode remains explicitly selectable.

## IP and binding

Separate netns with private routing resources (`/tmp`, `/dev/shm`, application,
network, diagnosis/client identity). A Host veth bridge links Central10.88.0.1,
Front10.88.0.2, Rear10.88.0.3/29. Packet capture and sockets must prove both paths.
Front services0x5344..0x5347/ports30501..30504 retain their meanings.

| Method | Direction/service/TCP port | Exact owner-wire v1 payload |
| --- | --- | --- |
| 0x0020 | Central→Rear / 0x5348 / 30505 | ZoneRequest addressed only to RearZone: lifecycle, vehicle, power, commands, arm, stop |
| 0x0040 | Central→Rear / 0x5349 / 30506 | Actual Session Control for RearZone/Drive/BMS/Power |
| 0x0050 | Central→Rear / 0x5349 / 30506 | Original RunLease |
| 0x0060 | Central→Rear / 0x5349 / 30506 | Original ProtectionRequest |
| 0x0040 | Rear→Central / 0x534b / 30508 | Actual participant ACK |
| 0x0060 | Rear→Central / 0x534b / 30508 | ProtectionAck only after actual local selection |
| 0x0070 | Rear→Central / 0x534a / 30507 | Actual/health Feedback from RearZone |
| 0x0080 | Rear→Central / 0x534a / 30507 | TxResult with original identity/operation |
| 0x0010 | Both directions on each ordinary/authority service | Existing exact16-byte probe v2; origin1 means the bound remote Zone |

All services instance1/major1/minor0, message type `MT_REQUEST_NO_RETURN` (0x01).
Payload is exactly `OwnerPacket.bytes[0:size]`, <=512, no C++ layout/implicit
serialization. CRC, role, method/type/version, clock domain, token/Epoch, original
source/sent/deadline and inner expiry retain existing validation. Service identity
also binds the remote ECU: Front services cannot introduce Rear authority or vice
versa. SD UDP239.255.1.1:30490 and bilateral probes on all four Central lanes prove
transport readiness only; neither readiness nor SDK send completion grants control.

Per peer/lane queues remain8, SDK endpoint buffers8192 bytes. FIFO TCP bytes are
not application delivery guarantees. The asynchronous sender keeps SDK work off
owners; actual feedback/results settle pending requests. `host10-v1` remains10ms
allocation, management10ms/+4ms, permission support through next release+8ms,
original20ms envelope, 2ms opportunities/4ms deadline and original controller grids.
No stale field is restamped and no retry extends validity.

## Protection, shutdown and rejoin

Each surviving Zone monitors original command/credit/source age and owner progress.
A paused owner cannot ACK; its independent monitor closes gates and the persistent
physical monitor applies the existing override. On whole ECU death the plant and
other ECUs remain the living protection subjects. No dead owner is credited with
protection or normal teardown. Central death is tested with both Zones alive.

Normal observation is followed by actual NormalStop, renewed trusted stop intent,
real Leaf handoff and measured HV-off. Stop requests replace scenario Enable/vehicle
roots; they do not overwrite feedback. After Complete, protection and bounded
pending cleanup precede sender shutdown, SDK stop and dispatch join. Forced cleanup
is failure, never orderly stop. A separate2500ms observation tail covers the original
2s controller shutdown budget without changing any deadline.

After an injected Zone crash, surviving Central and other Zone retain their PIDs.
Existing global protection is allowed/required; uninterrupted Front output during
Rear rejoin is not required. A trusted explicit request makes the existing durable
store issue a new Epoch. All eight real participants prepare/initialize/release
again, new credit and arm are required, and old packet bytes must be rejected.
The restarted SDK client has a new transport identity; this never substitutes for
application Epoch. The plant keeps physical state through the rejoin.
