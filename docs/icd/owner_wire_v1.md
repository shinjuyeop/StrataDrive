# Owner wire v1 — Host remote boundary

Date: 2026-10-20. Status: **M4 codec/authority/Leaf endpoint component; remote vehicle runtime NOT RUN**.
CAN/DBC/P05 bytes, DataIDs, counters and checks remain unchanged. This is a new outer Ethernet application contract, not AUTOSAR COM/RTE/BSW or a certified E2E profile. [Current state](../project_status.md) controls acceptance.

## Encoding and routing

Maximum512 bytes. Integers little endian; unsigned8/16/32/64 only, enum uint32 with registered range, bool uint8(0/1), double finite IEEE754 binary64 bit pattern. Optional has bool presence then value; variant has uint8 alternative then value; arrays fixed-length. No C++ padding/ABI, strings or dynamic lengths. Decoder rejects truncation, trailing bytes, unknown version/reserved/tag/enum, NaN/Inf and mismatched route.

| Offset | Type | Meaning |
| --- | --- | --- |
| 0 | uint32 | 0x56524453, `SDRV` |
| 4 | uint16 + uint16 | version1 + reserved0 |
| 8 | uint32 + uint32 | from/to: Front0, Rear1, Steering2, Brake3, Drive4, BMS5, Power6, CentralIngress7 |
| 16 | uint64 | trusted clock-domain identifier |
| 24 | uint8 + fields | payload tag and fields below |
| final4 | uint32 | CRC32C over all preceding bytes; reflected0x82F63B78, init/xorFFFFFFFF; check123456789=E3069283 |

| Tag | Existing canonical data contract | Route |
| --- | --- | --- |
| 0 / 1 | Session Control / Ack | Central→addressed role / role→Central |
| 2 | RunLease: full Plan, sequence32, source64, expiry64 | Central→role |
| 3 / 4 | ZoneRequest / TxResult | Central→Zone / Zone→Central |
| 5 / 6 | LeafRequest / LeafReport | assigned Zone→Leaf / Leaf→assigned Zone |
| 7 / 8 | ProtectionRequest / ProtectionAck | Central→role or Zone→its Leaf / exact reverse |
| 9 | Feedback(raw CAN or Zone health) | Zone→Central |

Exact recursive field order is the explicit `FIELDS` catalogue in [owner_wire.cpp](../../interfaces/remote/owner_wire.cpp). `tests/vectors/owner_wire_v1.hex` is the independent fixed golden (Vehicle request). Canonical message definitions are `interfaces/zone/owner_messages.hpp` and `interfaces/session/session_control.hpp`; transport code does not clone them or include controller/queue/atomic implementation headers. TxResult frame count is always uint64 on wire even on32-bit hosts.

CRC detects accidental corruption and parsing errors; it authenticates neither peer nor authority. The adapter must validate configured peer/route/clock, then existing domain admission/P05 checks. BMS kind/content semantics, permitted scope, real physical readiness and command authority remain the receiving controller's responsibility. Unknown/zero BMS values stay distinct. Raw CAN frame and parent sideband are copied verbatim; an adapter must never re-encode P05, relabel Actual source time, or derive a fresh parent from receipt time.

## Authority and lifecycle

1. Trusted coordinator sends Prepare/INIT/Release to each of8 actual participants. Existing2s Prepare,20ms INIT lead/window,30ms message age apply. Leaf INIT uses common physical reset predicate; model identity/physical history are preserved.
2. Local Release alone does not prove all other participants released. `RunLeaseIssuer` produces credit only when actual SessionCoordinator is RUNNING after **all8 Release ACKs**. Full Plan must match trusted local INIT; first sequence<10, next strictly increasing by≤10; source strictly increases.
3. Credit maximum lifetime60ms, source age≤30ms and exclusive expiry. No first credit by original commit-deadline+30ms latches acquisition failure. Poll old credit expiry **before** receiving a fresh packet; missed lease cannot heal in the same Epoch. Keep the first failure cause; clock rollback may supersede it.
4. Credit permits normal **ingress**, not automatic arm. Existing new sensor/health/HV readiness, request root, scoped command parent, oldest input age, original exclusive context expiry and inner P05 remain required. Existing arm ACK still proves local readiness. Central must await every correlated arm result before emitting normal commands. Enqueue/transport write is not a TX/selection ACK.
5. `RemoteLeafEndpoint` owns one actual AsyncLeafOwner and private local gate/link. It never shares Central's atomic gate. It accepts LeafRequest only from assigned Zone, with live credit/session, matching epoch, original sent/deadline and≤20ms envelope; actual actor enforces inner composite context. Monitoring runs before arm; credit expiration selects actual local protection.
   An old-Epoch request receives a negative result carrying the **request's** Epoch/token/operation, before current-session credit/state polling. Zone discards other-Epoch results before pending/arm/gate/history handling; no response relabels a session.
   Zone preserves the first Central `ZoneRequest.sent_ns` in each child Leaf envelope, and bounds its exclusive deadline by the upstream envelope, the inner command/power expiry, and `first_sent + 20ms`. `delivery_deadline` subtracts before adding to avoid overflow. Arm/Stop use the same original sent/deadline; duplicate forwarding cannot renew them. Inner context/parent/terminal lease and CAN source/payload/P05 are unchanged. The delivery deadline is **not** the actuator command lifetime.
6. Stop passes the existing `ActuatorStopLease` unchanged. Actor checks fresh sensors/arm/current demand and original lease bounds; late stop is not restamped. Credit continues during normal stop/HV shutdown. Missing credit overrides a stop with local protection; terminal expiry remains active.
7. Explicit protection uses epoch32, token64, source64, exclusive deadline64(≤20ms). Local Leaf validates source/clock/role/current epoch, selects real actor protection, then ACKs selection with the same request and immutable selection timestamp per issuer/token. No stopped owner can generate an ACK. `ProtectionReceipt` checks exact role/domain/identity/deadline/positive selection; receipt never opens permission. A new ACK does not prove physical angle/pressure/torque/HV response.
8. Resume/new traffic does not reopen a latch. Rejoin requires larger **durable** Epoch, physical reset evidence, complete new session/credit/readiness/arm. Failed FIFO cannot heal on Epoch change; stop/join the owner before replacing links. Endpoint component test uses explicit trusted grants42/43; existing CLI tests separately prove durable storage. Remote durable grant distribution/restart is still M5 work.

## Clock profile and timeout

Initial Host profile: separate processes/netns on the **same kernel CLOCK_MONOTONIC**, no time namespace; boot/domain agreement supplied by trusted launch config. No packet learns it. Gate rejects different domains, nonzero offset or uncertainty. Inner CAN source clocks therefore need no conversion. Separate-kernel/Target deployment is **blocked** pending synchronization/error budget and inner CAN/RX mapping.

`mapped_time` separately checks signed offset/overflow/uncertainty. With mapped source interval[S−,S+] and expiry[E−,E+], require S+≤now, now−S−≤max_age, now<E−. This math test is not an implemented cross-clock actuator runtime. Existing source/RX timeout and≤100ms loss contracts remain; no clock-skew margin is silently added.

## Validation scope

`remote_contract_test` covers golden, all10 tags, all6 operations/BMS alternatives/raw frame forms, every bit/truncation, delayed original expiry, clock uncertainty, all8 coordinator ACKs, replay/latch/receipt. `remote_leaf_test` runs a real Steering actuator/sensor/physical model through codec→INIT→credit→arm→command→Actual→expiry/protection→new session, stop expiry and true bounded FIFO overflow. `remote_zone_integration_test` additionally wires actual Central/Front/Rear outputs through codec to all five private Leaf endpoints and back to original Actual receivers, including readiness/arm, power/permission/limits, normal control and Stop/HV off. It checks original envelope expiry, late Arm/Stop/Power/permission rejection and old-Epoch results during pending Stop. This is a logical component harness, not remote process deployment or M5 adapter acceptance.
