# ADR-0049: Front non-driving 시작과 두 Leaf/gateway의 arm

Date: 2026-10-19. Status: **Host component·분리 vCAN 구현/시험 / 전체 coordinator 후속**.
[ADR-0048](ADR-0048-rear-power-routing-and-nondriving-startup.md)의 Rear 초기 구동에 이어
Front도 정상 command 없이 센서 Actual을 제공하며 준비를 기다릴 수 있게 한다.

## Leaf 시작과 감시

`ActuatorCommandStartup::{Immediate,NonDriving}`을 shared session 계약에 둔다.
SteeringActuator/BrakeActuator와 기존 SIL wrapper의 기본값은 Immediate다.
기존 DriveCommandStartup 이름은 shared enum의 alias로 유지하며 Drive의 동작은 바꾸지 않는다.

NonDriving은 normal command receiver를 아직 시작하지 않는다. Steering/Brake는 Hold를 선택하고
외부 physical model·독립 local sensor로부터 INIT/NoAcceptedInput Actual을 계속 보고한다.
Brake Hold는 압력을 0으로 내리거나 보호 floor로 올리는 명령이 아니다. 주차 제동/차량 정지 보장도 아니다.
Gateway는 기존 Idle 상태에서 대기한다. 가짜 zero command/normal sequence/counter를 만들지 않는다.

센서 freshness/identity/range와 제어 주기·clock 감시는 계속한다. Current fixture의 sensor age20 ms·
sample/control gap30 ms와 주기10 ms는 유지한다. 명령이 없다는 이유로 이 검사를 유예하지 않는다.
각 Leaf는 command ingress·prepare/complete·arm·current sample 조회의 monotonic 시각을 함께 기록한다.
Trusted 새 INIT도 마지막 관측보다 과거로 돌아갈 수 없다.

`can_arm_normal_commands`는 clock 및 오래된 센서/실행 공백을 검사하며 fault를 latch할 수 있는
preflight다. Fault 없음, 미완료 job 없음, 최신 complete의 new valid acquisition과 미만료 source가
필요하다. 단순 cached publication만으로는 arm하지 않는다. `arm_normal_commands`는 trusted caller만
호출하며 같은 Epoch에서 receiver 감시를 시작한다. 최초 정상 명령 대기80 ms는 이때부터다.
Physics·sensor identity·Actual publication sequence는 reset하지 않는다.

Arm 전 CAN packet은 NotInitialized로 거부하고 receiver/P05/application sequence를 소비하지 않는다.
Arm 뒤에는 source가 arm 경계보다 이전인 packet도 기존 SourceBeforeSession으로 거부한다.
과거 session의 receiver diagnostic history는 NonDriving Actual의 causal/origin이나 current sample로 쓰지 않는다.

## Front 단위의 trusted 연결

`simulation::FrontStartupControl`은 same-host single-owner binding이다. Central의 정상 준비/허가 결정은
caller 책임이다. CAN packet에서 준비를 학습하거나 arm callback을 호출하지 않는다.

1. Front scope와 gateway/Steering/Brake의 동일한 nonzero application Epoch를 확인한다.
2. Gateway Idle과 두 Leaf의 새 센서·fault/clock/period 조건을 모두 preflight한다.
3. Gateway와 두 Leaf를 arm한다. 도중 실패하면 gateway latch와 두 Leaf의 Hold/Protect를 선택한다.
4. 성공 뒤에도 원래 gateway의 독립 root·범위·metadata·expiry/각 write guard와 Leaf 감시는 계속한다.

Leaf preflight는 gateway poll 이전에 수행한다. Poll/arm이 더 나중 시각으로 이미 보호를 전달할 수
있으므로, 직접 보호에는 max(context time, gateway observed time)을 사용하고 그 뒤 gateway 보호를
요청한다. 같은 요청을 과거 시각으로 다시 전달해 원래 sensor fault를 ClockError로 덮지 않는다.

Preflight는 독립 객체 세 개의 transition을 atomic하게 만드는 기능이 아니다.
실패 시 normal path를 닫는 정책이며 실제 CAN 두 frame의 atomic delivery/rollback도 제공하지 않는다.
Wrong scope/Epoch·아직 첫 센서가 없는 준비 미완료는 arm 거부다. 감지된 fault/기존 gateway latch와
commit 실패는 Front 전체 보호다. 보호 ACK는 출력 선택이며 물리 압력 도달/차량 정지 ACK가 아니다.
복구는 각 객체의 명시적 새 INIT다. Gateway INIT 하나로 Leaf를 reset하지 않는다.

## 정상 종료 검토 — 후속 구현

현재 VehicleManagement의 Stopping은 normal_allowed를 내리고 Inhibit/Shutdown을 산출한다.
Active Drive는 Inhibit를 fault로 latch하고 allocator는 normal output을 중단한다. 따라서 이를
전 차량의 정상 감속·정지·전원 종료가 완성된 흐름으로 표시하지 않는다. 이번 변경에서도 유지한다.

다음 구현에서는 단일 coordinator가 fresh stop root에 묶어 다음 책임을 순서대로 연결해야 한다.

- 정상 제어가 살아 있는 동안 양수 추진을 막고 제동/hold를 지시한다. Actual speed·torque·friction 응답으로 정지/유지 조건을 판정한다.
- 정상 receiver를 조용히 끄는 packet 대신 별도 trusted quiesce/handoff를 정의한다. 원래 Epoch/causal root·시각·deadline을 보존하고 센서·critical input 감시는 유지한다.
- 출력 선택 ACK와 실제 torque/current/접점·bus 상태를 구분해 Inhibit→Power 종료를 연결한다. 즉시 contactor open이나 pressure release를 가정하지 않는다.
- 각 단계 입력 상실·deadline 초과·부분 handoff는 기존 protection으로 보낸다. 고장 latch를 정상 종료 성공으로 바꾸거나 INIT로 지우지 않는다.

차량 정지 threshold/dwell·hold calibration과 stop phase budget은 TBD-02/03/06/12다.
현재 외부 speed0 fixture만으로 실제 감속 완료를 검증할 수 없다. 그 수치를 이번에 임의 확정하지 않는다.
실제 stop owner/Leaf handoff·전체 ingress/status/rejoin, remote normal32-byte CAN lease/보호와 DDS·
full workload timing·Target은 후속이다. 검증 범위는 [학습 기록](../learning/m4_front_startup.md)에 둔다.
