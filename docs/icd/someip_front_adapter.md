# Host Central ↔ Front SOME/IP owner adapter

Status: **conditional adoption for the tested Host functional SIL profile**,
[ADR-0061](../adr/ADR-0061-someip-front-owner-adapter.md). Native IO/FIFO timing,
Rear network separation, Jetson and whole-system acceptance are not established.
This is separate from the [older component pilot](someip_pilot.md) and its grant
fixture. SOME/IP is the protocol; pinned COVESA vSomeIP is the implementation.

## Transport binding

Instance1, major1/minor0. Central10.88.0.1, Front10.88.0.2 on separate netns/veth.
Both nodes have their own routing manager and isolated `/tmp` and `/dev/shm`.
SD is UDP239.255.1.1:30490. All application traffic is **TCP**. There are no
eventgroups/subscriptions. All methods below use `MT_REQUEST_NO_RETURN` (0x01),
including the reverse direction; application identity and correlation are in the
canonical bytes. No SDK request/response target cache is needed.

| Method | Direction / service / TCP port | Exact payload / purpose |
| --- | --- | --- |
| 0x0010 | Both directions on each service below | v2 transport probe, exact16 bytes; no authority |
| 0x0020 | Central→Front, 0x5344:30501 | owner-wire ZoneRequest addressed to FrontZone |
| 0x0040 | Central→Front, 0x5345:30502 | Session Control for FrontZone/Steering/Brake |
| 0x0040 | Front→Central, 0x5347:30504 | Actual participant Session Ack |
| 0x0050 | Central→Front, 0x5345:30502 | Original RunLease from real RunLeaseIssuer |
| 0x0060 | Central→Front, 0x5345:30502 | ProtectionRequest on the separate authority lane |
| 0x0060 | Front→Central, 0x5347:30504 | Actual ProtectionAck, checked by ProtectionReceipt |
| 0x0070 | Front→Central, 0x5346:30503 | Existing Feedback: Actual/health/status, validated by Central |
| 0x0080 | Front→Central, 0x5346:30503 | Existing TxResult, original Epoch/token/operation correlation |

Payload is exactly [owner-wire v1](owner_wire_v1.md) `OwnerPacket.bytes[0:size]`,
maximum512 bytes; no C++ layout, padding or new size prefix. vSomeIP serializes its
header only. Method/type/interface/service/instance, payload variant, from/to route,
CRC and trusted same-kernel monotonic domain0x53444d4f4e4f must match. Domain agreement
is a trusted Host launch assumption, not authentication or cross-machine clock sync.
SOME/IP Session/client IDs do not substitute for application Epoch/token.

Probe v2 is `53 44 00 02`, kind1=query/2=reply, origin0=Central/1=Front,
lane0=ordinary/1=authority, reserved0, then a nonzero uint64 little-endian nonce.
A reply echoes the query origin/lane/nonce and must match a currently outstanding
probe younger than1s. Service availability plus successful probes on both lanes
within3s establishes transport readiness only. Rejoin resets probes. Unsupported
bindings are rejected before entering queues; all actual participant/owner checks
still execute after transport validation. The component pilot retains exact4-byte
v1 readiness and exact4-byte status-query formats; v1 and v2 are not interchangeable.

## Session and ownership

Central process uniquely owns SessionCoordinator, RunLeaseIssuer, VehicleCoordinator,
RearZone, Drive/BMS/Power and CentralIngress. Front process uniquely owns FrontZone,
Steering and Brake. All eight real participants receive Prepare/INIT/Release and
produce their own ACKs. Coordinator requires all eight Release ACKs before issuing
RunLease; actual feedback/preflight precedes arm. Transport readiness/send-return
cannot change this rule. The FrontEndpoint wrapper uses the existing participant,
RunLeaseGate and actual owner; RemoteLeafEndpoint is reused for Steering/Brake.

Durable EpochStore is explicitly bootstrapped once by the trusted launcher. On
Front crash, Central stays alive, observes failure and protects. A separate explicit
local operator rejoin request initiates a new durable Epoch, local owner graph
reinitialization and all eight participant handshakes. The surviving SDK application
is retained; the restarted Front has a distinct transport client ID. Old packet bytes
are rejected, not retimestamped. No grant file or assignment of RUNNING exists here.

The persistent SIL process alone owns the existing physical/sensor models. A tmpfs
bus carries only model sensors/actuation IO; each slot has one ECU writer, and the
model survives ECU restart. All inter-ECU control/session/result/Actual/health data
uses the IP services above. Trusted Enable and fixed vehicle demand are scenario
inputs. No healthy feedback, Release ACK or physical state is fabricated. Real CAN
devices, chassis/CARLA and Host native IO are outside this profile; existing CAN/P05
bytes and Leaf receiver/controller/model behavior are exercised.

## Delivery, bounds and protection

TCP provides ordered bytes per connection, not command completion or a20ms guarantee.
Ordinary and authority lanes have distinct TCP services and bounded8 RX/TX queues;
SDK queues are8192 bytes, payload limits512 remote/1024 local. Overflow latches a
fault; it never enlarges queues or renews requests. An asynchronous sender calls
the SDK outside owner execution. No owner waits for a network response. Existing
10/20ms owner grids and Central20ms allocation run with local monitoring continuing
when ordinary reception is paused. The optional native Host path now binds the existing
M4 execution watch:2ms service opportunities,4ms deadline, original requested-slot
completion and independent monitor protection. This does not alter10/20ms controller
periods. Its finite2540ms qualification window is not an indefinite scheduler claim.

No automatic application replay retries a command. Original source/sent/deadline,
exclusive `min(original_deadline, sent+20ms)`, inner expiry and allocator dependencies
remain unchanged at admission, CAN write and settlement. Expired/missing results
lead to protection. Actual/status is periodic new owner evidence, not a cached value
relabelled fresh. Session retries stay within existing phase/source deadlines;
fresh RunLease issuance requires live real session authority. RunLeaseGate checks
both original expiry and30ms source age. Prequeue stale-credit rejection uses only
an Epoch cache published by an actual positive INIT ACK; it grants no permission.

Protection has its own lane and local expiry/receiver monitors, independent of the
ordinary queue. FrontZone acknowledges selection only after both actual Leaf paths
select protection. Application TxResult records Zone processing/CAN admission;
physical achievement is separately observed through actual feedback/model output.

Shutdown first selects protection and accounts pending/unprocessed requests, stops
the sender, then calls SDK stop and joins dispatch. Send-return is not drain proof.
Raw API timestamps, original warning text, peer observations and bounded-loss
accounting are retained. A runner timeout/kill is never orderly success. See the
[fixed tests, raw results and limitations](../test-plan/evidence/m5_someip_front_adapter/README.md).

## Native execution binding (2026-10-21)

See [native protocol/results](../test-plan/evidence/m5_someip_native_watch/README.md).
Central main owns Central/Rear/Drive/BMS/Power/Ingress as one actual completion group7;
Front main owns FrontZone/Steering/Brake as group0. Each has monitor9; persistent
physical group8 observes process-monitor completions through a bounded Linux atomic
mmap observation channel. This channel supplies no session/command authority. The
physical output override takes priority over fresh same-Epoch nominal outputs; only
trusted higher-Epoch release permits recovery. Whole-ECU death also kills its local
monitor, leaving the peer and persistent physical process as surviving protectors.
A stopped physical process has no independent modeled physical actuator.

Normal/FIFO candidate: mainCPU1/2/3, monitorCPU0; FIFO11/18/19/20 only on those selected
threads. SDK/senderCPU4/5 and model auxiliariesCPU6 stayOTHER0. Readback and original
userRT20/20 are preserved. Callback validation/bounded enqueue and asynchronous SDK
send preserve ownership; application queue capacity8 and SDK8192 bytes are unchanged.
Overflow rejects the extra arrival without overwriting queued items, latches fault
and selects local protection independently of Central's command queue. Full queue
shutdown and actual overflow have separate verdicts.

Only measured normal FIFO quiet/loaded performance (3/3each) is positive profile
evidence. Functional and fault cohorts contain failures, so native operational
adoption remains pending. No current source re-stamping, deadline extension, retry
lifetime renewal or broad sanitizer exemption is part of this contract.


2026-10-22 [FIFO follow-up](../test-plan/evidence/m5_someip_fifo_refresh/README.md):
allocation readiness also requires usable received permission at actual execution
and unexpired original authority. Original release/source/support predicates remain.
Durable EpochStore.issue finishes before a new native guard starts; eight real ACKs,
RunLease and arm are still required afterwards. The historical short-support renewal
path remains OPEN, so final FIFO8/8 is bounded evidence, not expanded adoption.
