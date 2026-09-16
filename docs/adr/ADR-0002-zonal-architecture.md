# ADR-0002 — Central → Zone → Leaf architecture

## Status

Proposed — M0 design direction. Architecture is documented; runtime is Planned.

## Context

A direct controller-to-simulator loop would not expose zone allocation, actuator
communication or local ECU fault response. The learning objective includes modern
vehicle E/E boundaries even while components share one Linux target.

## Decision

Adopt Central Vehicle Compute → Virtual Ethernet / DDS → Virtual Zone Controller
→ SocketCAN / vCAN → Steering / Brake / Drive vECU. Separate Central and Zone as
logical Ethernet nodes using Docker networking or Linux namespaces + veth pairs
(selection TBD). Host–Target uses physical Ethernet.

Require actual vECU actuator response to return through the Zone/target feedback
bridge and Host Plant Adapter before affecting the vehicle. Define periodic tasks,
queues, synchronization, state, watchdog, integrity and actuator dynamics as vECU
contracts. They are not implemented in M0.

## Alternatives Considered

- Monolithic controller calling CARLA: less setup but does not exercise these boundaries.
- DDS directly to actuator models: avoids gateway work but omits the CAN/Zone contract.
- Physical distributed ECUs now: stronger hardware exposure but outside M0 scope.

## Consequences

This creates explicit ownership, timeout, translation and fault boundaries, with
additional scheduling/communication/configuration complexity. Sharing a Linux host
does not provide physical fault isolation. vCAN is for application-frame testing,
not CAN FD electrical behavior or actual arbitration timing. ECU timing fidelity,
Zone process layout and allocation rules remain TBD. See
[software contracts](../architecture/software_architecture.md).
