# Software architecture and contracts

Status: **Planned / TBD**, M0에서 production code를 구현하지 않는다.
Component ID는 [system architecture](system_architecture.md)의 ID를 사용한다.

## Module responsibility

| Directory | 입력 → 출력 / 책임 |
| --- | --- |
| `central/vehicle_state` | sensor/ego state → timestamp/frame/validity를 갖는 state snapshot |
| `central/perception` | sensor + inference 결과 → object/lane observations; 모델 경계의 integration |
| `central/world_model` | state + observations → planner용 일관된 world representation |
| `central/planner` | Phase A route/waypoint, Phase C의 learned 제안 → candidate trajectory; classical fallback 유지 |
| `central/safety` | trajectory/state/health → 검증된 trajectory, 한계값, 선택된 fallback/system state |
| `central/control` | validated trajectory + ego state → bounded vehicle-level command |
| `central/health` | task, resource, heartbeat → fault monitor 입력 |
| `central/diagnostics` | fault event → DTC lifecycle / system state 결정 |
| `zone/gateway` | DDS vehicle commands ↔ CAN actuator commands/status 및 target feedback bridge 경계 |
| `zone/command_validation` | validity, age, sequence, range, mode 검증 → accept/reject 사유 |
| `zone/control_allocation` | vehicle command → steering/brake/drive demand; 충돌 arbitration TBD |
| `zone/local_safety` | local timeout/fault → 제한 또는 local fail-safe; Central Vehicle Compute 의존 없는 판단 |
| `vecu/common` | task model, bounded queues, watchdog, command integrity, diagnostics 계약 |
| `vecu/steering`, `vecu/brake`, `vecu/drive` | accepted demand → state machine / actuator dynamics → actual feedback |
| `simulation/simple_plant` | CARLA 전 계약 검증용 작은 vehicle model |
| `simulation/plant_adapter` | actual actuator feedback → plant별 actuation mapping |
| `simulation/carla`, `simulation/scenarios`, `simulation/fault_injection` | simulator lifecycle, scenario, 명시적 fault injection |
| `physical_ai/perception`, `physical_ai/learned_planner` | model-specific inference/preprocessing와 temporal model 연구 |
| `physical_ai/export`, `physical_ai/inference` | artifact provenance, export, TensorRT runtime; Central Vehicle Compute가 결과를 소비 |

Safety Supervisor가 Planner와 Classical Controller 사이에서 trajectory를 검사한다.
Classical Controller는 자체 출력 한계를 적용하고 Zone Controller는 수신 command를 독립 검증한다.
어떤 layer도 다른 layer의 검증을 이유로 자신의 timeout/validity 계약을 생략하지 않는다.

## vECU task/communication contract

vECU는 CAN echo simulator가 아니라 MCU/RTOS를 학습하는 Linux software model이다.
실제 RTOS task나 interrupt의 등가 구현/실시간 보장은 주장하지 않는다.

| Task 후보 | 예시 period (TBD) | 계획된 책임 |
| --- | --- | --- |
| Task_10ms_Control | 10 ms | 유효 command snapshot, state update, actuator dynamics/control |
| Task_20ms_Communication | 20 ms | bounded RX/TX queue, command 검증, periodic feedback |
| Task_100ms_Diagnostics | 100 ms | fault aggregation, diagnostic status; 빠른 timeout 검출을 이 task에만 의존하지 않음 |

Periodic Task, RX/TX Queue, Mutex / Synchronization, State Machine, Watchdog,
Command Timeout, Alive Counter, CRC, Deadline Monitoring, Fault State, Actuator
Dynamics를 포함할 계획이다. Queue capacity/overflow, lock 범위/priority inversion,
thread/process model, scheduling policy/priority/affinity는 아직 TBD다.

수신된 bytes는 검사 후 command snapshot에 게시한다. stale, 중복, 순서 오류,
CRC 오류 frame은 valid-command freshness를 갱신하지 않는 방향이다. Alive counter
폭/wrap/restart 정책, CRC coverage/polynomial, startup grace와 rejoin은 CAN ICD에서
확정한다. Timeout 감시는 통신 task 정지 중에도 관측 가능해야 하며 watchdog과
monitor 배치/독립성 및 stop 조건을 설계 검토한다. 이 계약은 아직 구현되지 않았다.

| vECU | Command / dynamics 후보 | Feedback / fault 후보 |
| --- | --- | --- |
| Steering | steering command; rate / acceleration limit, dead time, friction, overshoot, noise | actual steering + validity/time; jam / tracking fault |
| Brake | brake command; pressure buildup, response delay | actual brake pressure + validity/time; stuck / slow-response fault |
| Drive | torque command; torque saturation, motor response | actual torque, speed/RPM + validity/time; over-current / mismatch fault |

Dynamics parameter, sign/unit/frame, noise seed, 초기화와 calibration은 TBD다.
Accepted demand와 actual actuator state를 다른 interface로 유지한다. Simulated current 등의 상태가 없으면 해당 fault는 검증됐다고 주장하지 않는다.

## Autonomous driving / Physical AI sequence

**Phase A — classical first (M8):** CARLA route/waypoint 기반 planner, Pure Pursuit
또는 Stanley lateral controller, Longitudinal PID. 반드시 Zone Controller/vECU를 거친
closed-loop를 먼저 완성하고 재현 가능한 기준 결과를 얻는다.

**Phase B — perception (M10):** pretrained Object Detection, Lane / Drivable Area
Segmentation, Multi-object Tracking을 우선한다. 처음부터 대형 모델 학습 대신
TensorRT deployment / optimization / integration과 accuracy 검증에 집중한다.

**Phase C — learned temporal planner (M11):** 최근 **0.5~1초** ego state history
(speed, yaw rate, steering, lane offset, route curvature, nearby objects)를 사용한다.
GRU 또는 작은 Temporal Transformer가 Future Waypoints, Target Speed, Risk Score를
제안한다. sample rate/history padding, coordinate frame, risk 의미/calibration은 TBD다.

Learned Planner → Suggested Trajectory → Safety Supervisor → Classical Controller
→ Vehicle Command. AI는 actuator command를 직접 생성하지 않는다. Timeout, NaN,
stale history, invalid trajectory 시 Classical Planner fallback을 유지하며 fallback의
입력도 유효하지 않으면 안전 상태 정책으로 넘어간다. [ADR-0004](../adr/ADR-0004-ai-control-boundary.md)
및 [fault architecture](fault_diagnostics_architecture.md)를 참조한다.
