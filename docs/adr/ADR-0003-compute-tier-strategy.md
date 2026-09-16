# ADR-0003 — Independent compute tiers

## Status

Proposed — M0 설계 방향이며, 보드 benchmark나 배포는 아직 실행하지 않았다.

## Context

목표는 주어진 compute budget에서 어떤 차량 feature 구성이 요구사항을 만족하는지
이해하는 것이다. 두 보드로 분산 차량을 구성하면 partitioning, 추가 통신, 보드 간
fault 동작이 함께 개입해 compute budget의 영향을 구분하기 어려워진다.

## Decision

동일한 Vehicle SW Architecture의 **Premium Target은 Jetson AGX Thor**,
**Mainstream Target은 Jetson Orin NX**로 정의한다. 한 번에 한 보드에 독립 배포하며,
두 보드를 연결해 하나의 차량을 구성하지 않는다.

먼저 동일한 Reference Config, scenario, 요구사항을 고정하고 두 보드에서 각각 실행한다.
이후 tier별 변경을 측정하고 탐색하며 reference 결과와 최적화 결과를 구분해 보관한다.
AI latency, camera-to-trajectory latency, FPS, CPU/GPU 사용률, RAM, power, temperature,
control jitter, deadline miss를 기록한다.

## Alternatives Considered

- Thor + Orin을 연결된 compute node로 사용: 다른 architecture 질문을 다루게 된다.
- Target 하나만 사용: 단순하지만 요청한 tier별 trade-off를 탐색할 수 없다.
- Reference 측정 전에 각 보드 최적화: 나중에는 유용하지만 workload 차이를 해석할
  공통 출발점을 잃는다.

## Consequences

Reference model/input/feature와 requirement acceptance는 공통으로 유지하고, 보드별
software 호환성, power mode, cooling 조건은 공개해야 한다. 동일한 binary나 TensorRT
engine을 두 보드에서 그대로 사용할 수 있다고 가정하지 않는다. Premium feature 확장과
Mainstream의 FP16→INT8/model/input/rate/feature 축소는 정확도와 closed-loop 재검증이
필요하다. 보드 성능 순위를 주장하지 않는다. Reference workload, budget, 정확한 보드
variant는 TBD다. [배포 protocol](../architecture/deployment_architecture.md)을 참조한다.
