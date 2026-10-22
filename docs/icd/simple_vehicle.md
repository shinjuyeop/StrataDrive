# Simple Vehicle / M6 초기 모델 계약

2026-10-22. 모델 revision `simple-vehicle-v1`, MIL `m6-pi-v1`.
후속 [vehicle-energy-v1](vehicle_energy.md)/[ADR-0064](../adr/ADR-0064-vehicle-ev-interval-energy.md)는
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
qualification이 아니다. M8 controller C++ 구현·모델/코드 동등성·차량 SIL은 후속이다.

PI sample20ms, speed acquisition50ms/ZOH/source age60ms, logical plant2ms다.
`u_raw = d(reference)/dt + Kp*e + integral`, Kp1, Ki0.2. 감속 시만120ms preview
(50ms actuator+50ms sensor+20ms controller)를 error용 reference에 반영한다.
판정 reference는 원래 ramp이다. u는[-5,2]m/s²와slew2m/s³로 제한한다.
Amplitude/slew 제한과 error 방향이 같은 때 integral 갱신을 멈추는 conditional integration을 쓴다.
D 항은 넣지 않았다. 이 noise-free 저차 plant에서 측정 미분 없이 기준을 만족하는 첫 후보다.

실행 누락·stale/invalid/future/old Epoch/변조 cached sample·permission loss는 invalid output과
latch를 만든다. 정상 command0으로 성공을 가장하지 않는다. 명시적 새 INIT만 상태를 초기화한다.
이 model INIT는 실제 시스템 신뢰 경로의 대체물이 아니며 M8 integration 때 연결해야 한다.
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
