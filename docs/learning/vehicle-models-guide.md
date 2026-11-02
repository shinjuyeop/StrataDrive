# 응답·전원·에너지 모델

## ECU 판단과 물리 응답

ECU는 유효한 명령·sensor를 검사해 목표와 보호를 결정한다. Plant는 delay/rate/saturation·
타이어/차체·전원 회로 같은 물리를 진행하고 독립 취득값을 제공한다.
`prepare`/`complete` 사이의 typed sensor/actuation port를 따라 읽는다. ECU가 plant를 직접 소유하지 않는다.

| 주제 | 코드에서 찾을 경로 | 구분할 개념 |
| --- | --- | --- |
| 조향·브레이크 | `vecu/steering/`, `vecu/brake/`, `simulation/steering/`, `simulation/brake/` | 정상 delay/rate 범위와 residual/dwell, 통신 loss와 response fault |
| Drive | `vecu/drive/`, `simulation/drive/` | signed motor target·Actual, normal gate와 capability, zero 요청과 잔여 torque |
| Battery·BMS | `simulation/battery/`, `vecu/bms/` | 물리 SOC/V/I/thermal 관측과 충방전 허용 판단 |
| Power | `simulation/power/`, `vecu/bms/`의 Power controller | 프리차지·접점·RC/current의 실제 응답과 READY permission |
| 차량·EV | `simulation/vehicle/`, `simulation/drive/` | 단일 motion owner, 같은 구간 work·전기 정산 |

## 예제 실행

[core 빌드](../../README.md#시작하기) 후 도움말에서 도메인별 입력을 확인한다.

```sh
build/m1-angle/actuator_demo --help
build/m1-angle/actuator_demo steering-model jam
build/m1-angle/actuator_demo ev-power normal
```

예제의 모델·수치는 fixture다. 실제 차량 calibration이나 CARLA 전체 fidelity의 근거가 아니다.
정상 지연·변화율·포화는 [조향 응답 그래프](steering-response.html)에서 바꿔 볼 수 있다.

## 보호를 관측하는 순서

명령 loss/센서 오류 검출 → 보호 목표 선택 → actuation 전달 → 실제 torque/압력/각도 →
차체 응답을 따로 관측한다. Steering hold, Brake increase-only floor, Drive zero motor target은
초기 SIL 정책이다. ACK가 왔거나 목표0을 선택했다고 실제 출력0·안전 정지를 선언하지 않는다.

Sensor source가 멈췄는데 새 feedback counter만 증가하는 상황도 검사한다.
Fault latch와 unavailable은 원인 해소만으로 자동 해제하지 않고 새 INIT·입력 재검증을 거친다.
정확한 요구/수치·도달 시한은 [안전](../requirements/safety-requirements.md),
[시간](../requirements/timing-requirements.md), [물리 응답 계약](../interfaces/vehicle-energy.md#physical-response-contract)을 따른다.

## 전기·에너지 장부

Battery 물리 모델과 BMS 판단을 분리한다. Terminal 전력은 traction DC와 auxiliary를 합하고,
화학 에너지에는 저항 손실도 반영한다. 회생 토크가 음수여도 보조 부하가 크면 SOC는 감소할 수 있다.

```text
Pterminal = Ptraction_dc + Paux
Vterminal = Voc - I*R
chemical_power = Voc*I = Pterminal + I^2*R
E_next = E_previous - chemical_power*dt
```

방전 I>0·충전 I<0이며 저항 손실은 양쪽 모두 nonnegative다.
회로는 end current와 구간 current/heat 적분을 구분하고, 후보 state·ledger를 함께 commit한다.
차량 motion과 EV는 같은 구간 motor work를 사용한다. Regen motor work와 friction loss를 합쳐
둘 다 배터리에 회수한 것으로 세지 않는다. 실제 측정 wheel과 speed/radius 추정도 구분한다.

M6의 [차량 모델](../interfaces/simple-vehicle-model.md)·[energy 계약](../interfaces/vehicle-energy.md)과
CARLA의 [관측 work](../interfaces/carla-plant-adapter.md#solver-work와-단일-ev)는 별도 경계다.
M6 Python MIL은 `models/longitudinal/`의 독립 모델이다. M8의 `central/longitudinal/`은
이를 수작업 C++17로 옮긴 순수 SpeedPI component이며 [공통 입력 동등성](../test-plan/evidence/m8_speed_pi/README.md)을
검증했다. `initialize`/`step`에서 상태와 출력을 비교하며 invalid acceleration은 absent다.
`SpeedRequest`는 이 component를 검증된 Drive Actual·기존 session/permission에 연결한다.
20ms마다 bounded acceleration을 만들고 기존 allocation이10ms마다 갱신한다.
명령이 물리를 직접 바꾸지 않으며 Leaf의 실제 torque/pressure가 차량 입력이다.
[SimpleVehicle 논리 시간 폐루프](../test-plan/evidence/m8_speed_loop/README.md)는 검증했고,
[CARLA 저속 속도 폐루프](../test-plan/evidence/m8_carla_speed/README.md)도 검증했다.
CARLA는0.355m 반경을 쓰며 계산된 요청의 생성 시각과 원래 wheel 취득 시각을 따로 보존한다.
[Pure Pursuit](../interfaces/lateral-route-controller.md)를 추가해 고정 곡선30km/h의
[첫 경로 추종](../test-plan/evidence/m8_route/README.md)도 검증했다. 원본 pose를 실제
rear-axle로 변환하며 전체 Reference와 Planner/localization은 후속이다.
이 흐름을 설명하는 개인 학습 review는 별도다.

추진 포화는 PI 출력 범위와 실제 배분 범위가 다를 때 중요하다. 예를 들어 PI가
요청한 가속도에500Nm가 필요해도 배분기는300Nm만 선택할 수 있다. 이때 속도 오차를
계속 적분하면 제한이 풀린 뒤 과도한 가속을 요청할 수 있다. 선택형 v2는 직전 요청의
배분 제한을 확인해 양수 적분을 보류한다. 이 정보는 실제 모터 토크나 주행 권한이
아니다. [구현 계약](../interfaces/simple-vehicle-model.md#m8-추진-배분-포화-feedback-v2)과
[모델 비교·CARLA 근거](../test-plan/evidence/m8_saturation/README.md)를 함께 읽는다.
