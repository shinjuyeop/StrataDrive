# System requirements — Reference Baseline v0.1 + RG-01 + EV-01 + ZON-01

Status: **DEFINED**, 문서 baseline은 [M0 종료 검토](../m0_baseline.md)에 따른다.
아래 요구사항의 전체 시스템 통합은 **PLANNED**, 전체 verification result는 **NOT RUN**이다.
M1의 Host codec/receiver/SocketCAN 부분 구현·시험과 구분한다.
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
| SYS-EV-xxx | Battery/BMS / power lifecycle / 차량 주행 허가 |

ID는 세 자리 증가 번호로 부여하고 삭제/대체 후 재사용하지 않는다.
M0의 23개 요구사항은 v0.1이다. 2026-10-13 [RG-01](../adr/ADR-0011-regenerative-braking-scope.md)
후속 설계로 **SYS-SAFE-004는 v0.2로 개정**, **SYS-CTRL-008/009와 SYS-SAFE-005는 v0.2로 추가**했다.
후속 [EV-01](../adr/ADR-0014-ev-functional-scope.md)으로 SYS-COM-003/004와 SYS-PERF-002를
**v0.3으로 개정**하고 SYS-EV-001–005를 v0.3으로 추가했다. 그 외 기존 요구는 위 revision을
유지한다. [ZON-01](../adr/ADR-0015-front-rear-zones.md)로 **SYS-ARCH-003 v0.4**를 추가한다.
RG-01/EV-01/ZON-01 runtime verification은 NOT RUN이며 상세 parameter는 TBD다.
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
| SYS-ARCH-003 | The final Reference shall use Front and Rear logical Zones with one vehicle-wide coordination owner, preserve per-source command and feedback metadata across peer routing, and verify independent Zone loss and rejoin. | ZON-01/v0.4; Front 단일 차량 관리·배분, Rear Drive/BMS gateway; peer schema/QoS/clock/rejoin TBD-15; TC-ZON-001/002/003 |
| SYS-ODD-001 | The reference driving scenarios shall remain within the StrataDrive Reference Baseline v0.1 ODD defined above. | 범위 밖 성능 주장 방지; TC-CTRL-002/003/004 |
| SYS-COM-001 | The Zone Controller shall detect Steering vECU feedback communication loss within 100 ms of the last valid feedback reception. | F01; timeout threshold만이 아니라 monitor 지연까지 포함; TC-COM-001 |
| SYS-COM-002 | Receivers shall reject commands with invalid application integrity, sequence or freshness and shall not refresh valid-command age from rejected frames. | CAN application CRC 필수, DDS integrity 방식 TBD-05; TC-COM-002 |
| SYS-COM-003 | Each receiver shall detect loss of a critical command, actual-feedback or BMS/power-status stream within 100 ms of its last valid reception, independently of Central diagnostics. | EV-01/v0.3; 기존 actuator/Central/Host 경로와 critical EV stream 목록(TBD-14)에 적용; TC-COM-001/003/004, TC-EV-002/004 |
| SYS-COM-004 | Feedback bridges shall preserve per-source time, sequence, validity and causal command or model-input identity without making cached feedback or dependent constraints fresh by republication. | EV-01/v0.3; BMS/power/Drive constraint도 Zone 원천/의존 metadata 보존; TC-COM-005, TC-EV-002 |
| SYS-CTRL-001 | The vehicle shall be actuated only through actual Steering/Brake/Drive vECU responses passed to the Plant Adapter. | sensor→Central→Zone→vECU→actual feedback→Plant 경계 필수; TC-CTRL-001 |
| SYS-CTRL-002 | The Plant Adapter shall never substitute vehicle-level or actuator commands for missing, stale or invalid actual feedback. | feedback 상실은 run gate/fault 정책 적용; TC-COM-001/005 |
| SYS-CTRL-003 | The Plant Adapter shall be the only writer applying ego actuation to CARLA. | Planner/Controller/Zone, autopilot, scenario runner의 별도 actuation 금지; TC-CTRL-001 |
| SYS-CTRL-004 | The vehicle shall maintain an absolute steady-state speed tracking error of at most 1 km/h in each eligible constant-speed window. | 평균으로 spike를 숨기지 않고 window 내 max absolute error 평가; TC-CTRL-002/003/004 |
| SYS-CTRL-005 | The vehicle shall achieve a 95th-percentile absolute lateral cross-track error of at most 0.3 m on each reference route. | ego reference point와 reference path 기준; TC-CTRL-002/003/004 |
| SYS-CTRL-006 | The vehicle shall achieve a 95th-percentile absolute heading error of at most 3 deg on each reference route. | path tangent 대비 wrapped angle; TC-CTRL-002/003/004 |
| SYS-CTRL-007 | The vehicle shall not exceed the time-aligned validated target speed by more than 10 percent while that target is positive. | S03의 감속 request와 연속 target profile 구분; TC-CTRL-002/003/004 |
| SYS-CTRL-008 | The Zone shall allocate braking between regenerative Drive torque and friction Brake pressure within validated actuator limits, using a common wheel reference and actual-response information. | RG-01/v0.2; capability/응답 전환/저속 hold calibration TBD-02/03/06; TC-REG-001/002/003 |
| SYS-CTRL-009 | Recovered energy shall be computed from valid actual regenerative mechanical power and bounded by mechanical energy and charge acceptance, excluding friction-brake energy. | RG-01/v0.2; 단순 모델 효율/적분 오차 TBD-02/03; TC-REG-005 |
| SYS-AI-001 | The learned planner shall provide trajectory, target speed and risk outputs through safety validation and classical control, with classical planner fallback on invalid or late AI output. | fallback 입력도 무효면 보호 상태; M11 계약, TC-AI-001 |
| SYS-SAFE-001 | The system shall transition to DEGRADED or FAIL_SAFE when a safety-critical actuator interface is unavailable. | 상태만으로 정지 보장하지 않음; fault별 정책은 safety 문서; TC-SAFE-001 |
| SYS-SAFE-002 | Components shall start in INIT, inhibit normal driving output until required input and feedback checks pass, and require explicit reinitialization before recovery to NORMAL. | 초기화/복구 gate, 자동 즉시 복귀 금지; TC-SAFE-002 |
| SYS-SAFE-003 | The Zone Controller and each vECU shall execute their local timeout protection without waiting for Central communication or diagnostic acknowledgement. | F04 및 상위 process 단절; TC-COM-004 |
| SYS-SAFE-004 | On drive-command timeout, the Drive vECU shall invalidate the old positive or negative demand and select a local zero motor torque target. | RG-01/v0.2; actual torque는 dynamics에 따라 변함; 양·음수→0 ramp/응답 deadline TBD-03; TC-COM-003 |
| SYS-SAFE-005 | The Zone shall inhibit new regenerative demands when capability is invalid or stale, distinguish valid zero capability from critical actual loss, and report unmet braking demand with local protection outside the validated envelope. | RG-01/v0.2; 마찰제동 한계/전환 budget TBD-03/06; critical loss 정책 유지; TC-REG-002/004 |
| SYS-DIAG-001 | The system shall trace monitored faults through fault events, DTC records and system state transitions. | local action과 기록 경로 분리; DTC 통합 M9, TC-DIAG-001 |
| SYS-PERF-001 | The system shall measure end-to-end control latency and report Mean/P95/P99/Max, sample count and deadline misses. | endpoint/clock/causal path는 timing 문서; M0 실측 없음; TC-PERF-001 |
| SYS-PERF-002 | The Reference Config shall define sensor/plant and planner rates of 20 Hz, controller rate of 50 Hz, and Zone and Steering/Brake/Drive vECU control rates of 100 Hz, and shall specify BMS/power task and publication rates before their execution tests. | EV-01/v0.3; 기존 수치는 유지, 새 rate/source-age TBD-14; logical 설정과 deadline 구분; TC-PERF-002, TC-EV-002 |
| SYS-PERF-003 | Timing and timeout evidence shall identify its clock domain and distinguish simulation time from elapsed monotonic wall time. | 서로 다른 clock 직접 차감 금지, pause/reset 별도 처리; TC-PERF-001/002 |
| SYS-EV-001 | The system shall verify modeled power readiness and fresh required health before enabling normal driving, keep power lifecycle distinct from severity state, and verify actual power response during startup and shutdown. | EV-01/v0.3; 요청≠actual/READY≠NORMAL, local drive permission과 INIT gate; TBD-12; TC-EV-001/004 |
| SYS-EV-002 | The BMS vECU shall report modeled battery state, charge/discharge limits and actual power status through the Zone with source and dependency validity, time and identity; consumers shall distinguish valid zero limits from unknown or stale data. | EV-01/v0.3; schema/critical stream/rate/source age TBD-14; TC-EV-002/003 |
| SYS-EV-003 | Drive shall enforce fresh battery charge/discharge constraints and local drive permission together with validated motor limits, while Zone allocation accounts for the resulting availability and actual response. | EV-01/v0.3; W/N·m 변환 명시, zero/low speed와 local response TBD-03/13; TC-EV-003, TC-REG-001/002/004 |
| SYS-EV-004 | BMS, Drive and Zone shall execute fault-specific local protection for unavailable critical EV inputs or power faults without Central diagnostic acknowledgement and shall require explicit reinitialization and power checks for recovery. | EV-01/v0.3; 고장별 reaction matrix/응답 budget TBD-12/14; 일괄 즉시 contactor open을 가정하지 않음; TC-EV-002/004 |
| SYS-EV-005 | A single battery-model owner shall update energy and SOC from valid actual model power using a declared loss/load model and simulation clock, preserve energy balance within a fixed tolerance, and expose invalid samples or limit violations. | EV-01/v0.3; command/limit 적분·마찰 회수·이중 집계 금지, capacity/sign/full/empty/오차 TBD-13; TC-EV-005, TC-REG-005 |

## Change control

수치와 logical rate는 M3 timing, M6 simple plant, M7 CARLA mapping, M8 control tuning
증거로 변경할 수 있다. 실패 결과를 그대로 보존하고 결과에 맞춰 threshold를 조용히
바꾸지 않는다. 모든 변경에 아래 행을 추가하고 requirement 문장, profile, ICD,
scenario/test, traceability를 함께 갱신한다. 이전 결과는 이전 revision에 귀속된다.

| Revision / date | 대상 | 변경 / rationale | 영향 / 근거 | Review |
| --- | --- | --- | --- | --- |
| v0.1 / 2026-09-22 | 기존 8개 및 신규 15개 requirement | 사용자 지정 ODD/rate/acceptance와 계층 분리를 M0 계약으로 확정; 기존 SYS-COM-001의 100 ms 예시를 검출 상한으로 정의 | M0 문서 검토; runtime evidence 없음; 전체 traceability/profile | M0 exit review 참조 |
| v0.2 / 2026-10-13 | SYS-SAFE-004 개정, SYS-CTRL-008/009·SYS-SAFE-005 추가 | RG-01 회생제동 포함; zero-propulsive target → 양·음수 motor torque의 zero target; 가용량 기반 배분/실제 회수 에너지 계약 추가 | Owner: project owner; 사용자 범위 결정과 ADR-0011, Result 없음(설계 단계); TC-COM-003 재시험 및 TC-REG-001–005, M1/M2/M4/M6/M7 | 포함 범위 ACCEPTED; 상세 parameter/실행 검증 후속 |
| v0.3 / 2026-10-13 | SYS-COM-003/004·SYS-PERF-002 개정, SYS-EV-001–005 추가 | EV-01 BMS/power/vehicle management 포함, actuator별 bridge → EV 원천/의존 status 보존; 기존 20/50/100 Hz는 유지하고 BMS rate를 별도 결정 | Owner: project owner; ADR-0014, Result 없음(설계 단계); TC-EV-001–005 및 기존 TC-COM/REG/PERF 영향 검토, M1–M7/M9; 당시 다중 Zone 채택은 별도 TBD-15 | 포함 범위 ACCEPTED; 상세 설계/학습자 review PENDING, runtime NOT RUN |
| v0.4 / 2026-10-13 | SYS-ARCH-003 추가; 기존 COM/SAFE/EV peer coverage 연결 | ZON-01 최종 Front/Rear Zone 및 Front 단일 coordinator 채택; 원천 freshness/독립 loss/rejoin 유지 | Owner: project owner; ADR-0015, Result 없음(설계 단계); TC-ZON-001–003, M4/M5/M6/M7/M9/M12; TBD-15 protocol은 남음 | 두 Zone·책임 배치 ACCEPTED; protocol review PENDING, runtime NOT RUN |

향후 행에는 이전 값→새 값, 실험 Result ID(없으면 그 이유), 결정 owner, rationale,
영향받는 test와 재시험 milestone을 반드시 기록한다.

[Traceability](../test-plan/traceability.md)가 Requirement → Component → Interface →
Scenario/Test → Future Result의 단일 연결점이다. 미결정 parameter는
[roadmap TBD register](../roadmap.md#open-m0-decisions)로 관리한다.

ZON-01에서 SYS-COM-003/004와 SYS-SAFE-002/003의 기존 의무를 peer-Zone 경로에도
적용한다. 문장/revision은 유지하며 TC-ZON-002/003으로 추가 coverage를 연결한다.
