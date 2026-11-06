# Simple Vehicle / M6 초기 모델 계약

2026-10-22. 모델 revision `simple-vehicle-v1`, MIL `m6-pi-v1`.
후속 [vehicle-energy-v1](vehicle-energy.md)/[ADR-0064](../archive/design-decisions.md#adr-0064)는
선택형 Host 물리 경로를 같은 구간 work의 vehicle/EV 결합으로 확장했다. 아래 첫 v1의
ZOH 비교 한계와 초기 실행 결과는 당시 기록이며 최신 수용 상태는 후속 evidence를 따른다.
기존 M5 accepted fixture는 그대로이며 `front_run.py --three --simple-vehicle`로만 활성화한다.
`profiles/reference.yaml`은 설계 기록이며 runtime loader가 아니다. 실제 값은
`simulation/vehicle/simple_vehicle.hpp`의 config와 Python model의 상수다.

## 단일 소유권과 경계

| 실행자 | 입력 → 출력 | 원천/권한 |
| --- | --- | --- |
| persistent SIL physical process | 기존 SteeringResponse·BrakePressureResponse·DriveSilPlant의 actual → SimpleVehicle | 명령/limit/permission을 actual로 쓰지 않음 |
| SimpleVehicle | actual aggregate driven wheel torque(Nm), friction pressure(Pa), road-wheel angle(rad) → rear-axle x/y(m), yaw(rad), speed(m/s), wheel speed(rad/s) | 물리 model epoch7; ECU INIT/rejoin은 reset 못 함 |
| EV electrical model | 같은 interval 시작의 torque·계산된 wheel speed → 기존 circuit/Battery | energy/SOC owner는 기존 EvPowerModel; 차량 모델이 SOC를 쓰지 않음 |
| Rear Drive | 원래 source의 wheel-speed sensor → 기존 CAN/P05 Actual → Rear → SOME/IP → Central validator | 새 speed/health를 Central에서 합성하지 않음 |
| 독립 Python MIL | reference/actual speed/permission 입력 → bounded acceleration 또는 invalid | 설계 모델만 존재. 실제 SessionCoordinator/RunLease를 발급하지 않음 |

기존 Central allocation fixture의0.2m/s²·curvature0.02 요구는 유지한다. 이것은 실제
속도 폐루프가 아니다. 물리 bus는 기존 센서/물리 output용이며 network 명령/권한을 우회하지 않는다.
Application epoch·원래 source/expiry·20ms envelope·host10-v1·2ms/4ms guard는 바꾸지 않는다.
물리 state CSV는 기존 bounded buffer에서 종료 뒤 쓰며 control loop에서 flush하지 않는다.

## 차량 수식과 적분

평지·전진 전용, mass1000kg / radius0.3m / wheelbase2.7m / friction0.001Nm/Pa는
기존 allocator fixture와 일치한다. rolling100N, drag coefficient0.4N/(m/s)²는
명시적 SIL 설계 가정이다. OEM calibration/타이어 slip/경사/기어/피치/후진은 없다.

`Fmotor=Tactual/r`, `Ffriction=Pactual*0.001/r`, `Froad=100+0.4*v²`,
`a=(Fmotor-Ffriction-Froad)/1000`. Interval 시작의 actual/road force를 ZOH한다.
속도가0에 닿으면 정확한 stop-crossing 시간까지만 이동하고 역행을 만들지 않는다.
거리 `ds=(v0+v1)/2*dt_moving`; curvature `tan(delta)/2.7`, exact circular-arc 이동,
직선 극한 sinc를 사용한다. Energy ledger는 각 힘×실제 interval 거리와 kinetic energy를 비교한다.
EV electrical은 기존 beginning-speed ZOH power를 쓰므로 두 적분의 quadrature 차이를
전체 차량/전기 energy 보존 증명으로 해석하지 않는다. 물리 소유권 중복은 없다.

입력은 기존 ModelMeasurement(value, model epoch/sequence/source, oldest input)를 사용한다.
연속 begin/end·step<=20ms·입력 age<=30ms·skew<=10ms·finite/range·sequence/동일 sample
불변을 검사한다. 실패하면 차량 상태를 commit하지 않는다. 실제 wall-time process는 기존
약0.5ms release, component analytic/MIL은 별도 logical time이다. 지연 호출을 새 sample로
보간하거나 미관측 구간을 임의 substep으로 숨기지 않는다.

## MIL / 도구 결정

TBD-16의 첫 pilot은 Python3 표준 라이브러리/binary64로 선택했다. 설치/license/자동 생성
없이 diff/replay가 가능하고 모델은 별도 실행된다. MATLAB/Simulink 제품 채택이나 tool
qualification이 아니다. M8의 수작업 C++ SpeedPI와 공통 vector 동등성은
[component 범위](../test-plan/evidence/m8_speed_pi/README.md)에서 검증했다.
C++의 SimpleVehicle 논리 시간 폐루프는 아래 별도 경계를 따른다.

PI sample20ms, speed acquisition50ms/ZOH/source age60ms, logical plant2ms다.
`u_raw = d(reference)/dt + Kp*e + integral`, Kp1, Ki0.2. 감속 시만120ms preview
(50ms actuator+50ms sensor+20ms controller)를 error용 reference에 반영한다.
판정 reference는 원래 ramp이다. u는[-5,2]m/s²와slew2m/s³로 제한한다.
Amplitude/slew 제한과 error 방향이 같은 때 integral 갱신을 멈추는 conditional integration을 쓴다.
D 항은 넣지 않았다. 이 noise-free 저차 plant에서 측정 미분 없이 기준을 만족하는 첫 후보다.

실행 누락·stale/invalid/future/old Epoch/변조 cached sample·permission loss는 invalid output과
latch를 만든다. 정상 command0으로 성공을 가장하지 않는다. 명시적 새 INIT만 상태를 초기화한다.
이 model INIT는 실제 시스템 신뢰 경로의 대체물이 아니다. C++ adapter는 기존 session release의
application epoch/enable로 초기화하며, 물리 모델을 초기화하지 않는다.
MIL plant/actuator는 독립 Python 근사(50ms delay,torque1000Nm/s,pressure5/10MPa/s)다.
C++ 실제 actuator/전원 모델을 호출한 것처럼 보고하지 않는다. 상세 case/판정은
[사전 protocol](../test-plan/evidence/m6_simple_vehicle/protocol.md)을 따른다.

## 실제 이동에서 드러난 정상 정지 경계

NormalStop은 속도/torque/floor만으로60ms 확인하면 압력이 아직 하강하는 동안 terminal
Hold로 인계할 수 있었다. 새 조건은 기존 standing-hold 목표100kPa(+1000Pa)에 도달한 뒤
같은60ms 동안 실제 brake pressure가 anchor로부터
한 wire step1000Pa 안에 머무는 것이다. 움직이면 기존 dwell을 다시 시작하고 원래5s
braking timeout은 유지한다. 수용한 lease의 source/expiry와2s shutdown, Leaf monitor는
변하지 않는다. 같은 cached acquisition은 dwell을 진행시키지 못한다.

수식 배경은 공식 [Vehicle Body](https://www.mathworks.com/help/vdynblks/ref/vehiclebody1doflongitudinal.html),
[Bicycle kinematics](https://www.mathworks.com/help/robotics/ug/mobile-robot-kinematics-equations.html),
[anti-windup](https://www.mathworks.com/help/simulink/slref/anti-windup-control-using-a-pid-controller.html)을
참고했다. 이 프로젝트의 간소화·parameter·120ms preview는 별도 설계 선택이며 해당 제품의 검증 결과가 아니다.

## 서로 다른 sampling 계약

실제 Host wheel sensor는 persistent physics의 약0.5ms acquisition에서 생성되고 기존
Drive source-age30ms 검사를 그대로 사용한다. MIL의20Hz sensor/60ms age는 별도 모델 입력
계약이다. 이것을 실제 Drive freshness로 옮기지 않았다. M7의20Hz CARLA state를30ms
Drive auxiliary 한계에 그대로 연결할 수 있다고 가정하지 않는다. 해당 sensor/clock 경계와
원천 시각을 보존하는 multirate 설계는 M7 전에 결정할 후속 항목이다.


## C++ 속도 폐루프의 논리 시간 경계

기본 M4 fixture는 유지하고 `M4Config::speed_loop`에서만 SimpleVehicle을 연결한다.
기존 8 participant의 INIT/ACK/release 이후 Central의 `SpeedRequest`가 검증된
`DriveReceiver::current_sample`을 받아 wheel rad/s × radius0.3m로 변환한다.
Drive Actual wire에는 별도 physical epoch/sequence가 없으므로 application epoch와
원래 wheel source timestamp를 입력 cursor로 사용한다. 매20ms 새 acquisition을
요구하고, 같은 wheel source를 새 Actual envelope로 갱신해도 거부한다.

VehicleRequest는 wheel source에 보수적으로 rooted되며 expiry는 source+30ms+1ns다.
이를 통해 기존 CommandContext의 oldest input/expiry 경계를 그대로 사용한다.
모델 자체의60ms age를 runtime으로 확대하지 않는다. 정상 arm과 receiver의 현재
AllowNormal grant를 함께 확인하며, 실패하면 acceleration0을 발급하지 않고 보호를 요청한다.

첫 계산은 정상 arm 뒤 allocation release+1ms에 시작해 새 Leaf→Zone→Central
피드백을 읽는다. PI20ms와 Host10ms allocation은 분리된다. 실제 물리는1ms,
owner poll0.2ms이며 이는 wall clock 지터를 허용한 scheduler 계약이 아니다.
목표0은 explicit standstill hold를 요청한다. 87초 profile 후 새 정상 root 생산을
중단하고 기존 NormalStop으로 인계해 pressure dwell·contactor open·HV off를 확인한다.

[폐루프 프로토콜](../test-plan/speed-loop-protocol.md)과
[실행 근거](../test-plan/evidence/m8_speed_loop/README.md)를 따른다.
실제 SOME/IP/vCAN·RunLease 전송과 CARLA 연결은 이 논리 시간 시험 범위 밖이다.

## M8 추진 배분 포화 feedback v2

2026-11-01. 선택형 `model_v2.py`/`SpeedPI::step(..., propulsion_saturated)`는 기존
출력 계산과 제한을 유지하고, 직전 배분이 양수 추진 요청을 제한했으며 현재 error가
양수일 때 integral 증가를 보류한다. 음수 error는 기존 내부 제한 조건 아래 적분한다.
외부 flag=false는 v1과 동일하다. 실제 actuator torque를 추정하는 보상은 아니다.

`SpeedRequest(radius, true)`는 첫 release에서 보수적으로 양수 적분을 보류한다.
이후 Central의 성공한 `PropulsionSelection`만 사용한다. 같은 epoch·직전 request
sequence·이전 release 이상 현재 release 미만의 selection 시각·30ms age·단조 cursor,
이전 acceleration과 유한한 요청/선택 토크·limited 일관성을 확인한다. 누락/불일치는
출력 없이 latch하며 새 INIT가 필요하다. 선택 이력은 sensor나 permission이 아니므로
기존 wheel30ms ingress, request30ms/input60ms dependency와 child expiry를 바꾸지 않는다.
토크는 CAN 반올림 전 배분값이며 양자화 오차만으로 포화 판정을 만들지 않는다.

`inertial_ramp_feasible`은 유한한 전진 목표와 기간에 대해 `m*r*dv/dt`의
추진/제동 상한 필요조건을 검사한다. CARLA opt-in fixture는1696kg/.355m/300Nm/1500Nm다.
경사·도로 저항·동적 BMS 제한을 포함한 추종 가능성 보장은 별도다.
[고정 protocol](../test-plan/propulsion-saturation-protocol.md)과
[실행 근거](../test-plan/evidence/m8_saturation/README.md)를 따른다.

## M8 제동 배분 피드백 v3

2026-11-06. 현행 opt-in `SpeedRequest(radius, true)`와 `--propulsion-aware`는 v3다.
동결된 v1/v2 모델과 이전 실행 증거는 유지하며, 새 trace/result는
`allocation_feedback_schema=3`을 명시한다. `SpeedPI::step`의 마지막 선택 인자인
braking_saturated가 true이고 error<0이면 음수 적분 누적을 보류한다. 기본 false는 기존
v2와 같고 반대 방향 적분은 기존 내부 제한 조건을 따른다. 첫 release는 양방향 보류다.

성공한 배분의 `requested_braking_nm`, `selected_braking_nm`, `braking_limited`는
양자화 전 회생+마찰 선택을 나타낸다. 명령 합성·물리 Actual·권한은 구별한다.
잔류 회생에 의한 마찰 명령 보류도 반영하며, 정상 fractional blend의 부동소수점 왕복
오차만으로 포화 flag를 만들지 않는다. 기존 BrakingCapacity/Deficit/Excess 보호를 유지한다.
원래 epoch/직전 request/시각/source 검증과 code reason7은 그대로다.
[사전 기준](../test-plan/milestone-followup-protocol.md)과
[component·원본 입력 재생·새 S03 근거](../test-plan/evidence/milestone-followup/README.md)를 따른다.
새 CARLA 고정 S03 8000구간도 기존 기준을 통과했다. 전체 도로/동적 참조 수용은 별도다.
