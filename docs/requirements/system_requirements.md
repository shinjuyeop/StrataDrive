# System requirements — Reference Baseline v0.1

Status: **DEFINED**, 문서 baseline은 [M0 종료 검토](../m0_baseline.md)에 따른다.
모든 runtime implementation은 **PLANNED**, verification result는 **NOT RUN**이다.
**StrataDrive Reference Baseline v0.1**은 학부 프로젝트의 engineering starting point다.
수치 acceptance는 양산차 요구사항, 안전 인증 기준 또는 실측 결과가 아니다.
Owner는 학습자(project owner)이며 구현 담당 역할은 traceability/component로 구분한다.

## ID, revision and status

| Prefix | 범위 |
| --- | --- |
| SYS-ARCH-xxx | architecture / 독립 배포 / 계층 경계 |
| SYS-ODD-xxx | Reference ODD |
| SYS-COM-xxx | 통신 / freshness / integrity |
| SYS-CTRL-xxx | 차량 제어 / plant loop / tracking acceptance |
| SYS-AI-xxx | AI 통합 / fallback |
| SYS-SAFE-xxx | 보호 상태 / local 동작 |
| SYS-DIAG-xxx | fault / diagnostics / DTC |
| SYS-PERF-xxx | logical timing / 측정 계약 |

ID는 세 자리 증가 번호로 부여하고 삭제/대체 후 재사용하지 않는다.
아래 기존/신규 요구사항의 현재 revision은 모두 **v0.1**이다.
DEFINED는 계약 정의, PLANNED는 향후 작업, TBD는 미결정 parameter,
NOT RUN은 미실행, IMPLEMENTED는 존재하는 실행 구현, MEASURED는 관측 결과 보유,
VERIFIED는 해당 revision의 전체 acceptance 검증 완료를 뜻한다.
문서 BASELINED와 runtime VERIFIED는 별개이며, 측정만으로 자동 VERIFIED가 되지 않는다.

## Reference ODD

SYS-ODD-001의 범위는 맑은 낮, 포장도로, 단일 ego vehicle, 신호등 없는 단순 route,
CARLA에서 재현 가능한 직선/완만한 곡선, 속도 **0–40 km/h**다.
복잡한 교차로와 복잡한 traffic interaction을 제외한다. 정상 S01–S03에는 다른 차량과
보행자의 상호작용을 넣지 않는다. 정지/startup은 범위에 포함하지만 parking, 후진,
급곡선, 야간/악천후, lane change, obstacle avoidance 성능은 이번 기준의 대상이 아니다.
곡률/route 좌표와 map은 M7에 고정한다(TBD-07). M8에서 30 km/h 주행 가능성과 재현성을
확인하며 부적합한 route로 acceptance를 완화하지 않는다. Fault injection과 M10/M11 AI
확장은 같은 interface를 사용하되 ODD 확장 시 requirement revision을 남긴다.

## Normative requirements

아래 `shall`은 정의된 의무이며 구현 완료가 아니다. 수치 평가 방법과 구간은
[scenario baseline](../test-plan/scenario_baseline.md), 시간 기준은
[timing](timing_requirements.md)을 함께 적용한다.

| ID | Requirement statement | Rationale / acceptance 연결 |
| --- | --- | --- |
| SYS-ARCH-001 | The system shall deploy the same Central–Zone–Leaf architecture independently on either AGX Thor or Orin NX. | 보드별 compute budget 비교; 두 보드 결합 차량 금지; TC-ARCH-001 |
| SYS-ARCH-002 | The system shall distinguish vehicle-level command, actuator command and actual actuator feedback by producer, meaning and interface direction. | allocation 및 actuator dynamics/fault 관측; TC-CTRL-001 |
| SYS-ODD-001 | The reference driving scenarios shall remain within the StrataDrive Reference Baseline v0.1 ODD defined above. | 범위 밖 성능 주장 방지; TC-CTRL-002/003/004 |
| SYS-COM-001 | The Zone Controller shall detect Steering vECU feedback communication loss within 100 ms of the last valid feedback reception. | F01; timeout threshold만이 아니라 monitor 지연까지 포함; TC-COM-001 |
| SYS-COM-002 | Receivers shall reject commands with invalid application integrity, sequence or freshness and shall not refresh valid-command age from rejected frames. | CAN application CRC 필수, DDS integrity 방식 TBD-05; TC-COM-002 |
| SYS-COM-003 | Each receiver shall detect loss of a critical command or actual-feedback stream within 100 ms of its last valid reception, independently of Central diagnostics. | vECU의 actuator command, Zone의 Central command/각 actual feedback, Plant Adapter의 각 actual feedback에 적용; TC-COM-001/003/004 |
| SYS-COM-004 | Feedback bridges shall preserve per-actuator source time, sequence, validity and causal command identity without making cached feedback fresh by republication. | bridge 수신 시각은 원천 생성 시각과 별도; TC-COM-005 |
| SYS-CTRL-001 | The vehicle shall be actuated only through actual Steering/Brake/Drive vECU responses passed to the Plant Adapter. | sensor→Central→Zone→vECU→actual feedback→Plant 경계 필수; TC-CTRL-001 |
| SYS-CTRL-002 | The Plant Adapter shall never substitute vehicle-level or actuator commands for missing, stale or invalid actual feedback. | feedback 상실은 run gate/fault 정책 적용; TC-COM-001/005 |
| SYS-CTRL-003 | The Plant Adapter shall be the only writer applying ego actuation to CARLA. | Planner/Controller/Zone, autopilot, scenario runner의 별도 actuation 금지; TC-CTRL-001 |
| SYS-CTRL-004 | The vehicle shall maintain an absolute steady-state speed tracking error of at most 1 km/h in each eligible constant-speed window. | 평균으로 spike를 숨기지 않고 window 내 max absolute error 평가; TC-CTRL-002/003/004 |
| SYS-CTRL-005 | The vehicle shall achieve a 95th-percentile absolute lateral cross-track error of at most 0.3 m on each reference route. | ego reference point와 reference path 기준; TC-CTRL-002/003/004 |
| SYS-CTRL-006 | The vehicle shall achieve a 95th-percentile absolute heading error of at most 3 deg on each reference route. | path tangent 대비 wrapped angle; TC-CTRL-002/003/004 |
| SYS-CTRL-007 | The vehicle shall not exceed the time-aligned validated target speed by more than 10 percent while that target is positive. | S03의 감속 request와 연속 target profile 구분; TC-CTRL-002/003/004 |
| SYS-AI-001 | The learned planner shall provide trajectory, target speed and risk outputs through safety validation and classical control, with classical planner fallback on invalid or late AI output. | fallback 입력도 무효면 보호 상태; M11 계약, TC-AI-001 |
| SYS-SAFE-001 | The system shall transition to DEGRADED or FAIL_SAFE when a safety-critical actuator interface is unavailable. | 상태만으로 정지 보장하지 않음; fault별 정책은 safety 문서; TC-SAFE-001 |
| SYS-SAFE-002 | Components shall start in INIT, inhibit normal driving output until required input and feedback checks pass, and require explicit reinitialization before recovery to NORMAL. | 초기화/복구 gate, 자동 즉시 복귀 금지; TC-SAFE-002 |
| SYS-SAFE-003 | The Zone Controller and each vECU shall execute their local timeout protection without waiting for Central communication or diagnostic acknowledgement. | F04 및 상위 process 단절; TC-COM-004 |
| SYS-SAFE-004 | On drive-command timeout, the Drive vECU shall invalidate the old demand and select a local zero-propulsive-torque target rather than retain uncontrolled torque. | actual torque는 dynamics에 따라 변함; ramp/응답 deadline TBD-03; TC-COM-003 |
| SYS-DIAG-001 | The system shall trace monitored faults through fault events, DTC records and system state transitions. | local action과 기록 경로 분리; DTC 통합 M9, TC-DIAG-001 |
| SYS-PERF-001 | The system shall measure end-to-end control latency and report Mean/P95/P99/Max, sample count and deadline misses. | endpoint/clock/causal path는 timing 문서; M0 실측 없음; TC-PERF-001 |
| SYS-PERF-002 | The Reference Config shall define sensor/plant and planner rates of 20 Hz, controller rate of 50 Hz, and Zone and each vECU control rate of 100 Hz. | logical starting point, 실행 시간/보장된 deadline과 구분; TC-PERF-002 |
| SYS-PERF-003 | Timing and timeout evidence shall identify its clock domain and distinguish simulation time from elapsed monotonic wall time. | 서로 다른 clock 직접 차감 금지, pause/reset 별도 처리; TC-PERF-001/002 |

## Change control

수치와 logical rate는 M3 timing, M6 simple plant, M7 CARLA mapping, M8 control tuning
증거로 변경할 수 있다. 실패 결과를 그대로 보존하고 결과에 맞춰 threshold를 조용히
바꾸지 않는다. 모든 변경에 아래 행을 추가하고 requirement 문장, profile, ICD,
scenario/test, traceability를 함께 갱신한다. 이전 결과는 이전 revision에 귀속된다.

| Revision / date | 대상 | 변경 / rationale | 영향 / 근거 | Review |
| --- | --- | --- | --- | --- |
| v0.1 / 2026-09-22 | 기존 8개 및 신규 15개 requirement | 사용자 지정 ODD/rate/acceptance와 계층 분리를 M0 계약으로 확정; 기존 SYS-COM-001의 100 ms 예시를 검출 상한으로 정의 | M0 문서 검토; runtime evidence 없음; 전체 traceability/profile | M0 exit review 참조 |

향후 행에는 이전 값→새 값, 실험 Result ID(없으면 그 이유), 결정 owner, rationale,
영향받는 test와 재시험 milestone을 반드시 기록한다.

[Traceability](../test-plan/traceability.md)가 Requirement → Component → Interface →
Scenario/Test → Future Result의 단일 연결점이다. 미결정 parameter는
[roadmap TBD register](../roadmap.md#open-m0-decisions)로 관리한다.
