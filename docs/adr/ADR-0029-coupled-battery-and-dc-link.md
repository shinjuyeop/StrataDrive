# ADR-0029: Battery와 실제 DC-link 회로의 에너지 연결

Date: 2026-10-16. Status: **Host functional SIL component 구현·시험 / 학습자 review PENDING**.
TBD-03/12/13/14의 부분 구현이다. 실제 Central/Zone runtime·차량 motion과 전체 TC-REG/EV/ZON은 NOT RUN이다.

## 결정과 책임

`simulation/power/EvPowerModel`이 기존 BatteryModel·PowerModel과 공통 motor power 계산을 묶는다.
별도의 배터리 장부를 만들지 않는다. BatteryModel은 chemical energy/SOC·battery 저항 발열,
PowerModel은 접점/커패시터, composition은 motor·경로 손실 장부를 소유한다.
두 물리 모델을 candidate로 계산하고 전체 에너지 검사까지 성공해야 함께 commit한다.
한쪽 실패에 capacitor만 진행하거나 SOC만 바뀌는 부분 commit은 없다.

기존 이상적 경로 DriveEnergyModel과 독립 Power fixture는 설명·회귀 목적으로 유지한다.
Motor conversion/copper/idle 식은 `calculate_motor_power` 하나를 공유한다.
ECU 소프트웨어인 BmsController/PowerController/DriveController는 physical truth가 아닌 별도 sensor port를 소비한다.
Model Epoch/초기 capacitor charge와 SOC는 물리 scenario 초기값이고 ECU session 재시작으로 리셋하지 않는다.

## 회로와 입력

Battery source는 constant Voc=400 V와 Rint=0.05 Ω다. 두 실제 main contactor·precharge 병렬 경로,
DC-link C=0.002 F, precharge 50 Ω·main 0.02 Ω·bleed 100 Ω와 접점 지연 20 ms를 재사용한다.
PowerModel은 기존 held bus-current fixture와 별도로 명시적인 bus-power mode를 제공한다.
두 load 표현을 동시에 사용하지 않는다. Coupled mode의 source voltage는 OCV이고 output pack voltage는
Rint를 거친 실제 terminal voltage다. Pack과 bus voltage를 같은 값으로 두지 않는다.

Motor의 actual torque와 wheel rad/s는 begin acquisition으로 ZOH한다. Inverter가 실제 enabled이면
그 actual의 DC power가 bus의 constant-power load다. Inverter off인데 actual torque가 남아 있으면
입력 오류로 중단한다. Permission Inhibit를 physical torque/전류 0으로 대체하지 않는다.
Standalone speed는 외부 20 rad/s fixture이며 vehicle kinetic energy를 구현한 것은 아니다.

Auxiliary는 이번 회로에서 **pack-side actual current 0.375 A**다. Power는 terminal voltage×current로
계산하므로 이전 ideal-path의 고정 150 W fixture와 구분한다. HV contactor가 열려도 이 branch는 남는다.
OFF를 battery 소비 0으로 해석하지 않는다. ECU/LV sleep·DC/DC·auxiliary 차단 모델은 후속이다.

## 적분과 보존

Auxiliary current를 Ia, 접점 경로 conductance를 gp, bleed를 gd라 하면
`G = gp/(1+Rint×gp)`, `Vs = Voc−Rint×Ia`다.
Path current는 `G×(Vs−Vbus)`, battery current는 path+Ia이며
`C dVbus/dt = path_current − gd×Vbus − Pmotor_dc/Vbus`를 푼다.
P=0·bus=0은 유효하다. 실제 load가 있는데 무전압/수치적으로 불가능한 구간은 오류로 보고한다.

접점 event에서 interval을 나누고, 각 구간은 implicit midpoint로 적분한다.
최대 내부 step 50 µs를 electrical time constant 이하로 제한하고 1 ns 이하 분해능이나
200,000개 초과 substep이 필요한 구간은 거부한다. 이것은 ECU task period/실시간 보장이 아니다.
Constant-power 식의 high-voltage quadratic root를 사용하며 voltage/current를 임의 clip하지 않는다.

BatteryModel의 새 `step_integrated` 입력은 구간 전체의 q=∫I dt, ∫I² dt, endpoint current와
pack branch/auxiliary energy다. Source는 end, oldest dependency는 begin 이하라는 별도 interval 계약이다.
Ending current를 구간 전체에 소급하지 않는다. Heat는 Rint×∫I²dt이며 square(mean I)와 다르다.
양방향 전류의 net charge가 0이어도 저항 발열은 생길 수 있다.
Endpoint electrical sensor와 interval-mean 진단 power도 구분한다.

Flow는 energy identity·Cauchy moment bound·power peak·identity/time·capacity를 검사한다.
Constant-power/integrated-current 입력 mode는 같은 battery scenario에서 바꾸지 않는다.
Thermal update는 interval 평균 heat를 사용한 lumped approximation이다. 전류 시간 파형의 정확한
열 convolution이나 실제 부품 온도 모델을 구현한 것은 아니다.

```text
initial_battery_energy − battery_energy
  = capacitor_energy − initial_capacitor_energy
  + signed_mechanical_work + motor_loss + auxiliary_energy
  + battery_ohmic_loss + precharge_loss + main_path_loss + bleed_loss
```

Coupled tolerance는 max(1e−6 J, capacity×4e−12), 50 kWh에서 0.00072 J다.
이 잔차는 이산 계산의 보존 검사이며 실차 정확도·보호 deadline을 뜻하지 않는다.
고립된 capacitor에 회생하면 capacitor 에너지가 증가하고 battery를 가상 충전하지 않는다.
Capacity/회로 domain을 벗어나면 latch/unavailable과 원래 fault를 보고하며 두 물리 state를 commit하지 않는다.

물리 관계의 참고는 [Capacitor 공식 설명](https://www.mathworks.com/help/simscape/ref/capacitor.html),
[Battery equivalent circuit](https://www.mathworks.com/help/simscape-battery/ref/batteryequivalentcircuit.html)이다.
수치 solver·fixture parameter·적분 port는 StrataDrive의 결정이며 외부 도구와 등가 검증은 하지 않았다.

## 연결 fixture와 고장

기존 CLI `ev-power`는 actual Battery→BMS limits/local gate→PowerController→접점/회로,
독립 trusted Central request/grant·명시적 limits relay→DriveController→TorqueResponse→실제 motor power를 연결한다.
PowerStatus·DriveActual은 기존 P05 codec/receiver도 통과한다. 실제 Central coordinator/Zone/DDS 구현은 아니다.
Drive의 로컬 HV acquisition은 물리 bus 측정이며 CAN PowerStatus를 측정값으로 복사하지 않는다.
Power current sensor를 unknown/hold해도 internal physical flow는 계산한다. 제어기는 이를 sensor fallback으로 쓰지 않는다.

이번 combined fixture만 opening-current threshold를 0.5 A로 둔다. Nominal aux 0.375 A와 구분하고
20 ms low-current dwell·actual contact-open·실제 잔류 voltage 확인을 거친다. Legacy fixture의 5 A default는 유지한다.
Drive fixed reserve는 500 W다. Normal bus ≥300 V·pack ≤450 V에서 max motor DC 약33.56 kW,
main-path loss 상한 약250.3 W + idle50 W + aux≤168.75 W를 덮는다.
이는 steady target budget이며 capacitor recharge/finite actual residual의 순간 power를 hard-limit한 결과가 아니다.

Normal shutdown에서 Central Inhibit 후 actual torque가 줄고, physical inverter stage는 torque 0 뒤 disable된다.
기존 Drive gate는 활성화 후 Inhibit를 latch하므로 종료 뒤 Drive fault=PermissionInhibit를 유지한다.
이는 power OFF 성공과 별개이며 자동 재허가/재출발을 구현한 것이 아니다.
Weld는 OPEN_CONTACTORS/blocked, current unknown·지속 10 A aux는 WAIT_CURRENT/blocked다.
Timeout을 접점 강제 개방 허가나 성공한 OFF로 해석하지 않는다.

## 검증과 후속

[학습·실행](../learning/m2_ev_power_circuit.md)에 결과와 재현 명령을 남긴다.
새 29개(Ev circuit 24개·Battery integrated-flow 5개)로 normal·ASan/UBSan 전체 unit은 391개다.
RC analytic/event·step refinement, capacitor 단독 discharge/regen, 10,000 alternating interval 장부,
원천/unknown·mode/epoch/transaction·capacity와 normal/고장 네 combined CLI loop를 검사한다.
정적 분석·production build 및 기존 Power/Drive energy/Drive gate demo 회귀를 구분해 기록한다.
Wire/transport는 추가하지 않으며 과거 vCAN 97개 이력과 gate 단계의 3개 재검사를 보존한다.
다음은 M2의 미결정 parameter·task/monitor 경계·fault/session 수용 항목과 학습자 review를 정리한 뒤 M3 timing 측정이다.
차량 motion/마찰 배분·hardware 보호·정밀 motor/chemistry·RTOS/분산 runtime·full TC는 후속이다.
