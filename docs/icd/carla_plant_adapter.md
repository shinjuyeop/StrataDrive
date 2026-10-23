# CARLA Plant Adapter / Vehicle Plant Interface 초안

2026-10-23, `m7-plant-draft-v1`. **M7-0 의미 계약 결정 / backend·수치 calibration 미확정 / 구현 NOT RUN**.
기존 [공통 ICD](interface_overview.md), [시간 계약](../requirements/timing_requirements.md),
[owner-wire](owner_wire_v1.md), [M6 종료 범위](../m6_exit_review.md)를 변경하지 않는다.
환경 근거와 실행 gate는 [M7 사전 점검·시험 계획](../test-plan/m7_carla_preflight.md)에 둔다.

## 1. 경계와 단일 소유권

정상 경로는 Central → Front/Rear Zone → vECU → Actual CAN/P05 → 담당 Zone →
Central feedback bridge → Plant Adapter → CARLA다. 물리 actuator 모델은 ECU 밖에서
응답을 생성하고 vECU가 이를 센서로 취득·검증해 Actual로 보고한다. 기존 physical bus의
값을 CARLA로 바로 보내 이 반환 경로를 생략하지 않는다. Command, target, permission,
capability, `get_control()`의 마지막 설정값은 실제 actuator feedback이 아니다.

Plant Adapter만 ego actuation API에 접근한다. Controller/AI/Zone/ScenarioRunner/
Traffic Manager/manual_control/ROS ego control은 writer가 될 수 없다. Autopilot은 끈다.
spawn/destroy/INIT pose 설정은 orchestration lifecycle이며 정상 주행 제어가 아니다.
fault injection도 명령/센서/actuator 모델에 적용하며 독립 ego writer를 만들지 않는다.
single writer는 CARLA 서버가 인증해 주는 기능으로 가정하지 않는다. 전용 서버·클라이언트
구성, adapter 내부 owner token, API 호출 감사로 통제하고 외부 무허가 client 배제는 실행
환경 gate다. 별도 client가 직접 API를 부르는 것을 Python wrapper만으로 막았다고 주장하지 않는다.

| 상태/계산 | M7 책임 | 중복 금지 / 미결정 경계 |
| --- | --- | --- |
| 세션·배분·보호 | 기존 Central/Zone/vECU | 실제8-role INIT/ACK/RunLease/arm·expiry·CAN/P05 보존 |
| actuator delay/rate/saturation/fault·actual 센서 | 기존 SIL actuator physical owner + vECU 보고 | CARLA adapter에서 같은 delay/ramp를 다시 적용하지 않음 |
| 차량 질량·관성·타이어/노면·pose/속도 | CARLA만 | CARLA run에서 SimpleVehicle 및 VehicleEvModel의 motion step을 함께 돌리지 않음 |
| CARLA engine/gear/clutch/steering filter | backend 적합성 검토 대상 | 기존 wheel actual에 engine response를 중복하지 않는 설정/저수준 API 입증 전 정상 apply 차단 |
| battery/SOC·HV/접점·전기 손실 | 하나의 EV physical owner | CARLA와 별도 SOC 적분 금지; vECU가 physics를 소유하지 않음 |
| motor/friction work | 검증된 CARLA interval telemetry → 단일 energy bridge | torque·wheel rotation의 같은 구간 work만 전달; 회생과 마찰을 별도 장부로 보존 |

현재 [PhysicalOwner](../../simulation/runtime/m4_owner_network.cpp)는 actuator/차량/EV를
한 경로로 실행한다. 위 분리는 후속 opt-in backend 작업이며 M6 코드를 이번에 바꾸지 않는다.
`VehicleEvModel::step`을 CARLA와 병행하거나, CARLA 속도로 M6 pose를 다시 적분하지 않는다.
50ms end speed를 10ms/2ms 센서나 과거 speed로 소급할 수 없다. [M6 energy port](vehicle_energy.md)의
구간·dependency·원자적 commit 전제는 CARLA에서 아직 충족되지 않는다. 외부 서버 tick은
로컬 candidate처럼 rollback할 수 없으므로 실패 interval을 invalid로 남기고 다음 tick을
막는다. M6의 에너지 오차 예산/230ms 응답 수용을 CARLA에 승계하지 않는다.
wheel work를 신뢰성 있게 얻기 전 CARLA EV energy는 **unavailable**, SOC/회생 수용은 NOT RUN이다.

## 2. Simulator 독립 Vehicle Plant Interface

아래는 의미 schema이며 C++ ABI, Python class, 새 wire layout 확정이 아니다.
기존 IF-HOST-ACTUATOR/IF-HOST-SENSOR/IF-HOST-EV-STATUS를 구현할 port로 검토한다.
CAN/P05나 owner-wire v1을 수정하지 않는다. CARLA handle/type은 backend 안에만 둔다.

| Port | 입력/출력 | 계약 |
| --- | --- | --- |
| describe/configure | backend version, geometry/calibration ID+hash, capabilities | INIT 전 읽기/고정. `supports_signed_wheel_torque`, true substep observation, energy fidelity 등 미지원은 명시 |
| accept_actual | `ActualBundle`: steering rad, signed drive Nm, friction Pa의 독립 sample | typed actual만 수용. 값이 같아도 command 타입/원천은 거부 |
| prepare_step | run/plant epoch, expected frame, begin/end, ActualBundle | age/clock/identity/coverage/calibration 검사 → prepared 또는 이유 있는 reject; actuation하지 않음 |
| commit_step | prepared token + tick-owner 허가 | adapter만 apply, orchestrator만 tick. 동일 token/frame 중복 apply 금지. tick RPC timeout은 무조건 재시도하지 않고 실제 snapshot과 대조 |
| observe | `VehicleState`, `SensorPacket[]`, `PlantHealth`, 선택 `IntervalWork` | 관측/추정/GT 구분, 원래 acquisition 보존; incomplete는 zero가 아닌 unavailable |
| pause/reset/close | lifecycle 요청 | pause containment; reset은 새 run/plant epoch·명시적 INIT, close는 sensor stop→자신의 actor destroy·설정 복원 |

각 sample은 `schema_version, run_id, plant_epoch, source_id, source_epoch, sequence,
clock_domain, acquisition_time, oldest_dependency_time, validity, reason, frame_id`를 갖는다.
actuator에는 기존 application Epoch/role/CAN identity/원래 source·parent·origin·expiry 및
수신 검증 provenance를 함께 보존한다. `source_id`는 trusted configuration의 role/plant/sensor
인스턴스에 바인딩하며 payload의 자기 선언만 신뢰하지 않는다. CARLA actor ID는 episode 안의
식별자일 뿐, ECU authority가 아니다. bundle 번호·bridge receive/publish 시각은 별도 필드다.

- `validity`: valid / unavailable / stale / invalid; reason은 missing, wrong-source, old-epoch,
  replay, future, clock, nonfinite, out-of-range, skew, expired, calibration, coverage, overflow 등.
- 새 source sequence·취득 시각은 단조 증가. 동일 sample 재사용은 원래 값·시각·dependency가
  모두 불변이어야 하며 valid-RX나 acquisition cursor를 갱신하지 않는다. wire counter wrap은
  기존 수신부 규칙을 따르고 adapter 자체 sequence 소진은 새 epoch를 요구한다.
- 각 actuator의 age/state/quality를 따로 검사한다. 부분 bundle을 0으로 채우지 않는다.
  missing/NaN/무효/출처 불명은 apply와 다음 driving tick을 막는다. command fallback 없음.
- M6 입력 age30ms/skew10ms는 [SimpleVehicleConfig](../../simulation/vehicle/simple_vehicle.hpp)의
  모델 한계다. M7 draft의 보수적 admission 상한으로 유지하며 기존 stream의 더 짧은
  expiry/지원 조건이 우선한다. CARLA 50ms interval 전체를 허용한다는 뜻은 아니다.

## 3. 물리량 변환과 calibration gate

[CARLA 0.9.16 API](https://carla.readthedocs.io/en/0.9.16/python_api/)의 VehicleControl은
steer[-1,1], throttle/brake[0,1]이며 Nm/Pa 직접 입력이 아니다. wheel max steer는 deg,
radius는 cm, max brake torque는 Nm다. engine torque curve는 wheel aggregate torque가 아니다.
Ackermann speed/acceleration 제어는 별도 제어기를 추가하므로 actual-only 대체 경로로 채택하지 않는다.

| 원천 actual | 후보 mapping / 정해진 의미 | 아직 필요한 근거 |
| --- | --- | --- |
| Steering δ(rad), 좌회전+ | `steer = inverse_steering(-δ, speed, geometry, calibration)` | 좌우 road-wheel→equivalent angle, 속도별 steering curve, tire/geometry와 포화 범위. 단순 δ/상수 확정 금지 |
| Drive T(Nm), 전진 구동+ | `throttle = inverse_drivetrain(T, wheel_speed, gear, calibration)` | engine/gear/differential 손실·inertia·zero-throttle drag를 포함한 wheel 기준 역변환. T/300 같은 M6 fixture 재사용 금지 |
| Drive T<0, 전진 회생 | signed wheel torque backend 우선 검토; 기본 API는 `brake_regen_equivalent` 후보 | reverse=true로 음수 torque를 구현하지 않음. 제동 등가 근사만으로 회생 에너지 검증했다고 주장하지 않음 |
| Brake P(Pa), 마찰만 | `Tfriction = calibrated_pressure_to_wheel_torque(P)`, inverse brake mapping | aggregate 계수·차륜 배분·max brake torque readback·정적 hold/저속 특성. M6 0.001Nm/Pa는 CARLA calibration 아님 |

기본 brake API를 사용하는 제한적 motion 근사 후보는 음수 motor torque의 등가 제동과
friction torque를 **한 번만 합산**한다. 각 원천 기여는 장부에서 분리하고 saturation/residual을
보고한다. 양수 drive와 마찰이 동시에 있을 때 API가 요청한 양쪽 실제 힘을 재현하는지도 gate다.
포화로 입력을 몰래 잘라 정상처럼 보고하지 않으며 backend capability 부족은 reject한다.
회생을 CARLA friction loss로 적용하면서 배터리에도 같은 에너지를 회수한 것으로 세지 않는다.
기본 API가 필요한 충실도를 못 내면 저수준 wheel-force/torque 연동을 후속 검토한다.
`set_target_velocity`, 반복 teleport, 두 번째 physics plant로 우회하지 않는다.

calibration artifact는 vehicle blueprint/map·CARLA build, physics readback, 단위/부호,
geometry, 곡선/유효 범위, 데이터·식별 방법, 검증 잔차/허용 오차, revision/hash를 포함한다.
계수·허용 오차는 **TBD-02/03/07**. M7-1에서 geometry를 읽는 것은 calibration 완료가 아니다.

## 4. 좌표계와 센서 계약

프로젝트는 x forward/y left/z up, yaw 좌회전+, rear-axle center 기준이다.
CARLA/UE는 x forward/y right/z up이며 센서 frame/time 의미는
[공식 센서 문서](https://carla.readthedocs.io/en/0.9.16/ref_sensors/)를 따른다.
CARLA world를 프로젝트 map으로 반사하는 기준은 `S=diag(1,-1,1)`:
`p_project=S*p_carla`, `R_project=S*R_carla*S`, yaw는 planar 경우 `-deg*pi/180`이다.
속도/가속도는 S, 각속도 같은 axial vector는 `det(S)*S`를 적용하고 deg/s→rad/s 변환한다.
원점·map ID를 manifest에 고정한다. rear axle 위치는 actor origin/COM과 같다고 가정하지 않고
검증된 `T_actor_rear_axle`로 변환한다. sensor extrinsic도 동일 기준으로 합성한다.
body 속도는 회전행렬 역변환으로 얻으며 `speed/radius`는 no-slip 추정이지 실제 wheel 센서가 아니다.

| Stream | 초기 계약 | 확장/금지 사항 |
| --- | --- | --- |
| RGB front | camera ID, frame, simulation timestamp, arrival monotonic, width/height/stride/encoding, intrinsics/extrinsics revision | CARLA BGRA8 원본과 AI용 RGB8 변환을 구분; 원본 timestamp 유지 |
| Semantic Segmentation GT front | RGB와 같은 pose/FOV/resolution·frame key, raw class ID 및 label-map version | 별도 training/evaluation channel/storage; palette image를 class ID로 쓰지 않음 |
| Vehicle State | 해당 WorldSnapshot/ActorSnapshot의 pose, velocity, acceleration, angular velocity·frame/time | 실제 wheel torque/pressure/angle을 차량 속도·마지막 control로 합성하지 않음 |
| 향후 multi-camera/object/BEV/temporal | sensor ID 배열, frame별 completeness mask, source frame 목록, 모델·calibration ID, uncertainty | array index를 camera identity로 사용하지 않음. derived timestamp와 oldest dependency 분리 |

GT topic/파일/포트는 inference runtime 구독 목록에서 제외한다. 객체 GT·semantic GT를
online perception output으로 대체하지 않는다. AI가 받는 관측 RGB/state와 학습 label은
별도 schema/접근 경계이며 실제 분리 검증은 M7-1/M10이다. Temporal history는 run/epoch와
frame gap을 검사하고 reset 시 비운다. 보간/추정 결과는 `estimated` provenance로 별도 전달하며
현재 Drive의 measured input으로 승격할 수 없다.

RGB/GT는 `(run_id, plant_epoch, frame, sensor_id)`로 join한다. callback 도착 순서가 capture
순서라는 가정은 금지한다. GPU camera의 frame 지연은 공식 [synchrony 문서](https://carla.readthedocs.io/en/0.9.16/adv_synchrony_timestep/)에도 명시돼 있다.
bounded queue·대기 시한·누락 mask를 사용하고 가장 가까운 frame으로 대체하지 않는다.
M7-1은 수집 전용 bounded window로 지연 frame을 join한다. startup/drain frame도 누락 통계에
남기며 별도 분모로 보고한다. 주행 모드에서 필수 input 만료/미완성이면 다음 driving tick을
보류한다. GT-only 누락은 dataset sample을 invalid로 만들며 online 주행 입력이 되지는 않는다.

## 5. Clock, 50ms tick과 freshness 충돌

**결정:** synchronous_mode=true, fixed_delta_seconds=0.05, 단일 Host orchestrator가 tick을
소유한다. physics substepping은 max delta0.01s/max steps10 후보로 설정·readback하여
`fixed_delta <= max_substep_delta * max_substeps`를 확인한다. 이것은 서버 내부 적분이며
Python에서 10ms 측정을 받거나 10ms마다 actuation할 수 있다는 증거가 아니다.
ScenarioRunner는 M7-1 기본 실행에서 제외하며 추후 passive 연동 또는 명시적 tick owner
위임 중 하나만 선택한다. `apply_batch_sync(..., do_tick=True)`의 숨은 tick도 금지한다.

Controller20ms, Zone/vECU10ms release grid는 유지한다. functional replay의 10ms quantum
순서는 새 관측 수용→due Controller/기존 Central 배분→기존 Front/Rear 전달·Leaf 작업→
physical actuator 응답/Actual 반환→adapter validation이다. 기존 owner-wire settle/ACK와
Front/Rear 전송 순서를 생략하지 않는다. 20ms Controller 위상은 50ms frame마다 재시작하지
않으므로 0,20,40,60,80,100ms에 release된다. 이 순서는 미래 scheduler 설계이며 기존
Host wall-time loop를 한 번의 50ms sleep으로 바꾸거나 5회 catch-up했다고 간주하지 않는다.

Driving step은 관측 frame n 뒤 각 원천의 실제 Actual을 수용·검사하고, adapter apply 완료를
확인한 뒤 owner가 한 번 tick하여 n+1 snapshot을 확인한다. 해당 interval의 유효성/인과성이
입증되어야 한다. `apply` RPC 성공과 물리 응답 완료는 다르며 result에 두 시각을 구분한다.

### 20Hz state와 Drive30ms — 현재 차단 사유

실제 코드 [DriveController](../../vecu/drive/drive_controller.cpp)는 local source와 oldest dependency
각각 age<=30ms를 요구하며 config>30ms를 거부한다. [DriveReceiver](../../interfaces/drive/drive_receiver.cpp)도
wheel source30ms를 검사한다. EV capability dependency70ms는 별도 계약이며 이 문제를 해소하지 않는다.
M6 MIL의 speed60ms도 실제 Drive에 적용할 수 없다.

시각0에 측정하고50ms에 다음 state가 생성되면, 10ms task의 age는0/10/20/30/**40**ms다.
지연이 전혀 없어도40ms release는 stale이다. 30ms는 `>` 비교 기준 경계일 뿐 전송 margin이
없고 실제 wall 지연은 더해진다. `get_velocity()` 재호출, 100Hz 재발행, sequence 증가,
도착 시각으로 restamp, 미래50ms sample을40ms에 배치하는 방법은 해결이 아니다.

| 해결 후보 | 판정 / 다음 확인 |
| --- | --- |
| 50ms world tick 안 실제 physics substep에서 wheel 관측·ECU exchange·Actual apply barrier 제공 | **요구사항 보존 방향의 우선 조사 후보**, 미구현/미입증. 같은 CARLA dynamics의 실제 substep 원천, 10ms causal exchange와 transport/age budget 모두 필요. 50ms 완료 후 과거 substep 묶음을 받는 것만으로는 live Drive freshness 해결 불가 |
| 10ms world tick + camera/state export50ms | 기술 대안이나 이번50ms fixed tick 조건 변경이므로 미채택; 별도 requirement revision 없이는 사용 불가 |
| predictor/독립 빠른 wheel model | 관측 보간·중복 dynamics/추정치 계약 변경이므로 현재 measured Drive 입력 대체로 미채택 |
| 30ms→60ms 완화 / 캐시 restamp | 금지. 코드/config 변경 없음 |

추가로 M6 actual age30ms·SimpleVehicle max step20ms와 native2ms/4ms guard는50ms hold로
대체할 수 없다. tick 직전에 fresh여도 interval 중간에 새 보호/Actual이 생길 수 있다.
한 Actual을50ms 내내 유효하다고 간주하지 않는다. 위 substep 연동은 입력 관측뿐 아니라
**같은 구간 실제 actuation 갱신과 protection 반영**까지 입증해야 한다. 원래20ms transport
envelope는 command lifetime과 다르므로 단순히50ms로 늘리지 않는다.

따라서 stock Python API만으로 기존 runtime 정상 주행 연결은 **BLOCKED**다. M7-1은
NON_DRIVING 센서 수집·의도적 stale 거부를 먼저 수행한다. 이 분리는 해결 완료나 freshness
예외가 아니며, 다음 주행 gate는 TBD-04/07의 causal substep 설계/검증으로 남긴다.

### 시간 영역·pause/reset

CARLA `frame/timestamp.elapsed_seconds`는 simulation clock이다. 원래 double seconds와
명시적 반올림한 ns를 함께 보존한다. M7-1 tick 검증 tolerance1µs는 부동소수 비교용이며
source-age 여유가 아니다. callback arrival/receive/apply/RPC 시작·끝은 Host CLOCK_MONOTONIC.
UTC는 run label에만 사용한다. 두 clock을 직접 빼거나 nominal50ms를 wall50ms라고 주장하지 않는다.

기존 owner-wire Host는 공통 kernel monotonic·zero offset/uncertainty다. CARLA sim timestamp를
그 domain으로 단순 라벨 교체하지 않는다. functional replay는 별도 simulation clock 모드로
고정하고 wall-time100ms 검증으로 세지 않는다. wall 연결용 acquisition mapping/불확실성
예산과 Target sync는 미확정이며, bridge 도착 시각을 acquisition으로 쓰지 않는다.

pause 시 tick만 멈추고 wall monitor/통신 timeout은 계속한다. 기존 latch/age는 보존한다.
simulation-clock replay의 logical age 정지는 모드로 명시한다. resume은 stale sample으로
NORMAL 복귀하지 않고 해당 기존 재가입/INIT를 요구한다. reset은 새 run/plant epoch,
센서 queue·pending apply·temporal history 폐기, actor handle 재바인딩, ECU의 새 trusted
application Epoch/전체 INIT/arm으로 연결한다. ECU 단독 재가입은 CARLA world를 reset하지 않는다.
snapshot 확인이 불가능한 RPC timeout·부분 apply는 ambiguous로 기록하고 추가 tick을 막는다.
containment는 시뮬레이션 진행 중단이며 물리 차량 정지/안전 성능의 증거가 아니다.

## 6. 결정과 미결정

**결정:** actual-only 경로·단일 actuation writer,50ms synchronous 단일 tick owner,
20/10ms 기존 rate·freshness/권한 보존, 중복 motion/actuator/energy 금지, metadata/좌표 의미,
GT 격리, pause/reset containment, M7-1 비주행 범위.

**미결정:** 실행 확인한 server/client artifact, vehicle/map/geometry와 역변환 calibration,
substep 양방향 연동 가능성·clock mapping·interval validity, energy telemetry/원자적 실패 처리,
Host–Target transport/배치, M10 AI shape/history. 소유자·gate는 기존 TBD-02/03/04/07/09
(energy는 기존 TBD-13)이며 [로드맵](../roadmap.md)에 연결한다. 이번 문서는 주행 통합 승인이나
interface binary freeze가 아니다.
