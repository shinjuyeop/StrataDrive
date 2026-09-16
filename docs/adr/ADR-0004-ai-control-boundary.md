# ADR-0004 — AI / control boundary

## Status

Proposed — M0 design direction; AI and control implementations are Planned.

## Context

Learned temporal planning may produce late, invalid or infeasible outputs. The
project needs observable failure behavior and a classical baseline before adding AI.
Keeping an interface boundary helps study these effects but does not prove safety.

## Decision

Build classical route/waypoint driving first, with Pure Pursuit or Stanley and
Longitudinal PID through Zone/vECU. Add pretrained perception next. Later evaluate
a GRU or small Temporal Transformer using 0.5–1 second state/object history.

AI outputs Future Waypoints / Suggested Trajectory, Target Speed and Risk Score.
It does not directly generate actuator commands. Route its output through Safety
Supervisor → Classical Controller → Vehicle Command, keeping a Classical Planner
fallback for timeout or invalid AI output. If fallback inputs are also unusable,
follow the defined degraded/fail-safe policy instead of assuming fallback is valid.

## Alternatives Considered

- End-to-end learned actuator control: reduces explicit boundaries but makes the
  intended contract, timing and fault studies harder to isolate.
- Classical autonomy only: the correct first phase, but omits later Physical AI learning.
- Learned outputs without a safety validator: insufficient validation/recovery boundary.

## Consequences

Validation, mode switching, trajectory continuity and fallback timing need explicit
tests. A classical controller or deterministic rule does not itself establish
hard real-time guarantees or safety certification. Risk semantics/calibration,
validation limits, training/evaluation split and recovery thresholds remain TBD.
See [software architecture](../architecture/software_architecture.md) and
[safety contracts](../requirements/safety_requirements.md).
