# ADR-0001 — Simulator selection

## Status

Proposed — M0 design direction; compatibility validation and learner approval pending.
No simulator is installed by this baseline.

## Context

The project needs an accessible vehicle plant, sensors, roads, traffic and scenario
workflow for learning closed-loop autonomy. The architecture must remain testable
with a simple plant before simulator integration.

## Decision

Use the **CARLA 0.9.16 family as the initial simulator candidate** on an x86 Ubuntu
Host. Exact build and compatible Host/Python/client/ScenarioRunner versions remain
TBD. Evaluate OpenDRIVE roads and ScenarioRunner / OpenSCENARIO for the scenario
workflow; required scenario features and version support must be checked before M7.

The official [0.9.16 release announcement](https://carla.org/2025/09/16/release-0.9.16/)
confirms this release family. The [ScenarioRunner documentation](https://scenario-runner.readthedocs.io/)
is the future compatibility reference, not evidence that a scenario already runs.

## Alternatives Considered

- Simple Vehicle Plant only: useful for M6 contracts, insufficient for the planned
  richer sensor/traffic environment.
- Other CARLA release families: revisit if compatibility or reproducibility requires it.
- Commercial CarMaker, CANoe or dSPACE tooling: different scope, access, cost and
  integration constraints for a student/personal learning project.

## Consequences

CARLA offers an autonomy-oriented sensor/traffic/scenario ecosystem and a practical
starting point for a personal project. It is **not asserted equivalent** to
CarMaker/CANoe/dSPACE, and simulator tests are not HIL or real-vehicle validation.
The adapter boundary must isolate CARLA APIs from control. Mapping fidelity,
synchronization and required scenario feature support remain open. See
[system architecture](../architecture/system_architecture.md).
