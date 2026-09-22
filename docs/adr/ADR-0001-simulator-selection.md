# ADR-0001 — Simulator selection

## Status

Accepted for **StrataDrive Reference Baseline v0.1** (2026-09-22).
설계 경계의 수용이며 runtime 구현/호환성/성능 검증은 **PLANNED / NOT RUN**이다.

## Context

Closed-loop 자율주행을 학습하려면 접근하기 쉬운 vehicle plant, sensor, road,
traffic과 scenario 실행 절차가 필요하다. Simulator 통합 전에도 simple plant로
architecture를 시험할 수 있어야 한다.

## Decision

x86 Ubuntu Host에서 **CARLA 0.9.16 계열을 초기 simulator 후보로 사용한다**.
정확한 build와 호환되는 Host/Python/client/ScenarioRunner 버전은 TBD다.
Scenario 실행을 위해 OpenDRIVE road와 ScenarioRunner / OpenSCENARIO를 검토한다.
필요한 scenario 기능과 버전 지원 여부는 M7 전에 확인해야 한다.

공식 [0.9.16 release 발표](https://carla.org/2025/09/16/release-0.9.16/)에서 해당 release
계열을 확인할 수 있다. [ScenarioRunner 문서](https://scenario-runner.readthedocs.io/)는
향후 호환성 검토 자료이며, scenario가 이미 실행된다는 증거는 아니다.

## Alternatives Considered

- Simple Vehicle Plant만 사용: M6 계약 검증에는 유용하지만, 계획한 풍부한 sensor/traffic
  환경을 다루기에는 부족하다.
- 다른 CARLA release 계열: 호환성이나 재현성 때문에 필요하면 다시 검토한다.
- 상용 CarMaker, CANoe, dSPACE 도구: 학생/개인 학습 프로젝트와는 범위, 접근성,
  비용, 통합 제약이 다르다.

## Consequences

CARLA는 자율주행 중심의 sensor/traffic/scenario 생태계를 갖춰 개인 프로젝트의
출발점으로 활용하기 좋다. 다만 **CarMaker/CANoe/dSPACE와 동등하다고 주장하지 않으며**,
simulator 시험은 HIL이나 실차 검증이 아니다. Plant Adapter 경계로 CARLA API와
control을 분리해야 한다. Mapping 충실도, 동기화, 필요한 scenario 기능의 지원 여부는
미결정이다. [system architecture](../architecture/system_architecture.md)를 참조한다.

미결정 build/호환성/route는 TBD-07(M7), plant mapping은 TBD-02/07(M6/M7)이다.
M0에서는 CARLA를 설치하거나 release 호환성을 검증하지 않았다.

미결정 항목의 owner/rationale은 [TBD register](../roadmap.md#open-m0-decisions)를 따른다.
