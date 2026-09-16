# Fault / diagnostics architecture

Status: M0 **Planned / TBD**. Fault 처리, DTC storage와 state machine은 미구현이다.

```mermaid
flowchart LR
  INJECT[Fault Injection] --> MON[Fault Monitor]
  MON --> EVENT[Fault Event]
  EVENT --> DIAG[Diagnostics Manager]
  DIAG --> DTC[DTC]
  DTC --> STATE[System State Transition]
  MON --> LOCAL[Immediate local protective action]
```

위 기본 흐름은 기록/상태관리 관계다. Diagnostics Manager/DTC 처리 완료를 기다리느라
local protection을 지연해서는 안 된다. Zone/vECU는 Central 통신 단절 중에도 자신의
timeout/fault 정책을 적용하는 방향이다. State 보고가 늦을 수 있으므로 local state와
Central system state를 구분하여 기록하고 재연결 시 reconcile 규칙을 정한다.

## Candidate monitors and reactions

모든 reaction은 **정책 후보 / TBD**이며 actuator 가용성과 scenario 검토 후 확정한다.
Candidate 문자열은 fault name이며 아직 numerical DTC mapping이 아니다.

| Fault candidate | Planned monitor | Candidate consequence |
| --- | --- | --- |
| CENTRAL_COMM_LOSS | Zone valid command age | local 제한/controlled-stop 가능성 평가 |
| STEERING_ECU_LOSS | Zone valid steering feedback age | steering 가용성 상실, DEGRADED/FAIL_SAFE 정책 |
| BRAKE_ECU_LOSS | Zone brake feedback age | brake 의존 stop을 보장하지 않음; scenario별 대안 검토 |
| DRIVE_ECU_LOSS | Zone drive feedback age | torque 가용성 상실, 제한/중단 |
| STEERING_TRACKING_FAULT | Steering demand vs actual residual | 지속성/threshold 검증 후 제한 |
| BRAKE_RESPONSE_FAULT | Brake response envelope | pressure buildup/response delay 이상 판단 |
| CAN_CRC_ERROR | Receiving Zone/vECU application CRC check | frame reject; invalid frame으로 freshness 갱신 금지 |
| ALIVE_COUNTER_ERROR | Receiving Zone/vECU counter check | duplicate/out-of-order/restart 정책 적용 |
| AI_INFERENCE_TIMEOUT | Central inference age/deadline | classical planner fallback |
| AI_OUTPUT_INVALID | Safety validation: finite/range/shape/feasibility | candidate reject, fallback 또는 안전 상태 |
| TASK_OVERRUN | task deadline monitor / watchdog | task별 영향에 따른 local 보호 및 event |
| COMPUTE_OVERLOAD | Central health and timing monitors | optional feature gating/감속 후보; safety task budget 보존 |

## State contract

| State | 의미 | 진입/이탈 계약 후보 |
| --- | --- | --- |
| NORMAL | 필수 interface/기능이 검증된 운행 상태 | startup checks 성공 후에만 진입 |
| DEGRADED | 정의된 제한 아래 일부 기능 운용 | fault별 허용 feature/speed/제한 TBD |
| FAIL_SAFE | scenario와 가용 actuator에 맞는 보호 동작 상태 | 심각한 fault 또는 degraded envelope 이탈; 안전 보장 표현 아님 |
| RECOVERY | fault clear 이후 health 재검증/재동기화 | dwell/rejoin/수동승인 정책 만족 전 NORMAL 복귀 금지 |

초기 상태는 RECOVERY 후보이며 초기 출력과 startup grace는 TBD다.
NORMAL → DEGRADED/FAIL_SAFE; DEGRADED → FAIL_SAFE/RECOVERY;
FAIL_SAFE → RECOVERY; RECOVERY → NORMAL 또는 fault 재발 시 DEGRADED/FAIL_SAFE를
검토한다. FAIL_SAFE → NORMAL 즉시 자동 복귀는 baseline 후보에서 허용하지 않는다.
동시 fault의 severity 우선순위/latching 규칙과 recovery 권한은 미결정이다.

## Fault event / DTC template

- Event ID, source component, fault name, severity, affected interface / requirement: TBD
- Run ID, source timestamp + clock domain, detection timestamp, sequence: TBD
- First/last occurrence, occurrence count, current/pending/confirmed/cleared state: TBD
- Evidence: expected/observed value, counter/CRC/age, local action and action time: TBD
- Numerical DTC mapping, debounce/confirmation, persistence, clear/recovery policy: TBD

DTC는 프로젝트 진단 코드이며 UDS/OBD 표준 구현을 의미하지 않는다. Fault injection은
scenario 정의에 onset/duration/target/seed와 expected monitor/state를 남긴다. 검출 시간,
local action, system state transition, 실제 actuator response 시점을 각각 관측한다.
[Timing](../requirements/timing_requirements.md)과
[verification](../test-plan/verification_strategy.md)에 증거를 연결한다.
