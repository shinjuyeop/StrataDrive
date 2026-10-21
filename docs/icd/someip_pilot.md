# Central ↔ Front SOME/IP pilot binding

Status: opt-in Host component pilot; not the regular M5 adapter. SOME/IP is the
protocol; COVESA vSomeIP is this implementation. DDS/Cyclone DDS qualification and
all its historical FAIL/OPEN records remain unchanged. See [protocol and evidence](../test-plan/evidence/m5_someip_pilot/protocol.md).

## Wire binding

All entries use service **0x5344**, instance **0x0001**, interface major **1**,
minor **0**, TCP **30501**, Front server / Central client. SD uses UDP
239.255.1.1:30490. No events/eventgroups/subscriptions are implemented, hence no
subscription ACK is used as readiness or control evidence.

| Method | Direction | Request payload | Response payload | Meaning |
| --- | --- | --- | --- | --- |
| 0x0010 | Central → Front → Central | exact `53 44 00 01` bytes | same four versioned transport-probe bytes | bidirectional readiness only; no owner/state transition |
| 0x0020 | Central → Front → Central | owner-wire v1 `ZoneRequest`: VehicleRequest or Front ScopedCommands | owner-wire v1 `TxResult` | original Epoch/token/operation correlation; result records processing, not physical achievement |
| 0x0030 | Central → Front → Central | `53 44 00 01` query | owner-wire v1 Feedback containing original Steering Actual CAN frame | observed fixture sensor status; no arm permission |

Owner payload is exactly `OwnerPacket.bytes[0:size]`, **not** the in-memory C++
variant or the full padded512-byte array. No extra size field: SOME/IP payload
length is the canonical packet length (max512). vSomeIP serializes the SOME/IP
header, not these application structures. Existing decoder/CRC32C, route and
trusted launch clock-domain checks run before the owner can see a request.
Malformed/unsupported binding returns an empty method response (protocol rejection,
never an accepted TxResult); valid rejected requests return correlated accepted=false.
SOME/IP client/session IDs never replace application Epoch/token.

## Preserved contracts and explicit limitations

- Central uses existing ControlAllocation and `front_commands`; Front uses existing
  CommandGateway, FrontStartupControl, Steering/Brake actors and CAN/P05 codecs and
  receivers. Constant-zero sensor observations and allocator support inputs are
  explicit SIL fixtures. Rear/management/permission fixture values are not measured
  remote state. No trajectory controller, Rear network, CAN device, Host IO or full
  vehicle closed loop is claimed.
- A separate trusted launcher grant initializes/arms only these component objects.
  No eight-participant Release ACKs, RunLeaseIssuer, regular global RUNNING, or
  network INIT/Release/Arm authority is manufactured. Transport method0x10 cannot
  grant control. Session/RunLease/remote ProtectionRequest bindings are NOT implemented.
- Root expiry60ms and allocation dependency expiry from existing allocator are
  retained, not recreated by Front. Outer transport expiry is exclusive
  `min(original_deadline, original_sent+20ms)`; checked at ingress and final CAN
  write along with context expiry. No result wait, readiness, retry or restart
  renews these times. Front rejects old Epoch and nonincreasing token; no same-Epoch
  latch recovery. Restart constructs fresh objects under a new locally supplied Epoch.
- App receive/response mailbox has capacity8, failure latch; SDK send queues have
  separate8192-byte limits and a512-byte reliable payload limit. Overflow selects
  existing local Hold/Protect independently of consuming the blocked normal FIFO.
  Status is latest locally produced observation; it carries its original CAN bytes.
  Result loss is a failed transaction, not application retry. TCP retransmission
  may deliver stale bytes, which remain subject to the original expiry.
- TCP provides ordering/retransmission but has head-of-line blocking; it is chosen
  for bounded request/result correlation in this first pilot, not a 20ms guarantee.
  Status polling avoids untested subscription/event lifecycle and does not claim
  loss-free periodic telemetry. UDP event/loss recovery and separate remote
  protection/session lanes remain integration work. DDS QoS names are not mapped
  to vSomeIP configuration as if their semantics were equal.
- Four nPDU debounce/retention values are explicitly0; SDK defaults otherwise cost
  5ms sender retention per direction. OTHER0 CPU1/2, 20ms allocation/10ms Leaf
  observation, bounded1ms owner polling. No FIFO promotion or deadline relaxation.
  `profiles/reference.yaml` is design reference, not consumed by this executable.
- Same kernel monotonic clock, fixed trusted domain0x53444d4f4e4f, offset0,
  uncertainty0; separate time namespaces are not used. This does not establish
  cross-kernel Jetson clock agreement or authentication. CRC is not authentication.

Each process owns its routing manager, local socket directory and /dev/shm in an
independent mount namespace; different diagnosis/client IDs0x13/0x1311 and
0x14/0x1422 prevent cross-host routing ambiguity. Captured veth TCP payload and
socket/netns records prove actual IP transit. The two netns simulate vECU boundaries
on one Host; they do not implement Host PC plus Jetson deployment.

## Official implementation sources

[vSomeIP3.7.6 release](https://github.com/COVESA/vsomeip/releases/tag/3.7.6),
[pinned README/build requirements](https://github.com/COVESA/vsomeip/blob/4187431d2815bd351845a09d01aa85b2a3163cab/README.md),
[pinned configuration including nPDU and byte queue bounds](https://github.com/COVESA/vsomeip/blob/4187431d2815bd351845a09d01aa85b2a3163cab/documentation/vsomeipConfiguration.md),
[Boost1.85 archive digest](https://www.boost.org/releases/1.85.0/).
