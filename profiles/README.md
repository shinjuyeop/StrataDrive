# Compute profile design baseline

Status: Reference 계약 **DEFINED**, tier별 override **PLANNED / TBD-09**.
YAML은 설계용 data이며 loader, schema validator, deployment
command는 미구현이다. `null`은 미결정이며 무제한, 비활성화, default 값을 뜻하지 않는다.
`baseline_profile`은 문서상의 참조이며 자동 inheritance가 구현됐다는 뜻이 아니다.

`m2_drive_fixture`는 [첫 torque 응답](../docs/learning/m2_drive_model.md)의 시험 설정이다.
Command/physical 한계와 normal/zero rate를 구분하고 speed/capability는 unavailable로 둔다.
BMS power limit·permission·local HV gate와 에너지 계산은 아직 통합하지 않았다.
이 fixture를 차량 운행 가능한 Drive runtime이나 실제 회생 가용량으로 해석하지 않는다.

`m2_drive_gate_fixture`는 [Drive local gate/capability](../docs/learning/m2_drive_gate.md)의 후속 설정이다.
필수 원천 limits·trusted Central permission·독립 HV/속도 관측을 검사한다. 방향별 power/torque 한계,
저속 회생 taper, queued goal 축소와 actual 잔여 응답을 구분한다. `eta`는 부하 비례 변환항의 하한 가정이고
fixed reserve는 fixture의 공유 auxiliary/idle 몫이다. 실제 loss map/공유 부하 배분·headroom은 후속이다.
Capability dependency 70 ms는 이 fixture의 명시적 opt-in이며 generic default 30 ms를 바꾸지 않는다.
Central/relay는 독립 fixture다. Actual DC/Battery SOC는 아래 ideal-path·combined circuit component로 연결했고 차량 배분 runtime은 미통합이다.

`m2_drive_energy_fixture`는 [실제 Drive/Battery 에너지 연결](../docs/learning/m2_drive_energy.md)의 설정이다.
Begin actual torque/speed를 ZOH해 motor conversion/copper/idle·별도 auxiliary를 계산한다. Chemical energy는
기존 BatteryModel만 소유하고 motor loss와 battery 저항 heat를 구분한다. 200 W reserve는 실제 idle 50 W와
auxiliary 150 W를 덮으며 실제 장부에는 각 부하를 한 번만 더한다. SOC guard band/finite reaction budget은
이 fixture의 부분 검토이며 shutdown/부품 안전성 보장이 아니다. 이상적 energized HV와 외부 speed를 사용하고
이 ideal-path fixture는 dynamic PowerModel을 실행하지 않는다. RC/접점·capacitor는 별도 `m2_ev_power_fixture`에서 연결하고 vehicle motion은 후속이다.

`m2_battery_fixture`는 [Battery 물리·관측 모델](../docs/learning/m2_battery_model.md)의 독립 시험 설정이다.
50 kWh/400 V와 Rint/lumped thermal parameter는 차량 capacity·chemistry 선택이 아니다.
Actual traction DC와 auxiliary만 입력하고 chemical energy 장부와 independent sensor acquisition을 검증한다.
BMS sensor port와 이상적 HV·실제 RC 회로의 Drive actual DC까지 local component로 연결했다.
차량 배분 runtime은 미통합이며 아래 차량 calibration TBD를 유지한다.

`m2_bms_fixture`는 [BMS 한계·보호 판단](../docs/learning/m2_bms_controller.md)의 시험 설정이다.
방향별 SOC/온도/cell voltage ramp, 독립 hard trip/release band와 acquisition 기반 dwell을 구분한다.
차량 chemistry/제조사 calibration이나 hardware protection 지연을 지정한 값은 아니다.

`m2_power_fixture`는 [Power lifecycle/RC·접점 모델](../docs/learning/m2_power_lifecycle.md)의 시험 설정이다.
BMS local safety gate와 actual contactor/전압/전류를 확인한다. 시험용 저항·시간·잔류 전압 기준을
실차 정격/안전 기준으로 해석하지 않는다. 이 standalone demo는 독립 fixture이며 아래 combined loop에서 Battery와 연결한다.

`m2_ev_power_fixture`는 [실제 회로·Battery 연결](../docs/learning/m2_ev_power_circuit.md)의 설정이다.
OCV/Rint·main/precharge/bleed·DC-link를 함께 풀고 구간 charge/current-square integral을 단일 BatteryModel에 전달한다.
Motor 식은 ideal-path와 공유하지만 auxiliary는 pack-side actual current 0.375 A이고 OFF에도 남는다.
Opening threshold 0.5 A와 Drive reserve 500 W는 이 combined fixture만의 값이며 legacy defaults를 바꾸지 않는다.
50 µs 이하 내부 electrical step은 ECU task 주기가 아니다. Source/dependency·sensor unknown/hold와
internal energy flow를 구분하고 Battery/회로는 함께 commit한다. 실제 Central/Zone/차량 motion·LV sleep은 후속이다.

`reference.yaml`의 ODD/scenario/수치 acceptance/logical rate/state는 **Reference Baseline v0.1**로
정의했다. 값은 engineering starting point이며 실측이나 양산차 기준이 아니다. 먼저 future AI
workload와 보드 조건의 TBD를 고정하고 Thor와 Orin에서
같은 reference를 독립 실행한다. 이후 `thor_premium.yaml`과 `orin_mainstream.yaml`을
별도 실험으로 비교한다. 후보 목록은 적용된 설정이 아니다. Model/hardware에
의존하는 engine은 별도 artifact로 관리하고 공통 model/checksum과 수치 정확도를 추적한다.

2026-10-13 [RG-01 회생제동 확장](../docs/icd/regenerative_braking_design.md)을 현재 설계에
추가했다. YAML의 `design_extensions`는 M0 v0.1 이후의 requirement revision을 구분한다.
Drive timeout은 이전 양·음수 demand를 무효화하는 zero motor torque target으로 개정했고,
`regenerative_braking`에 공통 책임/부호/에너지 단위와 미결정 모델 parameter를 기록했다.
Thor/Orin 공통 reference에 적용할 설계이며 runtime loader/회생 구현/검증 완료가 아니다.

[EV-01](../docs/icd/ev_power_bms_design.md)을 v0.3 requirement extension으로 추가했다.
[ZON-01 v0.5](../docs/adr/ADR-0021-central-coordination-and-parallel-zones.md)은 v0.5 requirement revision이다.
`architecture`는 최종 Front/Rear 두 Zone과 단일 Zone component 검증 단계를 구분한다.
후륜 구동 packaging에서 Central이 차량 관리·배분·session·피드백 집계를 소유하고 Rear는 Drive/BMS를 연결한다.
Central–Zone schema/QoS/clock/rejoin은 TBD-15이며 runtime switch나 배포 구현이 아니다.
`ev_power_bms`의 lifecycle·부호·단위는 설계 의미이며 parameter는 TBD-12/13/14다.
2026-10-14 [BMS wire 초안](../docs/icd/bms_frame_draft.md)에서 BMS control/limit 50 Hz,
power actual/permission 100 Hz, battery 관측 10 Hz를 제안했다. YAML도 이 논리 설계 값을 담는다.
`wire_draft`의 50 ms source/70 ms dependency/80 ms timeout은 후속 측정 대상 시작값이다.
Drive 보조 source/input age config를 분리·시험했다. 기본 30 ms를 유지하고 EV capability input
70 ms는 명시적 opt-in이다. EV codec/receiver와 local vCAN 36개 case를 검사했으며
실제 model/Zone task·cross-node rate/timeout 보장으로 확대하지 않는다.
Trusted coordinator/startup/cross-node budget은 TBD다. 로컬 모델의 셀 전압·온도 극값 입력은
범위로 정했고 threshold/dwell은 TBD-13이다. [BMS 실행 안내](../docs/learning/m1_bms_codec.md)를 참조한다.

`m1_local_can_fixture`는 [영속 Epoch/queue 기술 검사](../docs/learning/m1_session_queue.md)의 설정이다.
Capacity 32/ingress·dispatch 8/polling sleep 1 ms는 local fixture 값이다. 운영 store 경로와
실제 Central coordinator/Zone DDS INIT protocol은 후속이며 이 YAML이 runtime loader나 Target timing 보장은 아니다.

`m2_steering_fixture`는 [첫 조향 응답 모델](../docs/learning/m2_steering_model.md)의 시험 설정이다.
Command/model 각도 범위, rate/delay, control gap과 source-loss hold를 기록한다.
C++ fixture와 값이 일치하지만 YAML loader는 없으며 OEM calibration은 TBD-02/03이다.
[Steering response monitor](../docs/learning/m2_steering_fault_monitor.md)의 physical sensor identity,
healthy rate 0.8..1.2배·residual 여유 0.01 rad·fresh-source confirmation 60 ms와 sensor age/gap 20/30 ms도 기록한다.
센서 캐시는 새 angle Actual로 발행하지 않는다. 이 값은 첫 SIL 설정이며 기계 jam 원인 분리/실차 검출 budget은 아니다.

`m2_brake_fixture`는 [첫 Brake 압력 모델](../docs/learning/m2_brake_model.md)의 설정이다.
정상 delay/rise/fall과 물리 한계, loss 시 increase-only/floor 보호 요청을 기록한다.
정상 plant는 max(actual, floor)까지 유한 rate로 접근한다. [실행 경계](../docs/learning/m2_execution_boundaries.md)처럼
이 물리 응답은 SIL이 계산하며 ECU가 physical getter로 보호 목표를 정하지 않는다.
[Brake monitor](../docs/learning/m2_brake_fault_monitor.md)의 방향별 healthy rate 0.8..1.2배·residual 25 kPa·fresh-source dwell 60 ms,
sensor age/gap 20/30 ms도 기록한다. 보호는 increase-only/floor 요청이며 물리 stuck에도 압력 도달을 보장하지 않는다.
Floor 관측은 fresh sensor로만 보고하고 cached/invalid에서 unknown이다. YAML은 C++ 설정의 기록이며 loader는 없다.
차량 안전 제동 calibration/ABS/pressure→wheel torque는 TBD-02/03/06의 후속 작업이다.

`m3_steering_runtime_fixture`는 [첫 Steering wall-time 실행](../docs/learning/m3_steering_timing.md)의 설정 기록이다.
10 ms release와 별도 5 ms deadline, 2 ms monitor/plant, 120 jobs와 bounded fault 조건은 local Host 실험이다.
차량/Target deadline은 TBD-04이며 YAML loader는 없다. 중간 snapshot 대체와 trace drop을 구분하고 warm-up을 제외하지 않는다.

`m3_multirate_runtime_fixture`는 [후속 다중 주기·CAN 감시](../docs/learning/m3_multirate_runtime.md)의 설정이다.
Brake/Drive/Power 10 ms·deadline 5 ms, BMS 20 ms·deadline 8 ms, RX 2 ms·deadline 3 ms와 release offset/job 수를 기록한다.
독립 감시/plant 2 ms, 6개 critical stream(입력 5개+Drive Actual)의 valid RX threshold 80 ms·검출 <=100 ms와 poll당 8개 budget은 Host 실험 값이다.
Core 최소 호출 guard 1 ms는 runnable period가 아니다. Trusted parent 이력은 CAN 밖의 최근 4개 원천 frame/context에 한정한다.
후속 [비동기 Drive Actual](../docs/learning/m3_drive_feedback.md)은 기존 SourceTimeNs에 실제 취득 시각을 보존해 송수신한다.
RX 1210 jobs는 ECU workload 뒤 20 ms drain tail을 포함하며 monitor/plant tail은 40 ms다.
Cached torque는 unavailable 진단이며 source age·valid RX timer를 갱신하지 않는다. 현재 trace schema 5와 CAN schema 2를 구분한다.
후속 [전체 cycle 계측](../docs/learning/m3_owner_cycles.md)은 enable부터 2440 ms까지 monitor/plant 각각 1221개 기회를 양 trace mode에 기록한다.
Full의 thread CPU clock과 owner 지연 주입을 기록하며 기존 trace 2/3/4는 원래 의미로 읽는다.
[ADR-0039](../docs/adr/ADR-0039-owner-completion-guards.md)는 Host owner deadline 4 ms·1211개 guard slot과
peer 검출/적용 margin 10 ms를 채택한다. 나머지 tail 10개는 관측용이다. 교차 guard와 각자 별도 6-stream 수신 감시가
floor/zero를 latch하며 effective RX loss는 실제 먼저 검출한 observer의 원래 last-valid/detected를 보존한다.
YAML loader·차량/Target timing 보장·실제 Central/Zone runtime은 후속이다.

`m3_cpu_placement_fixture`는 [고정 부하·CPU 배치 비교](../docs/learning/m3_cpu_placement.md)의 protocol 기록이다.
Runtime 7개 owner를 같은 allowed CPU A에 고정하고 부하 없음/A 부하/다른 B 부하를 full/minimal·3회 비교한다.
10 ms마다 7 ms wall busy window를 요청하며 실제 busy CPU 범위와 worker 전체 CPU 시간을 따로 보고한다.
SCHED_OTHER를 유지하고 기존 deadline/ECU 설정을 완화하지 않는다. 실패 run도 유효한 job은 통계에 남긴다.
CPU 번호는 현재 allowed mask/topology에서 선택해 실행 결과에 기록하며 YAML loader나 resource reservation은 아니다.

`m3_owner_placement_fixture`는 [ADR-0037](../docs/adr/ADR-0037-runtime-owner-cpu-placement.md)의
4 layouts × full/minimal × 3회 비교다. Loaded 조건의 부하는 모두 CPU B에 두고 RX만 A로 옮기는 경우,
RX·monitor·plant를 함께 옮기는 경우를 비교한다. 같은 IO map의 무부하 대조군도 둔다.
7-owner CPU map은 실행 시 명시하며 미지정 시 기존 상속 동작을 유지한다. SCHED_OTHER·period/deadline·RX budget은 같다.

`m3_guard_placement_fixture`는 같은 CPU B ECU/부하에서 IO 동반 배치, RX 단독 CPU C 분리, monitor 단독 C 분리와
그 무부하 조건을 비교한다. Allowed A/B/C는 서로 달라야 하며 C도 가능한 다른 physical core를 선택한다.
Full/minimal·layout 순환·모든 실패 보존 규칙은 유지한다. 별도 CPU 배치가 우수하다는 가정은 두지 않는다.

향후 resolved profile에는 모든 TBD의 값, profile hash, source commit, board software
stack, model/input settings, scenario/seed, power/thermal 및 측정 조건을 기록한다.
결과는 단순 속도 순위 대신 요구 충족과 feature trade-off로 평가한다.
[Deployment protocol](../docs/architecture/deployment_architecture.md)과
[timing contract](../docs/requirements/timing_requirements.md)을 참조한다.

각 `null`의 owner/rationale/결정 milestone은 [TBD register](../docs/roadmap.md#open-m0-decisions)에
있다. Reference의 wire/actuator/timing/mapping TBD는 해당 comment ID에 귀속된다.
Tier profile의 모든 `null`과 candidate 선택은 TBD-09(M5 stack, M10 workload, M12 비교)다. `acceptance_thresholds`
override는 공통 SYS requirement를 완화하는 필드가 아니며 추가 compute/resource 목표를
결정할 자리다. 공통 기준 변경은 requirement revision이 필요하다.

20 Hz camera/sensor baseline과 30→20 FPS optimization 후보는 다른 개념이다. 후자는
향후 workload에서 30 FPS를 선택한 경우의 후보일 뿐 현재 Reference 값을 30으로 뜻하지
않는다. 숫자를 바꾸면 요구사항/시나리오/ICD와 함께 revision/rationale을 기록한다.
