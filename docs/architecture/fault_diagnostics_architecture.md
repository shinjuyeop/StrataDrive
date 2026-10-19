# Fault / diagnostics architecture

Status: M0 계약 **DEFINED**, system fault/DTC runtime **PLANNED**.
M1 actuator receiver의 local 검증/timeout과 [M2 첫 Steering 모델](../learning/m2_steering_model.md)의
source-loss/continuity/deadline hold는 Host에서 구현·시험했다. [첫 Brake 모델](../learning/m2_brake_model.md)의
압력 floor/retain ramp도 부분 구현했다. 차량 보호 출력/DTC 통합은 미구현이다.
[M2 수용 검토](../m2_acceptance_review.md)는 기존 actuator 보호와 BMS/Power/Drive gate·회로 component의
부분 증거를 대조했다. 후속 [Steering response monitor](../learning/m2_steering_fault_monitor.md)는
정상 delay/rate 범위·sensor residual/dwell과 local hold/latch를 구현·시험했다.
[Brake monitor](../learning/m2_brake_fault_monitor.md)도 별도 pressure sensor·rise/fall 범위와 residual/dwell을 구현·시험했다.
보호 floor 요청과 fresh sensor 관측을 구분하며 물리 stuck은 보호 요청 뒤에도 지속될 수 있다.
[ZON-01](zonal_partition.md)의 Central–Front/Rear 독립 link/source monitor는 PLANNED / NOT RUN이다.

```mermaid
flowchart LR
  INJECT[Fault Injection] --> MON[Local Fault Monitor]
  MON --> LOCAL[Local protection and local state]
  MON --> EVENT[Fault Event]
  EVENT --> DIAG[Diagnostics Manager]
  DIAG --> DTC[DTC record]
  DIAG --> STATE[Central aggregate system state]
  LOCAL --> EVENT
```

DTC 저장 완료는 state transition이나 local protection의 선행 조건이 아니다.
Zone/vECU는 Central communication이 없어도 timeout을 검출하고 보호 동작을 수행한다.
Local state와 Central aggregate state의 시각을 구분한다. 통신 단절 중 Central의
상태 표시는 늦거나 unknown일 수 있으며 이를 local NORMAL의 증거로 쓰지 않는다.
재연결 시 더 낮은 severity로 자동 덮어쓰지 않고 INIT 재검증한다.

## Detection ownership

Fault 이름은 논리적 이름이며 numerical DTC mapping은 M9(TBD-08)이다.

[RG-01](../icd/regenerative_braking_design.md)의 유효 회생 한계 0은 ECU 통신 고장이 아니다.
Capability 제한과 actual stream 상실의 증거를 분리하며 기존 critical loss 정책을 유지한다.

| Fault name / scenario | Primary detector | 독립 관측 / 최소 반응 |
| --- | --- | --- |
| STEERING_ECU_LOSS / F01 | Zone steering actual feedback age | Host Plant Adapter per-actuator age; unavailable, FAIL_SAFE, run gate |
| CAN_CRC_ERROR / F02 | 수신 vECU, feedback의 경우 Zone | reject + valid RX age 미갱신; 오류 반복으로 timeout 가능 |
| ALIVE_COUNTER_ERROR / F02 | 수신 vECU/Zone의 sequence 검사 | duplicate/out-of-order/잘못된 epoch reject; 정상 heartbeat로 대체 불가 |
| COMMAND_STALE / F02 | 수신 vECU/Zone의 source freshness 검사 | reject, timeout 보호는 계속 진행 |
| DRIVE_COMMAND_LOSS / F03 | Drive vECU local valid-command age | 이전 양·음수 demand 무효화, zero motor torque target, local FAIL_SAFE, actual response 별도 기록 |
| CENTRAL_COMM_LOSS / F04 | Central VCU valid VehicleCommand age와 각 Zone scoped-command age | local FAIL_SAFE/보호 allocation; Central diagnostics 의존 없음 |
| STEERING_COMMAND_LOSS | Steering vECU local command age | 첫 SIL hold/latch 구현; 실차 hold/rate/가용성 정책 TBD-03 |
| BRAKE_COMMAND_LOSS | Brake vECU local command age | 첫 SIL max(actual, floor) ramp/latch; 차량 초기/유지/감압 정책 TBD-03/06 |
| BRAKE_ECU_LOSS / DRIVE_ECU_LOSS | Zone의 각 actual feedback age | Host도 per-actuator stream 확인; brake 상실에서 정지 보장 금지 |
| REGEN_CAPABILITY_INVALID / RG-01 | Drive input validation + Zone capability age | 새 회생 demand 0, 제한 원인/마찰제동 부족분 기록; critical actual loss와 별도; state/envelope TBD-06 |
| BMS_STATUS_LOSS / BMS_CONSTRAINT_STALE / EV-F01 | Zone BMS status age + Drive forwarded-constraint dependency check | critical loss <=100 ms 검출, 새 normal motor demand 금지와 고장별 local reaction; valid 0≠unknown; TBD-12/14 |
| POWER_NOT_READY / POWER_RESPONSE_FAULT / EV-F02 | BMS power actual monitor + Central vehicle management | READY/normal permission 금지 또는 고장별 보호; precharge/contactor 요청≠actual; recovery INIT 재검증, TBD-12 |
| BATTERY_SENSOR_INVALID / EV-F02 | BMS local sensor validation | 해당 state/limit validity 제거와 local protection; 센서 model/threshold/dwell TBD-13, 미구현 fault는 검증 주장 금지 |
| FRONT_ZONE_LOSS / ZON-F01 | Central의 Front status/Leaf 원천 age; Front Leaf command timeout | local 보호/FAIL_SAFE, normal 배분 중단; Rear link 상태는 독립 관측, Host per-source gate |
| REAR_ZONE_LOSS / ZON-F01 | Central의 Rear status/Drive/BMS 원천 age; Rear Leaf command timeout | 정상 배분 중단/local 보호, Front heartbeat로 정상화 금지; physical reaction TBD-03/12/15 |
| CENTRAL_COORDINATOR_LOSS / ZON-F01 | 각 Zone scoped-command age; Leaf 자체 timeout | 두 Zone 독립 local 보호; coordinator failover 없음, trusted INIT로만 복구 |
| PEER_SOURCE_STALE / PEER_SESSION_INVALID / ZON-F01/02 | 각 수신 Zone의 envelope와 per-source/dependency/session 검사 | cached source·parent expiry 보존, reject는 valid age 미갱신, trusted INIT/rejoin 및 power/health gate |
| ACTUAL_FEEDBACK_STALE | Host Plant Adapter 원천 sequence/time/validity | bridge heartbeat와 독립 검출, run gate; cached actual을 fresh로 처리 금지 |
| STEERING_TRACKING_FAULT | Steering local bounded-target history↔angle sensor | M2 component 구현·시험: rate-band 밖 0.01 rad 초과가 fresh source 기준 60 ms 지속되면 hold/latch; sensor health 별도, 기계 jam의 고유 원인 진단은 아님; Zone 전달 후속 |
| BRAKE_RESPONSE_FAULT | Brake demand↔pressure sensor residual | M2 component 구현·시험: 정상 delay/rise/fall band 밖 25 kPa 초과가 fresh source 기준 60 ms 지속되면 latch·increase-only floor 요청; 센서 health/보호 floor 관측 별도, Zone 전달 후속 |
| TASK_OVERRUN | 각 component deadline monitor/watchdog | task 자체 정지 감시 독립성 M3 결정; miss와 local state 기록 |
| COMPUTE_OVERLOAD | Central health + task timing monitors | optional feature 축소 / 필수 경로 protection; M3/M12 검증 |
| AI_INFERENCE_TIMEOUT / AI_OUTPUT_INVALID | Central inference monitor / Safety Supervisor | 유효 classical fallback 또는 FAIL_SAFE; M11 |

## Top-level state contract

기본 severity 흐름은 **INIT → NORMAL → DEGRADED → FAIL_SAFE**다. 모든 고장이
DEGRADED를 거쳐야 하는 것은 아니며 critical path loss는 NORMAL→FAIL_SAFE로 직행한다.

| State | 의미 / 진입 | 허용 이탈 |
| --- | --- | --- |
| INIT | startup 또는 명시적 reinitialize; normal output 금지, 입력/feedback/health 검증 | 필수 조건 충족 시 NORMAL; startup fault 지속 시 FAIL_SAFE |
| NORMAL | 필수 stream/health 유효, reference envelope 안에서 운행 | 제한된 optional fault는 DEGRADED, critical fault는 FAIL_SAFE |
| DEGRADED | 미리 검증된 제한 envelope의 기능 축소 | critical fault/envelope 이탈 시 FAIL_SAFE; recovery 요청 시 INIT |
| FAIL_SAFE | local 보호 동작, 정상 운행 중단; 안전 정지 보장 의미 아님 | 원인 해소 + 명시적 recovery 요청 시 INIT만 허용 |

M0 F01/F03/F04 및 F02 지속 후 timeout은 보수적으로 FAIL_SAFE를 선택한다.
Actuator가 불확실한 상태에서 계속 운행할 DEGRADED envelope는 아직 없기 때문이다.
[ADR-0048](../adr/ADR-0048-rear-power-routing-and-nondriving-startup.md)은 알려진 Drive capability/BMS derating만
제한적으로 허용한다. 불확실한 actual이나 critical loss로 계속 운행하는 envelope를 추가한 것은 아니다.
동시 fault는 FAIL_SAFE 우선이며 복구는 자동 severity 하향 없이 gate를 거친다.
RECOVERY는 별도 top-level state가 아니라 INIT 재검증 절차다. 상세 dwell과 local
actuator 물리 동작은 [safety contract](../requirements/safety_requirements.md)의 TBD다.

## Fault evidence contract

Event에는 fault name, source component, severity/local state, 영향 Interface/Requirement,
run/epoch, clock domain, last-valid RX, injection onset(시험 시), detection time,
예상/관측값(age/counter/CRC), local action/time을 남긴다. Central 수신 시간과 실제
actuator response time은 각각 별도 필드다. 원천 event를 재전송할 때 검출 시각을 바꾸지 않는다.

M9에서 DTC code, occurrence count, pending/confirmed/cleared, debounce, persistence,
clear policy를 추가한다. DTC는 프로젝트 진단 코드이며 UDS/OBD 구현을 뜻하지 않는다.
Event 기록이 없어도 local protection은 실행되어야 하며 logging loss는 검증 증거 결손으로
명시한다. [Timing](../requirements/timing_requirements.md)과
[verification](../test-plan/verification_strategy.md)에 연결한다.
