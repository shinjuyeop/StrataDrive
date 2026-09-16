# ADR-0003 — Independent compute tiers

## Status

Proposed — M0 design direction; no board benchmark or deployment has run.

## Context

The goal is to understand which vehicle feature configuration satisfies requirements
under a compute budget. A two-board distributed vehicle would confound this with
partitioning, extra transport and inter-board fault behavior.

## Decision

Treat **Jetson AGX Thor as the Premium target** and **Jetson Orin NX as the Mainstream
target** for the same Vehicle SW Architecture, deployed independently to one board
at a time. Do not connect the boards to form one vehicle.

Freeze and run the same Reference Config, scenario and requirements on both first.
Then measure and explore tier-specific changes, retaining separate reference and
optimized results. Record AI and camera-to-trajectory latency, FPS, CPU/GPU usage,
RAM, power, temperature, control jitter and deadline misses.

## Alternatives Considered

- Thor + Orin as connected compute nodes: answers a different architecture question.
- One target only: simpler, but cannot explore the requested tier trade-offs.
- Optimizing each board before measuring reference: useful later, but loses the
  common starting point needed to interpret workload differences.

## Consequences

Reference model/input/features and requirement acceptance must be shared, while
board-specific software compatibility, power modes and cooling must be disclosed.
Do not assume identical binaries or TensorRT engines are portable between boards.
Premium feature expansion and Mainstream FP16→INT8/model/input/rate/feature reductions
need accuracy and closed-loop revalidation. No board performance ranking is claimed.
Reference workload, budgets and exact board variants remain TBD. See
[deployment protocol](../architecture/deployment_architecture.md).
