# CARLA Plant Adapter / Vehicle Plant Interface 초안

2026-10-27, `m7-plant-draft-v15`. **native Actual→CARLA·solver work→단일 EV 기능 연결 한정 검증 / 전체 정상 주행 미수용**.
[시간 계약](../requirements/timing_requirements.md)의 M7 world/state 주기는 M7-1d 사용자 승인에 따라
50→10ms로 개정했다. M7-1f는 별도 opt-in functional clock 검증이며 wall 계약 개정이 아니다.
기존 [공통 ICD](interface_overview.md), [owner-wire](owner_wire_v1.md),
[M6 종료 범위](../m6_exit_review.md)의 통신·안전·물리 수용 계약은 유지한다.
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

| 원천 actual | 기본 package에서 검토한 mapping (미채택) | 아직 필요한 근거 |
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

### M7-1i — 직접 wheel effort 확장안

[공식 소스·설치 API 조사 및 오프라인 시험](../test-plan/evidence/m7_carla_1i/README.md)에 따라
기본 `VehicleControl`의 throttle 역변환을 정상 연결의 구현 방향으로 채택하지 않는다.
선행 Actual은 wheel torque인데 기본 backend는 engine/clutch/gear 상태를 추가한다.
현재 공개 관측만으로 이를 정확히 역변환하거나 중복 응답을 없앴다는 근거가 없다.
**우선 구현 후보는 PhysX `PxVehicleNoDrive`를 노출하는 별도 CARLA 서버 확장**이다.
이는 엔진 없는 suspension/wheel/tire plant를 제공하지만 설치된0.9.16 Python API에는
직접 effort setter가 없다.1j에서 source build 작업은 승인 범위가 되었지만 실제 서버 구현·빌드·차량 수용은 미완료다.

| 입력 | 확장 backend에 전달할 SI 값 / 설계 법칙 | 미결정 또는 필요한 검증 |
| --- | --- | --- |
| equivalent Steering Actual δ, 좌+ rad | 이상 Ackermann: `δL=atan2(L tanδ,L−W tanδ/2)`, `δR=atan2(L tanδ,L+W tanδ/2)`; CARLA 우+ 기준은 `−δL,−δR`, rear0 | 실제 local wheelbase L/front track W, 휠 순서·축 부호·최대각 readback과 실제 회전 검증. 스케일·속도 필터·추가 지연 없음 |
| aggregate Drive Actual T, signed Nm | 제안 EV 모델은 이상적 open differential: rear 각각 `T/2`, front0. 양·음수 모두 motor 입력에 유지 | stock mkz drivetrain 재현이 아닌 명시적 모델 법칙. 원래 rear 평균 ω와 `ΣTiωi=T(ωRL+ωRR)/2`가 일치. torque vectoring은 별도 work port 개정 필요 |
| Brake Actual P, Pa | 근거 있는 `P→[TFL,TFR,TRL,TRR]` 단조 table의 구간 선형 보간; 전부 nonnegative friction Nm | 실제 유압·패드·디스크 데이터 또는 명시적으로 수용한 가상 brake 모델 필요. max brake800Nm readback만으로 P→Nm 식별 불가. 기본 계수 없음 |

`tests/integration/carla/m7_1i`는 위 수학만 구현한 **test-only prototype**이다.
합성 geometry/table은 오프라인 test vector이며 차량 calibration artifact가 아니다.
table 누락/비정상·입력/휠 한계 초과·불가능한 조향 기하는 거부하고 clamp/외삽하지 않는다.
원래1c Actual/P05 boundary 뒤 fake backend로만 검사하며 `CarlaDriving`은 계속 Disabled다.
순수 함수의 double 인자 자체는 Actual provenance 증명이 아니므로 runtime 입구로 노출하지 않는다.

CARLA plugin 경계까지 SI를 보존한다. UE kg/cm/s 내부에서만 torque를 `Nm×100²`로 바꾼다.
이는 단위 변환이지 임의 normalization gain이 아니다. 각도는 rad, scene 길이는 cm→m로 구분한다.
upstream PhysX3.4 소스는 확장 설계 근거이며 bundled UE의 exact build identity를 증명하지 않는다.
빌드 시 실제 fork/commit·scale·좌표 기준을 별도로 고정하고 검증해야 한다.

확장 시 native actuator는 delay/rate/fault, CARLA는 wheel inertia/damping·tire/suspension·chassis만
소유한다. stock movement controller·engine·clutch·gear·steering smoothing은 함께 실행하지 않는다.
기존 M6 response/vehicle model을 변경하거나 두 번째 motion step을 추가하지 않는다.

#### 서버 apply receipt와 interval work 요구

구현 전의 의미 계약이며 새 RPC/wire ABI는 아직 없다. 단일 writer와 tick owner는 유지한다.

1. INIT에서 build/model/calibration hash, wheel order, 단위, run/plant/actor/owner를 바인딩한다.
   client가 임의로 보낸 capability=true는 권한 또는 calibration 수용 근거가 아니다.
2. `prepare`는 원래 CAN/P05 Actual·application·sequence·source/oldest/expiry를 그대로 보존한다.
   geometry/table 범위와 전체10ms interval coverage를 검사한다. endpoint 관측으로 소급하지 않는다.
3. 하나의 `(run,plant,actor,frame,token)`에4wheel steer/motor/friction을 원자적으로 stage한다.
   pre-physics ACK는 **staged**이고 work 증명이 아니다. 같은 token 재호출은 조회만 가능하며
   재적용·중복 tick을 하지 않는다. timeout은 receipt/snapshot 대조 전까지 ambiguous로 latch한다.
4. physics 구간 종료 receipt는 실제 begin/end·frame·적용 effort·solver substep coverage·원래
   Actual 참조를 포함한다. `Σ Tmotor_i Δθdynamic_i`와 friction loss를 별도로 기록한다.
   animation pitch 또는 endpoint `T×ω×dt`를 실제 구간 work로 승격하지 않는다. brake lock,
   damping·tire loss·수치 잔차를 분리하고 선택한 solver work 정의/허용 오차를 검증해야 한다.
5. receipt가 검증된 뒤에만 단일 EV owner의 IntegratedMotorWork에 전달한다. 같은 구간을
   기존 ZOH 예측과 함께 적분하지 않는다. 외부 tick은 rollback 불가하므로 불완전 receipt는
   energy unavailable·latch이며 다음 tick 금지다. M6 energy budget 수용을 승계하지 않는다.

NoDrive setter는 다음 setter까지 지속되는 API다. 따라서 RPC 추가만으로 expiry를 만족하지 않는다.
확장 서버가 frame별 single-use latch와 pre-tick coverage를 검사하고 old effort 재사용을 막아야 한다.
pause는 tick 정지·pending token 폐기, reset은 새 epoch/INIT·잔존 effort 제거이며 자동 재무장하지 않는다.
wheel·brake 초기 보호 Actual도 같은 반환 경로를 거쳐야 하고 초기화 명목의 직접 brake 쓰기는 금지한다.

### M7-1j — 독립 public SDK 포트와 남은 서버 경계

[실행 근거](../test-plan/evidence/m7_carla_1j/README.md)의 포트는 위 계약 중
단일 wrapper owner·Actual/P05 admission·frame별 stage/tick·잔존 setter 제거·모호한 결과 latch를
공개 PhysX3.4 CHECKED SDK에서 구현했다. 입력은 합성 Actual fixture이며1c `FakeProbe`
경계 뒤에서만 실행한다. 실제 native8-role 반환·CARLA RPC에 연결한 것은 아니다.
post-step 관측에는 원래 Actual/provenance·interval·float applied effort·raw signed omega·
PhysX sleep을 보존한다. setter readback을 새 Actual로 생성하지 않는다.
`interval_work_valid=false`이며 위 서버 work receipt 계약을 충족했다고 주장하지 않는다.

SDK snippet은 upY/forwardZ, wheel order RL/RR/FL/FR이므로 프로젝트 FL/FR/RL/RR과
`{2,3,0,1}`로 바인딩했다. SI1500kg/radius0.5m fixture와 합성 pressure table은
mkz_2020 또는 실제 brake calibration이 아니다. 실제 UE에서는 fork·좌표·단위·wheel geometry를
다시 검증해야 한다. 외부 SDK writer는 wrapper만으로 완전히 봉쇄되지 않는다.

world10ms 안에서 차량 내부 `setSubStepCount`를3/10/20/40으로 비교했다.
3에서는 출발 중 rear 음수45/850 FAIL,10/20/40은0/850이었다. 독립 probe 설정은20이며
별도 fail-stop 시험에서 coarse 첫 음수 후 다음 tick 차단을 확인했다. 신호 보정/threshold 완화가
아니며 차량 질량·타이어·gain은 바꾸지 않았다. 이 설정을 CARLA `max_substeps`와 혼동하거나
stock 바이너리의 평지 실패 해결로 수용하지 않는다. 정확도 허용 오차·전체 ODD는 OPEN이다.

1j 초기 UE fork404 이후 Epic 연결과 [UE4.26.2 전체 빌드](../test-plan/evidence/m7_carla_1j_ue_build/README.md)를 완료했다.
후속 [CARLA 기본 빌드](../test-plan/evidence/m7_carla_1j_carla_build/README.md)는 Client/서버 module exit0이다.
[source 실행](../test-plan/evidence/m7_carla_1j_source_smoke/README.md)은 Town03 비렌더링
identity/ego 정상·예외2/2·102샘플10ms를 한정 검증했고 Episode 설정 복원·SIGINT130/자원 정리를 확인했다.
Town10 준비 한도 초과와 Town03 렌더링 SIGSEGV는 미해결이다.
후속 [렌더링 조사](../test-plan/evidence/m7_carla_1j_render_diagnosis/README.md)에서 잘못된
Distance Field 내부 참조를 관측했다. 같은 바이너리에서 source RGB/GT320×240 수신은
GDB1회·native 같은 서버2회 각30쌍으로 한정 확인했지만 crash 원인/재질 준비/완전 delivery는 OPEN이다.
직접 effort 포트·정상 actuation은 NOT RUN이며 기존 센서/시간 계약을 완화하지 않는다.
후속 [준비/반복 검증](../test-plan/evidence/m7_carla_1j_render_followup/README.md)은 ego·RGB/GT가
살아 있는 상태의 shader/Distance Field zero 관측2회와 준비 후 새 native2서버의150tick/30쌍·
정리/복원·SIGINT130을 한정 확인했다. 원래 crash 원인·전체 content/동적 asset 안정성은 OPEN이다.
이 baseline은 NoDrive 최소 포트의 후속 시험 조건이며 정상 actuation/주행 수용이 아니다.
동일 의미를 실제 서버 lifecycle·scene tick
안에 구현·검증하고 brake calibration과 구간 work를 해결해야 정상 주행 gate를 열 수 있다.

### M7-1k — 서버 NoDrive 0 effort 진단 포트

[설치·구체 RPC 계약](../../tools/carla/m7_nodrive/README.md)과
[실행 evidence](../test-plan/evidence/m7_carla_1k/README.md)에 별도 opt-in 서버 포트를 둔다.
고정 CARLA/UE Linux fork에서 기존4W component를 상속하고, 명시적으로 bind한 ego만
실제 `PxVehicleNoDrive`로 전환한다. stock engine/gear/control 처리는 그 ego에서 제외하며
타이어·suspension·차량 운동은 기존 UE PhysX 한 곳이 소유한다. M6 구현·wire는 변경하지 않는다.

현재 admission은 **합성 CAN/P05 fixture 전용이며 세 Actual이 모두0인 경우만 허용**한다.
원본 receiver·codec을 UE clang10/libc++의 별도 모듈에서 그대로 컴파일해 Actual CAN identity,
CRC·epoch·sequence·source를 검사한다. oldest/source의 전체10ms age30ms·skew10ms 및
exclusive expiry도 별도로 검사한다. nonzero rad/Nm/Pa는 calibration unavailable로 거부한다.
합성 지원 provenance는 실제 Central–Zone–vECU authority가 아니며 이 진단 경로를 정상
8-role 반환으로 수용하지 않는다. command/마지막 control을 새 Actual로 발행하지 않는다.

서버 INIT는 owner key와 명시적 실행 flag를 요구하고 run UUID/session/actor를 바인딩한다.
바인딩 중 legacy 제어·force/velocity/pose·physics·설정/reload·batch·일반 tick RPC를 막는다.
이는 전용 실행 환경의 추가 서버 guard이며 전체 CARLA 인증/격리 수용을 뜻하지 않는다.
`stage` ACK는 미적용, `advance` ACK는 큐 삽입, `receipt`만 physics 종료 관측이다.
frame/ticket은 single-use이며 원래 CAN bytes와 실제 frame·simulation begin/end를 receipt에
보존한다. persistent setter readback은 적용 demand이지 실제 actuator feedback이 아니다.
raw signed wheel ω를 보존하며 `interval_work_valid=false`, substep work observation도 false다.
energy owner를 연결하지 않은 이0 effort 진단만 다음 관측 tick을 허용하며, 정상 energy
receipt가 불완전하면 latch해야 한다는 위 주행 계약을 완화하지 않는다.

진단 clock은 bind 원점1s + frame차×10ms이고 원래 payload source는 불변이다.
실제 simulation 시각을 별도 기록하며 native wall/kernel clock 수용으로 승격하지 않는다.
pause는 pending 폐기·latch, reset은 실제 physics state 재생성·generation 변경·latch다.
physics generation 변경 또는 모호한 post-tick 결과는 다음 tick을 막는다. close로 해당 ego를
종료하고 새 session/INIT를 받아야 다시 진행한다. advance timeout의 자동 재시도는 금지한다.

다음 gate는 readback geometry의 좌표·휠 순서 검증과 근거 있는 brake 모델, nonzero effort,
보호 Brake Actual/raw wheel, 실제8-role interval 연결, solver work/단일 EV 및 wall timing이다.
짧은0 effort 실행은 평지 brake-hold·기존 미세 음수 문제·렌더러 crash 해결의 근거가 아니다.

### M7-1l — rest geometry와 brake 모델 선택 경계

[실행·독립 감사](../test-plan/evidence/m7_carla_1l/README.md)에서 yaw0/±90/180 및
yaw37/pitch7/roll−4의5개 INIT 자세를 사용했다. physics enabled·tick 정지 상태에서
reference bone/offset→body→실제 COM→world→actor 및 프로젝트 반사 변환을 대조했다.
FL/FR/RL/RR 순서와 nominal rear-axle rest 중심의 actor 기준 위치 약
`[-1.388633,0,0.359541] m`, wheelbase 약2.86047m·front track 약1.59292m를 확인했다.
이는 **reference/rest geometry**이며 contact patch나 suspension 변위에 따른 실제 wheel center가 아니다.
body에 고정된 nominal rear frame의 초기 근거로 사용하며 동적 기준점/속도 변환은 별도 검증한다.

공개 `VehiclePhysicsControl.center_of_mass`는 `COMNudge`이고 RPC에서 이미 cm→m 변환된다.
관측값 `[0.3,0,-0.2] m`를 실제 COM 위치로 사용하지 않는다. 실제 body local COM은
약`[0.212369,0.000294,0.549693] m`였다. 변환 검사는 float32 계산 오차 예산을 사전 고정했고
센서 validity/freshness epsilon을 추가하지 않았다. nonzero 조향 방향은 NOT RUN이다.

[brake 모델안](../test-plan/evidence/m7_carla_1l/brake-model-proposal.json)은 **미채택**이다.
V1은 기존 M6의 합산0.001Nm/Pa를 명시적인 가상 EV에서4륜 균등 배분하는 제안이며
각0.00025Nm/Pa,200kPa에서각50Nm·1.5MPa에서각375Nm다. 합산 law의 근거는 기존 SIL
정의이고 균등 배분은 새 가상 모델 선택이다. MKZ/OEM 보정이나 M6 응답 수용 승계가 아니다.
이 가상 모델의 명시적 수용 전에는 runtime에 설치하지 않는다.
H1은 유압 pressure 위치/회로 배분·피스톤 면적·마찰·유효 반경·효율·onset의 식별 자료를
요구하는 대안이며 수치는 미확정이다. wheel radius와 max brake800Nm로 이를 대신하지 않는다.
현재 서버는0 Actual만 수용하며 pressure→torque law를 실행하지 않는다.

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

## 5. Clock과 M7 multirate 개정 (M7-1d)

**결정:** 사용자가 world/state10ms + 영상50ms 방향의 다음 작업을 승인했다.
M7-0의50ms world baseline을 아래와 같이 명시적으로 supersede한다. M7-1b의50ms
시험과 M7-1c의40ms stale 거부는 당시 조건의 유효한 과거 증거로 보존한다.
M6 코드/실행 profile/수용 수치와 Drive30ms 한계는 변경하지 않는다.

| 단계 | M7 개정 주기 / 의미 |
| --- | --- |
| CARLA world / Vehicle State | synchronous=true, fixed_delta_seconds=0.01; 매 frame의 새 WorldSnapshot/ActorSnapshot 취득 |
| RGB / Semantic GT | sensor_tick=0.05; world5frame마다 촬영, 원래 frame/time 유지 |
| Planner / Controller | 기존50/20ms; Controller 위상은 영상 frame마다 재시작하지 않음 |
| Zone / Steering·Brake·Drive vECU | 기존10ms; 실제 task/runtime 연동은 후속 |
| Source freshness / native owner guard | 기존30ms 및2ms opportunity/4ms 완료 계약 유지; CARLA tick으로 대체하지 않음 |

단일 Host orchestrator만 tick한다. `apply_batch_sync(..., do_tick=True)`의 숨은 tick,
Traffic Manager/ScenarioRunner의 별도 tick은 금지한다. ScenarioRunner는 기본 시험에서 제외한다.
physics substepping은 max delta0.01s/max steps10으로 설정·readback한다. 이 설정은
서버 내부 적분의 상한이며 클라이언트 substep 관측/API 제공의 증거는 아니다.

향후 functional scheduler의 각10ms 단계 순서는 새 관측 수용→due Controller/기존 Central
배분→Front/Rear 전달·Leaf 작업→외부 actuator 응답/Actual 반환→adapter 검증/apply ACK→
단일 world tick→다음 관측이다. Controller는0,20,40,60ms의 연속 위상을 유지한다.
관측 frame n을 사용한 출력은 다음 interval에만 적용한다. 원천30ms·skew·expiry·interval
coverage와 기존 peer/parent/ACK/RunLease를 모두 검사한다. camera 지연 때문에 같은
snapshot을 새 것으로 재발행하거나 미래 상태를 과거 ECU release에 배치하지 않는다.
이 순서는 **설계**이며 M7-1d에는 ECU scheduler·Actual apply가 연결되지 않는다.

### 50ms/30ms 충돌의 해소 범위와 남은 gate

기존 [DriveController](../../vecu/drive/drive_controller.cpp)와
[DriveReceiver](../../interfaces/drive/drive_receiver.cpp)는 원천/oldest dependency30ms를
요구한다. 50ms 측정 사이10ms task의 age0/10/20/30/**40**ms는 필연적으로 stale이었다.
EV capability70ms나 M6 MIL speed60ms는 이 계약을 바꾸지 않는다.

이제 state를10ms마다 **실제 새 snapshot**으로 취득하여 이 샘플링 주기 불일치를 제거한다.
state까지50ms로 export/decimate하면 충돌이 남으므로 critical feedback 후보 경로는100Hz를
유지한다. 영상만20Hz다. 100Hz 재발행·sequence 증가·도착 시각 restamp·보간으로 대체하지 않는다.

| 대안 / 상태 | 판단 |
| --- | --- |
| world/state10ms + 영상50ms | **채택**, M7-1d 비주행 수집으로 논리 cadence 검증. 실시간 Drive 적합은 별도 |
| 50ms world 내부의 실제 substep 양방향 연동 | 기존 조건 보존 후보였으나 이번 주기 개정으로 우선순위에서 제외. 패키지에서 구현/입증되지 않음 |
| predictor/독립 wheel model | measured input 대체 불가, 중복 dynamics 금지 |
| freshness30→60ms / 캐시 restamp | 계속 금지 |

10ms 논리 tick도 wall10ms를 보장하지 않는다. sampling 간격+전송/queue/consumer 지연+
clock uncertainty가30ms 안인지 실제 경로에서 측정해야 한다. actor velocity와 `speed/radius`는
실제 wheel angular-speed 센서가 아니므로 Drive 연결에 필요한 wheel 원천은 여전히 미확정이다.
또한10ms interval 안의 새 보호 반영·비가역 CARLA RPC 지연은 native2ms/4ms guard와 별개다.
더 빠른 world 설정만으로 기존 완료 시한이나20ms transport envelope 충족을 주장하지 않는다.
Actual interval support·중복 dynamics/energy·calibration gate도 남는다.

**정상 주행 연결 BLOCKED**를 유지한다. M7-1d 수집기는 static NON_DRIVING fixture이며
논리 cadence·센서 누락·pause/reset 결과와 wall 측정치를 따로 보고한다.

### 시간 영역·pause/reset

CARLA `frame/timestamp.elapsed_seconds`는 simulation clock이다. 원래 double seconds와
명시적 반올림한 ns를 함께 보존한다. M7-1 tick 검증 tolerance1µs는 부동소수 비교용이며
source-age 여유가 아니다. callback arrival/receive/apply/RPC 시작·끝은 Host CLOCK_MONOTONIC.
UTC는 run label에만 사용한다. 두 clock을 직접 빼거나 nominal10ms를 wall10ms라고 주장하지 않는다.

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

## M7-1b 실행 연결

2026-10-23 [수집 근거](../test-plan/evidence/m7_carla_1b/README.md)에서 정적 ego의
RGB/GT/state·50ms tick/원천 metadata·채널 분리·제한된 fault/pause/reset을 검사했다.
서버 포함0.9.16 wheel/별도 venv·fresh client reset 경로를 한정 사용한다. 같은 client native
reload/server crash OPEN은 보존한다. Vehicle State는 actor origin이고 rear-axle calibration은
미확정이다. 이 실행은 외부 Actual bridge·clock mapping/Drive30ms·actuation/energy 수용이 아니다.

## M7-1c 논리 검증 연결

2026-10-23 [test-only Actual/fake backend](../test-plan/evidence/m7_carla_1c/README.md)에서
원래 receiver/P05·DriveController를 재사용해 metadata/interval·writer·single-use ticket·
ambiguous apply/tick·중복/재진입 거부와 source-age 경계를 검사했다. Normal/ASan 각39/39.
이 prototype은 정규 runtime/새 wire ABI가 아니다. measurement support metadata는 fixture의
원천 선언이며 기존 CAN command/RunLease expiry와 같은 것으로 바꾸지 않았다. 실제
peer/parent/authority transport·CARLA 접근 제어·주행 calibration은 미구현이다.
이1c 당시50ms 조건에서는 원래 Drive가40ms-old local sample로 보호를 선택해 충돌이 남았다.
현재 M7 주기는 아래1d 개정을 따르며1c의 과거 조건/결과는 보존한다.

## M7-1d 실행 연결

[10ms world/state·50ms 영상 비주행 근거](../test-plan/evidence/m7_carla_1d/README.md)에서
main state600/600·영상각120/120, live pipeline drop·실제 pause/fresh-client reset을 확인했다.
첫 camera 간격60ms는 startup 변동으로 남겼다. 마지막50startup tick에서 안정 위상을 확인하고
main 위상을 고정했다. 주행 센서 readiness는 첫 callback 수신만으로 성립하지 않는다.
최종 nominal RTF0.764923, pause 제외 snapshot 완료 간격>30ms12/798로 wall100Hz는 미충족이다.
실제 ECU clock/Drive 연결은 NOT RUN이며 논리 source-age replay로 대체하지 않는다.
정리 후 SIGTERM 중 native SIGSEGV/139는 OPEN-M7-1D-01이다. 기존 native crash OPEN도 유지한다.

## M7-1e 원천·clock·비용 진단 연결

[진단과 대안](../test-plan/evidence/m7_carla_1e/README.md)에서 공식0.9.16 source와 설치된
wheel RPC를 대조했다. `get_wheel_pitch_angle`은 physics on이면 물리 wheel 회전각,
off이면 animation pitch다. frame/time 없는 float RPC이며4wheel 개별 호출이다.
새 snapshot 사이 tick을 보류한 unpowered probe에서 유한 값을 얻었지만, 유효 회전 자극·
wrap/slip·구간 각속도의 기존 Drive sensor 적합성은 NOT RUN이다. v/r 대체는 계속 금지한다.

`platform_timestamp`는 WorldObserver 직렬화 시작의 FPlatformTime이며 개별 물리 취득
시각과 동일하다고 가정하지 않는다. Host monotonic과 약2.4s 차이가 있었고, 전체 진단
구간에서 하나의 상수 offset은 관측 bracket과 불일치했다. arrival restamp/zero offset은 금지다.
render/audit 분리 결과 metadata만 수집하면 RTF1.014~1.033이었으나 max gap26.654ms이며
실제 ECU/통신·source-age 수용은 미검증이다. 빈 서버도 종료139가 재현돼 OPEN을 유지한다.

다음 우선 후보는 명시적 **functional simulation clock 모드 설계**다. 기존 wall runtime에
sim timestamp를 넣거나 기존2ms/4ms guard의 clock을 몰래 바꾸지 않는다. 전체 ECU/권한/
lease/expiry·Actual 경로와 논리 barrier를 별도 opt-in으로 설계하고,30ms 값·원천 dependency를
보존해야 한다. 해당 결과는 wall deadline/100ms 검출 수용을 대신하지 않는다.
CARLA를 영상/환경용으로만 쓰고 기존 SIL이 motion을 소유하는 대안은 현재 소유권 변경을
요구하므로 미채택이다.1e 당시 정상 주행·새 backend·clock mode 구현은 NOT RUN이었다.

## M7-1f functional clock/shadow 계약과 구현

[구현/시험](../test-plan/evidence/m7_carla_1f/README.md)은 `STRATADRIVE_M7_FUNCTIONAL_TESTS=ON`
및 native CLI `--functional-shadow`로만 실행한다. default는 OFF이며 production wire ABI,
M6 실행 profile, 세션·lease 상수, 기존 wall watch를 변경하지 않는다.

| 경계 | 이번 구현 / 제한 |
| --- | --- |
| 시계 | run/application/plant scope와 별도 domain `0x4d3746554e435449`; native 시간은 CARLA snapshot의 원래 elapsed seconds를 ns로 반올림. nominal grid나 도착 시각으로 치환하지 않음. 원래 seconds·platform·Host monotonic도 raw trace에 별도 저장 |
| tick 순서 | snapshot → frame/scope/time 검사 → 해당 시각까지 native jobs →8역할 처리 barrier → NON_DRIVING next-frame permit → Python tick1회 → 원래 snapshot 확인. 중복/skip/rollback/domain 오류는 해당 instance를 latch하고 재시도 금지 |
| native 실행 | 같은 프로세스/단일 thread의 실제 Central·Front/Rear Zone·Steering/Brake/Drive/BMS/Power. 기존0.2ms ingress·1ms physical fixture job grid, Controller root20ms, Host10ms child allocation, leaf10ms/BMS20ms를 유지. 이 grid는 Host 실행 기회/4ms deadline 판정이 아님 |
| 세션/권한 | 실제8역할 ParticipantPort의 Prepare/INIT/Release ACK를 원래 SessionCoordinator가 수용한 뒤 원래 RunLeaseIssuer가 발급. 각 역할에 개별 RunLeaseGate, global60ms·source30ms·원래 expiry 유지. Central self-credit만 local binding; 다른 역할의 제어/ACK/lease는 v1 codec 왕복, normal 경로는 native typed queues. SOME/IP/프로세스 분리 시험 아님 |
| Actual | native physical fixture→vECU→Zone→Central 실제 반환 경로. armed 구간에3Actual의 원래 source age+다음10ms<=30ms/skew<=10ms 검사. 이것은 **source-only fixture coverage**이며1c의 source/oldest/expiry provenance·full apply admission을 대체하지 않음 |
| plant 책임 | 기존 PhysicalOwner를 `simple_vehicle=false`인 stationary actuator/electrical 시험 fixture로만 재사용. fixture wheel=0; CARLA 측정으로 위장하지 않음. CARLA는 별도 physics-off ego, apply0. 실제 backend 분리/물리량/energy 결합은 아직 구현하지 않음 |
| pause/실패 | Python이 tick을 멈춘 동안 native process에도 STEP을 보내지 않아 logical time·lease를 갱신하지 않음. 별도10s IPC wall timeout은 시험 hang containment용. lease 갱신 상실·Actual/역할 누락은 native 검증 또는 barrier에서 차단. wall 실행에서는 기존 monitor가 계속 동작한다는 계약 유지 |
| reset | fault latch를 같은 instance에서 해제하지 않음. trusted caller가 새 scope·새 process/object를 발급하고 INIT부터 재시작. native 새scope/oldscope 거부를 검증했으나 live world reset·영속 epoch store 연결은 NOT RUN |

**해결 범위:** CARLA의 wall 처리 지연과30ms source-age를 혼용하던 문제에 대해, 요구값을
보존하는 별도 기능 검증 경로를 구현했다. 원래 native ECU/권한 API에 동일 logical time을
공급할 수 있음을 실제 actor 경로에서 확인했다. CARLA의 vehicle/wheel sensor나 Actual actuation이
이 경로에 연결된 것은 아니다. 실제 wheel 원천·source/oldest dependency·actuator 분리·calibration이
준비되기 전 정상 driving permit은 구현하지 않는다. wall mapping과2ms/4ms 검증은 별도 gate다.

## M7-1g wheel 검증 계획

**계획을 실행한 결과:** [M7-1g 원본/실패/근거](../test-plan/evidence/m7_carla_1g/README.md).
0.9.16의 `get_telemetry_data().wheels[].omega`가 직접 PhysX rad/s를 제공함을 확인했다.
이 입력에는 pitch 차분·unwrap 후보를 사용하지 않는다. 기존1e/1f의 당시 조사 결과는 보존한다.

| 항목 | 이번 결정과 한계 |
| --- | --- |
| 원천 | physics-on,4wheel을 한 RPC/scene read lock으로 읽음. RPC payload에는 timestamp/frame 없음. 전용 single tick owner가 snapshot 전후 동일 frame/time을 확인하고 source=oldest=원래 elapsed ns로 결부 |
| identity | trusted run/application/plant/actor·functional clock 고정. 원래 frame을 sequence로 사용,32bit 범위 밖 거부. 네트워크 인증이나 서버 timestamp 확장을 구현한 것은 아님 |
| ECU 입력 | 뒤쪽 index2/3 산술평균 → 기존 LocalSensors → DriveActual CAN/P05 → Rear → Central. 실제 비영 wheel 입력/원래 source/CAN0.01rad/s 양자화를 확인. rear drivetrain calibration을 의미하지 않음 |
| multirate | native subjob 시각보다 미래인 sample은 최대2개 queue에서 보존. 소비 시각으로 restamp하지 않음. ns grid 오차 때문에 pending을 덮어쓰던 첫 live 실패를 수정·회귀 검증 |
| 유효성 | 결측·scope/actor/frame/source 불일치·NaN·range·rear 음수 거부. 평지 접지 중 미세 음수로 native 연결 실패가 남음. abs/epsilon/clamp로 원래 전진 전용 계약을 완화하지 않음 |
| 실제 검증 | 내리막400tick 중396개 wheel Actual 반환·322개 armed fixture frame, 최대 wheel source age10ms. pause250ms와 duplicate 후 tick 차단. 무동력 중력 이동이며 정상 control actuation 아님 |
| ownership | CARLA는 motion만 관측, native torque/steer/pressure·전기는 여전히 시험 fixture. 에너지 입력 wheel0을 실제 CARLA energy로 사용하지 않음. CARLA apply0이며 정상 driving CLI 없음 |

`telemetry.torque`는 DebugWheelTorque이며 실측상 `-long_force×radius`와 일치한다.
모터축 Drive Actual로 사용하지 않는다. 직접 omega는 구간 각도 차분의 aliasing 문제를 피하지만,
이 결과가 역회전/정지 잡음/슬립/전체 운행 범위 calibration을 모두 해결하지는 않는다.

1g 이후 signed wheel validity와 actuator/전기 포트 분리는 아래1h를 따른다.
full Actual provenance→apply ACK→tick 및 원래
interval expiry 검증이 끝나기 전 정상 driving permit은 없다. 패키지 직접 torque 포트가 확인되지
않았으므로 검증 가능한 역변환과 서버 확장안을 비교한다. source build는 별도 범위다.

## M7-1h signed validity와 actuator/electrical 포트

[구현·실행 근거](../test-plan/evidence/m7_carla_1h/README.md).
`--external-wheel-plant`는 M7 전용 ActuatorElectrical을 선택하며 기존 PhysicalOwner를 병행하지 않는다.
Steering/Brake/Drive 응답과 EvPowerModel을 소유하고 SimpleVehicle/VehicleEvModel을 사용하지 않는다.
파라미터는 기존 functional fixture의 명시적 재사용이며 CARLA 차종 calibration이 아니다.

| 포트 | 계약 / 현재 상태 |
| --- | --- |
| signed wheel 평가 | 기존 accepted 값은 유지. rear 음수 중 abs<0.005rad/s인 zero-bin은 SubResolutionNegative 진단으로만 분류하고 forward 값은 unavailable. 기존0.01rad/s wire resolution을 noise 허용값으로 사용하지 않음. 평지 일반 연결은 FAIL 유지 |
| ECU wheel | 원래 sample·rear 평균·source/frame/model identity, 기존 source-age 유지. 값이나 시각을 소비 시각에 맞춰 고치지 않음 |
| electrical wheel | 원래 acquisition 최대5개 history에서 각1ms 구간 begin 이전 최신 값 선택. ZOH 입력이며 미래 endpoint 사용 금지. 기존30ms age/10ms skew 유지 |
| actuator output | leaf/type·application·source 검증 후 기존 물리 응답 모델에만 적용. fresh old/new application mismatch·잘못된 시각/값 거부. no-actuation publication은 watchdog을 갱신하지 않음 |
| commit/fault | actuator·전기·Battery·출력 cursor를 후보 상태로 계산, 전체 성공 후 commit. 실패 시 센서 unavailable·latch·추가 tick 거부. 모델 상태 일부만 전진시키지 않음 |
| energy audit | 각 구간 Tactual×ω(begin)×dt 및 source/oldest/누적을 출력. `MODEL_ZOH_UNAPPLIED`, `carla_work_valid=false` 고정. CARLA apply/receipt가 없으므로 실제 차량 work/회생/에너지 수용으로 사용 금지 |

1h는 실제 wheel을 전기 **예측 모델**에 공급하는 포트 분리까지 구현했다. CARLA 실제 물리 work를
받는 IntegratedMotorWork 연결은 아직 없다. 모델 파라미터/응답 budget의 CARLA 동등성도 미검증이다.
1i의 직접 wheel effort 확장안은 위3절을 따른다. full Actual provenance/apply ACK/interval work
연결은 후속이며 M6 계약은 변경하지 않는다.

### M7-1i 정지 부근 validity 판단

**숫자 epsilon은 채택하지 않는다.** 기존 평지 trace는 자유 낙하·접지 중이고 Brake Actual이
CARLA에 적용되지 않았다. 음수74/400개의 관측 상한은 센서 오차 bound가 아니며, 현재 RPC는
PhysX sleep/접지 제약 상태도 제공하지 않는다. actor `is_active/is_dormant`로 대체할 수 없다.
upstream PhysX에는 brake로 회전 부호가 바뀔 때 wheel을 물리적으로 lock하는 처리와 sleeping
차량의 내부 속도를0으로 만드는 처리가 있다. 이는 **물리 solver 동작**이지 client의 음수→0 보정
허용이 아니다. 현재 바이너리의 미세 음수 원인이나 brake 적용 후 정상성을 증명한 것도 아니다.

후속 순서는 실제 보호 Brake Actual 적용 → 원래 wheel·contact/sleep·frame·receipt 관측 →
정지/출발/정지 반복 시험이다. 음수이면 계속 unavailable/latch하고 tick을 정지한다.
exact0 또는 원래 전진 범위의 측정만 수용하며 warmup을 명목으로 음수 구간을 숨기지 않는다.
이 경로로도 실패하면 forward ODD와 측정 불확도를 포함한 별도 requirement revision이 필요하다.
이번 단계에서 M6 ODD·codec·source-age·reset 증거 조건을 바꾸지 않았다.

## M7-1m — 수용된 V1 가상 EV / 격리 nonzero 진단

[승인 모델](../../tools/carla/m7_nodrive/virtual_ev_v1.json)과 [실행 근거](../test-plan/evidence/m7_carla_1m/README.md).
사용자가 V1을 수용했다. 이는 **가상 모델 선택**이며 실제 MKZ 유압 식별이 아니다.
기존1l의 DRAFT artifact는 당시 상태로 보존한다. 별도 `-StrataM7V1Probe`가 있어야 하며
zero-only flag와 동시 지정은 거부한다. owner/run/session 외 bind에 정확한 모델 SHA256이 필요하다.
모델 값은 서버가 설치 시 생성한 상수이며 client가 승인/계수를 선언해 교체할 수 없다.

| 입력·범위 | 승인된 V1 법칙 |
| --- | --- |
| equivalent angle ±0.3rad, 프로젝트 좌+ |1l 실측 front track/wheelbase로 이상 Ackermann, UE 우+는 음수, rear0 |
| aggregate signed motor −200..300Nm | front0, rear각T/2. 별도 gear/lag/filter 없음 |
| Pressure Actual0..1.5MPa | 합산0.001Nm/Pa,4륜 각25%의 nonnegative brake capacity.200kPa→각50Nm,1.5MPa→각375Nm |
| geometry/상한 | 실측 mass1696kg·wheel bone/COM x,y offset·radius.355m·front steer/각800Nm brake와 정확히 일치해야 함. 변경 asset은 거부 |

검사된 원래 CAN/P05 Actual에서만 mapping한다. 원래 native receiver의 mode/source/age/expiry를
통과해야 하며 pressure/drive/steer 초과를 clamp하지 않는다. LocalProtection Brake Actual은 센서 보고의
원래 mode를 보존한다. 합성 test fixture이며 실제8-role 보호 authority를 증명한 것은 아니다.
Nm는 UE kg·cm²/s²로10000배, rad는 그대로 float32 setter에 전달한다. pre-physics에서12개 setter를
한 번 적용하고 post-physics에서 같은 float32 demand를 검증·receipt에 남긴 뒤 모두0으로 지운다.
후속 describe의0은 setter 제거 증거이며 solver에 실제 적용된 brake 반력의 측정값이 아니다.
pause/reset은 nonzero pending도 폐기·latch한다. 다음 tick이나 자동 재무장으로 이어지지 않는다.
clock schema 이름은 기존 `m7-zero-probe-logical-frame`을 유지하며 wall authority를 뜻하지 않는다.

실제 두 새 서버에서 각1,621receipt·nonzero1,601개와 출발/감속/정지/hold/release/좌우 조향을
관측했다. hold100/100frame exact wheel0이지만, 출발/주행의 rear 음수로 각487frame은 native forward
unavailable이다. 음수는 최대 약−7.4rad/s로 작은 센서 epsilon으로 처리할 근거도 없다.
이 diagnostic에서는 native sensor 입력/8-role loop를 연결하지 않고 원래 음수까지 관측했다.
정상 native 경로라면 unavailable/latch·다음 tick 차단 계약이 유지된다. **forward gate FAIL**이다.
내부 적분 분할 후보 비교는 후속이며 world/ECU rate·30ms freshness를 바꾸는 해결안이 아니다.
solver 구간 work는 미관측, `interval_work_valid=false`; 전기/SOC/회생 수용과 정상 주행 permit은 없다.

## M7-1n — 별도 내부20분할 수치 진단

[동일 입력 대조·원본 실패](../test-plan/evidence/m7_carla_1n/README.md).
`-StrataM7V1Substeps20`은 V1 flag와 함께 지정하는 별도 서버 진단 옵션이다.
client가 count를 전달하는 actuation API를 만들지 않는다. 기본 asset low/high3/1·threshold5m/s는
유지하고, 후보에서만 low/high20/20을 NoDrive wheel sim data에 설정한다.
threshold 양쪽에서20이므로 원래10ms world step 내부 분할이다. wheel/frame/source를 추가 생성하거나
Controller20ms/Zone10ms·Drive30ms freshness·Actual expiry를 바꾸지 않는다.
receipt의 numerical profile·실제 live low/high/threshold를 보존하고,20/20 일치 여부도 pre/post에 검사한다.

동일 원래 CAN/P05/Actual·V1 law·world 설정에서 기본487frame rear 음수가 재현됐고,
20분할 새2서버는 각각3frame으로 감소했다. launch 첫 tick의 약−.256rad/s는 여전히 unavailable이다.
입력과 원래 음수를 보정하지 않았으며 이3frame을 startup 면제로 처리하지 않는다.
**20분할 정상 profile은 미채택, native gate FAIL**이다.40분할이나 기존 actuator owner의 원래
Actual trajectory 분리 시험은 후속이다. adapter에서 응답 ramp/filter를 추가하지 않는다.
전체 ODD/실제8-role/work/전기/wall 수용을 이 대조 결과로 대체하지 않는다.

## 6. 결정과 미결정

**M7-1o 후속:** [원인·검증](../test-plan/evidence/m7_carla_1o/README.md)에서 기존20분할의
출발 음수는 저속 tire 반력과 명시적 wheel 적분의 진동으로 확인했다. 정착/기존 response 모델
입력/40·80분할도 FAIL이며, 물리 계수 변경 없이320분할을 후속 격리 통합 후보로 사용한다.
world10ms와30ms freshness는 그대로다.160/320/640 비교는 측정된 민감도이며 전역 정확도 수용이 아니다.

원천 정정: 기존 `getWheelRotationSpeed()`/`omega_rad_s`는 이 fork의 `mCorrectedWheelSpeeds`다.
무구동·무제동 저속에서는 rolling speed 혼합이 가능하므로 항상 내부 solver ω라는 해석은 정정한다.
과거 원본/FAIL은 보존한다. 새 `solver_omega_rad_s`/`PhysX3.4.mWheelSpeeds.direct.v1`는
pinned UE header의 serialization accessor로 `mWheelSpeeds`를 직접 읽은 동일 post-physics
frame 관측이다. engine 수정·v/r 재구성·clamp·timestamp 재발급이 아니다. 향후 native bridge는
이 source를 명시적으로 요구하고 source 부재·비유한·rear 음수에는 unavailable/latch를 유지한다.
공개 보정값으로 fallback하지 않는다. 기존 M6 CAN/P05 wire나 native 요구사항은 바꾸지 않는다.

최종320분할의 새2서버 stress와 response 입력은 각각1,621frame/4wheel 직접 solver 음수0이다.
내부 앞바퀴 callback의 미세 음수는 보존하며 모든 substep의 무음수/전체 ODD를 주장하지 않는다.
callback은 생략될 수 있어 `interval_work_valid=false`와 solver work/단일 EV gate는 유지한다.
native8-role full Actual/authority·wall2/4ms는 미연결·미수용이다.

**M7-1p 센서 반환 경계:** [실행 근거](../test-plan/evidence/m7_carla_1p/README.md).
별도 opt-in local bridge는 bind의 run UUID/session/actor/physics generation/model/profile을 고정하고,
post-physics receipt의4wheel 직접 source·순서·frame·ticket·구간 연속성을 검사한다. 공개
`omega_rad_s` fallback은 없다. CARLA world snapshot은 같은 frame/원래 simulation-end time으로
교차 확인한다. receipt RPC보다 episode stream이 늦을 수 있어 최대10s wall 동안 **조회만** 기다린다.
timeout/skip이면 latch한다. 이 timeout은 functional harness의 수신 한도이며30ms source age나
native wall deadline 변경이 아니다. 기다리는 동안 tick/advance 재시도·restamp는 없다.

센서 acquisition은 원래 simulation-end seconds의 ns 반올림이며 frame은 원래 acquisition sequence다.
기존 M7 native fixture의 scope `(1,42,7)`/clock domain은 fresh process마다 새 INIT로 시작한다.
CARLA run/session/generation은 그 외부의 신뢰된 local binding으로 보존한다. synthetic Actual의
`m7-zero-probe-logical-frame` 시각이나 session을 native authority로 간주/변환하지 않는다.
기존 native rear 평균·CAN0.01rad/s 양자화·vECU→Rear→Central 반환을 사용하고, pending sample은
자기 시각 이후 job에만 공급된다. Controller20ms/Zone·vECU10ms/Drive30ms를 유지한다.

실제320분할 step/response 새2서버는 각각1,621관측/1,609반환·다음 구간 끝 age 최대20ms였다.
native 반환은 **sensor-only shadow**다. actuator/전기는 stationary native fixture이고
차량 motion 적분은 비활성이다. 이 fixture의 torque/SOC를 CARLA effort/work로 주장하지 않는다.
native barrier 성공만 다음 진단 tick 진행을 허용한다. 부재/비유한/범위 초과/원천 불일치/후륜 음수는
다음 tick을 막고 backend pause·persistent setter clear·latch로 이어진다. 아주 작은 음수도 native가
거부한다. pause/reset/close는 bridge를 폐기하며 cached receipt로 재무장하지 않는다.
실제20분할 음수와 snapshot 누락 주입에서 containment를 검증했다. 실제8-role full Actual의
authority/interval→NoDrive 적용, solver work/EV, wall 성능은 별도 후속 gate다.

**M7-1q native Actual 적용 경계:** [구현·실행·실패](../test-plan/evidence/m7_carla_1q/README.md).
별도 `-StrataM7NativeProbe -StrataM7V1Substeps320`로만 활성화한다. 기존 zero/V1 합성 진단과
상호 배타적이며 일반 `stage`는 거부·latch한다. `stage_native`는 반환된 원본 CAN/P05와
native authority를 검사한 뒤 single-use ticket을 발급한다. `advance` 한 번에 한 구간만 적용하고
post-physics receipt/clear 후 다음 관측으로 진행한다. 일반 CARLA writer/tick RPC는 계속 차단한다.

- 원본 native mailbox의 **수신 완료 hook**에서 Zone→Central Actual과 Zone→vECU 명령/permission을
  읽기만 한다. 메시지를 pop/대체/재발급하거나 ACK를 대신 만들지 않는다. current receiver 표본의
  epoch/sequence/source 및 Actual.causal_sequence에 맞는 원본 command를 선택한다.
- 실제 coordinator가 수용한8개 Release ACK,7개 remote RunLease 및 Central local credit을 포함한
 8-role service/credit mask를 전달한다. server는 original owner-wire route/domain/CRC32C와
  session plan/ACK·동일 credit/60ms expiry를 검사한다. CRC는 인증이 아니다. owner key와 fresh local
  process의 신뢰 경계 안에서만 사용하며 Host IPC/SOME-IP 또는 Target authority로 전용하지 않는다.
- CARLA run UUID/session/actor/physics generation/model/profile은 외부 binding으로 고정한다.
  native application42/fixture scope(1,42,7)는 fresh process의 실제 INIT로 시작한다. native 시각은
  동일 snapshot의 원래 simulation elapsed seconds를 ns 반올림한 `m7-native-simulation-elapsed`다.
  기존 합성 profile의 logical-origin 시각은 사용하지 않는다. 이전 binding의 packet 재사용은 금지한다.
- 새 모드만 최초 관측+8ms에 INIT을 요청한다. 현재 native owner 순서에서 enable은+29ms,
  Controller/management 첫 위상은 enable+14ms다. 주기20/10ms·IO200µs·physical1ms 및 모든
  freshness/expiry는 그대로다. 기존 immediate INIT은 Actual 반환 후 부모 명령의 여유가5ms인
  구간에서 다음10ms를 덮지 못했다. offset은 실제 job의 실행 시점을 바꾸며 source를 재발급하지 않는다.
- Actual3개는 원본 receiver로 decode/P05/cursor 검사하고 source·Drive wheel의 **구간 끝 age≤30ms**,
  skew≤10ms를 요구한다. Normal/Degraded NormalPath만 정상 적용하며 causal command/root age30ms,
  dependency70ms, 원래 context expiry를 **전체 다음10ms**에 검사한다. 원래 BMS permission의
  source50ms/dependency70ms·parent와 grant expiry·Drive capability quality도 검사한다.
  동일 held packet은 새 표본으로 수신 처리하지 않고 기존 receiver의 current_sample로 검증한다.
- 최초4tick은 native Actual이 아직 없는 명시적 INIT 무입력 관측이다(최대80ms, 정상 권한 없음).
  이후 실제 Init/NoAcceptedInput Actual만 torque0 조건으로 적용하며 angle/brake를0으로 만들지 않는다.
  최초 정상 진입 후 INIT/empty로 돌아가거나 누락을 cache로 채우는 것은 거부·latch한다.
- native external owner가 기존 actuator 응답과 전기 ZOH **예측**만 소유하고 차량 운동은 CARLA만 적분한다.
  모델 전기는 적용 receipt/solver 적분 work를 정산한 값이 아니다. `MODEL_ZOH_PREDICTION_NOT_CARLA_WORK`,
  `interval_work_valid=false`이며 일반 정상 주행/에너지 수용 flag는 열지 않는다.

최종 새 서버400tick/319정상 권한 구간 및 독립 wire/physics 검사에서 원래 source의 구간 끝 age는
최대20ms다. 최소 명령 expiry 여유1ns는 기존 exclusive expiry 경계이며 wall jitter나 불확실성의
여유가 아니다. pause/reset/오류는 setter clear·latch 후 fresh process/새 INIT를 요구한다.
현재 시험은 고정 VehicleRequest(0.2m/s², curvature0.02/m)의 제한된 출발이며 일반 시나리오·센서
영상/AI·전체 ODD·wall deadline은 포함하지 않는다. 다음은 solver work/단일 EV·원자적 실패 처리다.

### M7-1r: 완전한 solver work와 단일 EV 정산

[실행 근거](../test-plan/evidence/m7_carla_1r/README.md). `-StrataM7SolverWork`를 native/320분할
프로필에 추가한 경우만 아래 계약을 사용한다. 기존1q 모드는 ZOH 예측/`interval_work_valid=false`를
유지한다. M6 코드·EV 계수·에너지 오차 수용 기준은 변경하지 않는다.

- **관측점:** pinned PhysX3.4 `updateNoDrive` 진입/정상 종료 및 sleeping-return, 각320개
  `integrateNoDriveWheelSpeeds` 호출 전후의 raw `mWheelSpeeds`, 실제 drive/brake/tire/damping,
  원래 float solver dt를 기록한다. ABI1·단일 호출·4wheel·순서/개수·overflow·전후 연속성·setter·
  최종 direct getter를 검사한다. tire callback 생략을 work 누락으로 추정 보완하지 않는다.
  sleeping은 실제 해당 return의 witness와 torque/steer/최종 wheel0이 함께 있어야0 work다.
- **정의:** wheel별 `W = Σ τ_drive,Nm × ω_solver,after,rad/s × dt_solver,s`인 signed discrete
  motor work다. NoDrive의 구동 wheel 회전각 적분에 쓰이는 post-solver ω를 사용한다. torque0의
  렌더링용 회전 보정은 motor work0을 바꾸지 않는다. UE torque의cm²→m² 변환은10000으로 나눈다.
  프레임 끝 속도의 ZOH나 임의 변환 계수를 사용하지 않는다. 이 정의는 chassis/tire/brake까지
  포함한 전체 기계 에너지 보존·연속시간 적분 정확도·OEM 효율의 검증을 뜻하지 않는다.
- **범위:** V1 rear50:50의 모터 축 속도는 후륜 평균이다. 관측된 구동 substep마다 그 평균이
  원래 전진 모델의0..100rad/s 범위를 벗어나면 EV 연결을 거부한다. 음수 절댓값/epsilon/clamp는 없다.
  마찰 brake work는 DC/회생 work에 합치지 않는다. 실제 회생/일반 제동 scenario는 후속 검증이다.
- **원천/시각:** receipt의 UUID/session/actor/generation/frame/ticket 및 원본 Actual proof를
  유지한다. `solver_work.source=PhysX3.4.NoDrive.integrator.postOmega.v1`; 정산 끝은 원래 CARLA
  elapsed seconds를 ns 반올림한 `work_end_ns`다. 기존 `logical_end_ns=begin+10ms`는 명목 끝이며
  float clock으로1ns 차이 날 수 있다. 어느 경우에도 wheel/CAN 취득 시각을 고쳐 쓰지 않는다.
- **정산:** native `--native-solver-work`는 완전한 receipt를 검증한 후 기존 EV owner 하나의
  `step_integrated_motion`만 호출한다. 같은 owner의 ZOH `step`은 호출하지 않고 SimpleVehicle도
  만들지 않는다. scalar wheel은 구간 시작의 원래 취득 표본이다. torque는 서버가 실제 setter에
  적용한 Nm witness이며 source는 그 apply의 원래 frame begin, oldest는 원본 Actual/wheel 의존성이다.
  원본 CAN의 source/sequence는 proof에 그대로 남으며 apply witness가 새 CAN Actual을 만들지 않는다.
  최초 empty INIT의0 setter도 명시적 무입력 관측이며 정상 권한/가짜 Actual이 아니다.
- **다중 주기:** 원래320개 discrete work를 원래 frame begin/end의 동일 ordinal bin에 배분하고,
  native1ms 경계와 겹치는 비율만 각 전기 구간에 보수적으로 배정한다. 원래 solver dt와 frame 전체
  work 합은 보존하며 이 배분값을 새 wheel 취득으로 사용하지 않는다. 끝의1ms 미만 잔여도 그 프레임
  안에서 정산한다. actuator 응답 job·Controller20ms·Zone/vECU10ms·30ms age/10ms skew는 유지한다.
- **commit/중단:** 모델 상태와 cursor는 frame checkpoint를 두며 중간 실패 시 해당 frame의
  actuator/EV 모델 상태·장부를 복원하고 sensor를 무효화한다. 이미 진행된 CARLA physics나 내부
  native 메시지를 되돌릴 수 있다는 뜻은 아니다. 실패한 rig는 폐기하고 fresh process/새 INIT가 필요하다.
  서버는 유효 work receipt 뒤 `settle_work` 전까지 다음 stage를 차단한다. 인증된 단일 local adapter가
  frame/ticket/원래 끝 시각·누적 motor J·에너지 balance를 제출하며 누락/중복/불일치는 clear·latch다.
  누적 J 비교 허용치는 binary64 합산 오차 범위이고 EV의 기존0.00072J balance 기준은 유지한다.
  ACK는 신뢰된 local owner의 결과 보고이며 독립 원격 증명/암호 인증 protocol로 전용하지 않는다.

이 opt-in receipt만 `interval_work_valid=true`다. `normal_driving_enabled=false`는 유지한다.
UE 원본 source/static archive는 보존하고, hash로 고정한 외부 copy에 읽기 전용 observer를 삽입하여
PhysXVehicles module만 별도 빌드한다. 원본 module backup/restore와 실행 binary hash를 기록한다.
Wall2/4ms·계측 비용·renderer·다중 ODD·실차 calibration·signed 회생/일반 정지는 미수용이다.

**결정:** actual-only 경로·단일 actuation writer,10ms world/state·50ms 영상·단일 tick owner,
20/10ms 기존 rate·freshness/권한 보존, 중복 motion/actuator/energy 금지, metadata/좌표 의미,
GT 격리, pause/reset containment, M7-1 비제어 관측 범위. 별도 opt-in functional clock/8-role
barrier는1f, 직접 omega→native Actual 반환은1g, actuator/electrical 분리·원래 wheel 기반 ZOH는1h에서
한정 검증했다.1i는 직접 wheel effort 확장안을 우선 후보로 결정하고 수학/거부 경계를 오프라인
검증했다.1j는 공개 NoDrive SDK에서 합성 Actual의 물리 적용·single-use/pause 경계를 한정 검증했다.
정지 sensor의 임의 오차 보정은 미채택이다. 정상 CARLA driving 수용은 아니다.

**미결정:** smoke 외 server/client 조합의 안정성, V1 외 vehicle geometry/실차 역변환 calibration,
wheel 정지 잡음/전체 ODD validity·wall clock mapping·일반 시나리오의 Actual interval·native wall guard 연동, 일반 주행/회생의 energy telemetry,
Host–Target transport/배치, M10 AI shape/history. 소유자·gate는 기존 TBD-02/03/04/07/09
(energy는 기존 TBD-13)이며 [로드맵](../roadmap.md)에 연결한다. 이번 문서는 주행 통합 승인이나
interface binary freeze가 아니다.
