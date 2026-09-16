# System requirements — M0 draft

모든 요구사항은 **DRAFT / TBD**, 미검증 상태다. `shall`은 향후 검토할 계약의 표현이며
구현/시험 통과를 뜻하지 않는다. 아래는 소수의 baseline 후보다. 100 ms 등의 숫자는
예시이며 safety 근거 또는 측정으로 확정되지 않았다. Owner는 학습자(project owner),
승인 상태는 PENDING이다.

## ID and lifecycle

| Prefix | 범위 |
| --- | --- |
| SYS-ARCH-xxx | architecture / 배포 경계 |
| SYS-COM-xxx | 통신 / freshness / integrity |
| SYS-CTRL-xxx | 차량 제어 / plant loop |
| SYS-AI-xxx | AI 통합 / fallback |
| SYS-SAFE-xxx | 보호 상태 / 동작 |
| SYS-DIAG-xxx | fault / diagnostics / DTC |
| SYS-PERF-xxx | timing / compute 증거 |

ID는 세 자리 증가 번호로 부여하고 삭제/대체 후 재사용하지 않는다. 변경 시 rationale,
영향 component/interface/test, review 상태를 기록한다. Draft → Reviewed → Baselined는
학습자 검토 후 진행하며 implementation/verification 상태는 별도로 관리한다.

## Candidate requirements

| ID | Normative statement (초안) | 설계 이유 / 미결정 acceptance | Component | Test 후보 |
| --- | --- | --- | --- | --- |
| SYS-ARCH-001 | The system shall deploy the same Central–Zone–Leaf architecture independently on either AGX Thor or Orin NX. | 단일 차량에 두 보드 결합 금지; 보드별 stack TBD | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU | TC-ARCH-001 |
| SYS-COM-001 | The Zone Controller shall detect Steering vECU communication loss within 100 ms. | **100 ms는 TBD 예시**; 통신 상실의 기점, monitor 주기/startup, clock 정지 정책 TBD | ARCH-ZONE, ARCH-VECU | TC-COM-001 |
| SYS-COM-002 | Receivers shall reject commands with invalid application CRC, sequence or freshness and shall not refresh valid-command age from rejected frames. | CRC/counter/age parameter와 restart 정책 TBD | ARCH-ZONE, ARCH-VECU | TC-COM-002 |
| SYS-CTRL-001 | The vehicle shall be actuated only through actual Steering/Brake/Drive vECU responses passed to the Plant Adapter. | Classical Controller의 직접 CARLA 호출 금지; actual-state mapping과 한계값 TBD | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER | TC-CTRL-001 |
| SYS-AI-001 | The learned planner shall provide trajectory, target speed and risk outputs through safety validation and classical control, with classical planner fallback on invalid or late AI output. | fallback 입력도 사용할 수 없으면 안전 상태 정책 적용; threshold TBD | ARCH-CENTRAL, ARCH-SAFETY | TC-AI-001 |
| SYS-SAFE-001 | The system shall transition to a safe or degraded state when a safety-critical actuator interface is unavailable. | safe/degraded의 실제 동작, 가용 actuator, reaction deadline 모두 TBD | ARCH-SAFETY, ARCH-ZONE, ARCH-VECU | TC-SAFE-001 |
| SYS-DIAG-001 | The system shall trace monitored faults through fault events, DTC records and system state transitions. | 진단 code mapping, debounce, 저장 유지/복구 정책 TBD | ARCH-DIAG | TC-DIAG-001 |
| SYS-PERF-001 | The system shall measure end-to-end control latency and report Mean/P95/P99/Max, sample count and deadline misses. | clock/domain, 측정 endpoint/protocol과 한계값 TBD | ARCH-CENTRAL, ARCH-ORCH, ARCH-ADAPTER | TC-PERF-001 |

## Requirement detail template

- ID / 제목 / version / 상태 / 담당자 / 검토자: TBD
- Requirement (`shall`, 검증 가능한 단일 의무): TBD
- 설계 이유 / 출처 / 가정 / ODD: TBD
- Trigger / 사전 조건 / 입력 / 관측 가능한 예상 출력: TBD
- 단위 / 수치 threshold / deadline / clock domain / 허용 오차: TBD
- Fault 시 동작 / 의존 관계 / 미결정 사항: TBD
- Architecture component / Interface ID / Test ID / Result ID: TBD
- 검토 결정 / 변경 이유 / 증거: PENDING / NOT_RUN

## Traceability

[Traceability matrix](../test-plan/traceability.md)가 Requirement → Architecture Component
→ Interface → Test Case → Result의 연결점이다. Component ID 정의는
[system architecture](../architecture/system_architecture.md), interface ID 정의는
[interface overview](../icd/interface_overview.md)에 있다. Parameter TBD인 test는
수치 acceptance를 평가할 수 없고 NOT_RUN 또는 BLOCKED로 남긴다.

상세 계약: [timing](timing_requirements.md), [safety](safety_requirements.md).
