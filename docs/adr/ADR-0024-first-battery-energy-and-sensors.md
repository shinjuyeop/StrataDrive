# ADR-0024: 첫 Battery 에너지·전기·온도·관측 모델

Date: 2026-10-15. Status: **Host functional SIL component 구현 / 학습자 review PENDING**.
TBD-02/04/13, IF-MODEL-BMS, SYS-EV-005의 부분 검증이다. Full TC-EV-005는 NOT RUN이다.

## 결정과 물리 경계

`simulation/battery/BatteryModel`이 한 simulation clock에서 chemical energy/SOC와
등가 pack 전기·온도 상태를 소유한다. BMS controller와 CAN 통신은 이 모듈에 넣지 않는다.
실제 차량용 calibration, 전하량 추정기, 셀별 chemistry/열화/balancing은 구현하지 않는다.
Pack 전압은 컨택터 뒤 Drive 자체 HV bus의 관측이 아니다. 이 모델이 전원 READY를 선언하지 않는다.

입력은 명시적 interval의 **실제 traction branch DC power와 별도 auxiliary load**다.
Motor/inverter 변환 후 battery 쪽 DC branch를 기준으로 traction power는 방전 양수·반환 음수다.
Wheel torque·speed에서 이 DC power를 산출하는 coupling은 후속이다. Command/허용 limit나
마찰제동을 적분하지 않는다. 반대 부호의 DC 입력 시험만으로 회생 에너지 검증을 주장하지 않는다.

첫 모델은 constant OCV + 저항의 Rint 근사와 lumped thermal model을 사용한다.
고정 OCV 가정에서 `E = Voc × Q`이므로 `SOC = E / capacity_j`가 전하 비율과 일치한다.
가변 OCV/온도별 parameter/RC polarization이나 실차 SOC 추정으로 일반화하지 않는다.
실제 equivalent-circuit 모델은 OCV/저항·capacity의 SOC/온도 의존성을 다룬다
([공식 모델 설명](https://www.mathworks.com/help/simscape-battery/ref/batteryequivalentcircuit.html)).
전하량 기반 SOC 추정은 [Coulomb counting 설명](https://www.mathworks.com/help/simscape-battery/ref/socestimatorcoulombcountingvariablecapacity.html)을 참고한다.

`Pterminal = Ptraction_dc + Paux`, `Vterminal = Voc - I×R`와 `Pterminal = Vterminal×I`를 풀고
`dE/dt = -Voc×I = -(Pterminal + I²R)`로 chemical energy를 갱신한다.
유입/유출 DC·보조 부하·내부 저항 손실을 별도로 누적하며 inverter 손실을 여기서 다시 더하지 않는다.
`Cthermal dT/dt = I²R - G(T - Tambient)`는 interval 내 고정 전력의 해석해로 적분한다.
발생 열을 SOC에서 두 번 차감하지 않는다. Thermal/OCV/저항의 feedback은 이번 근사에 없다.

## Fixture와 에너지 장부

Fixture는 50 kWh(180 MJ), OCV 400 V, R 0.05 Ω, thermal capacity 200 kJ/K,
cooling 20 W/K, ambient/초기 온도 25 °C, 초기 SOC 0.5, series 100개다.
관측 극값 half-spread는 전압 0.01 V·온도 1 °C다. Cell별 물리 분포를 계산한 값은 아니다.
각 DC 항과 terminal 합의 절댓값 상한은 100 kW, step 상한 40 ms, input dependency age는 50 ms다.
예제는 20 ms step을 사용한다. 전부 **독립 시험 parameter**이며 차량 baseline의 TBD-13을 닫지 않는다.

저장 에너지와 네 누적 장부는 compensated summation을 사용한다.
`initial_E - E = drawn_dc - received_dc + auxiliary + ohmic_loss`의 residual을 공개한다.
허용치는 `max(1e-6 J, capacity_j×1e-12)`이며 fixture에서는 0.00018 J다.
Full/empty 초과나 실수 회로해가 없는 부하, 비유한 계산은 step 전체를 거부한다.
에너지/온도/누적값을 일부만 갱신하거나 power를 조용히 clip하지 않는다.
Capacity 위반은 경계 초과 에너지를 보고하며 last committed truth는 진단용으로만 남긴다.

## 시간·identity와 센서

각 interval은 직전 committed 시각부터 연속해야 하며 실제 power가 그 구간에서 일정하다는
명시적 입력이다. 끝 시각에 도착한 새 순간 전력을 과거 구간으로 소급 적용하지 않는다.
Power의 Epoch/source/oldest dependency와 sequence progress/동일 cached sample 불변성을 검사한다.
새 envelope 시각으로 cached dependency를 fresh하게 만들 수 없다. Model batch는 별도 증가한다.
Missing/invalid/stale power, gap·clock·identity 오류는 latch하고 current 관측을 unavailable로 만든다.

SOC, electrical pair, pack temperature, cell voltage pair, cell temperature pair는 독립 관측이다.
각 group은 acquisition Epoch/batch/source와 dependency time을 갖는다.
Acquire/Hold/Invalidate 및 cell pair override로 센서 상실·고정·극값을 주입한다.
Hold는 기존 시각·값·batch를 그대로 유지한다. 새 model batch로 group age를 갱신하지 않는다.
Optional 값 존재는 acquisition의 유효성이며 freshness는 BMS 소비자가 별도로 검사해야 한다.
Sensor override는 관측 주입으로서 physical energy/temperature를 바꾸지 않는다.

초기화에는 알려진 SOC/온도를 명시한다. 반복 초기화는 새 Epoch/비감소 clock의 **scenario reset**이며
새 energy ledger를 시작한다. 단순 ECU 재시작으로 battery SOC를 이 초기값으로 되돌리면 안 된다.
Gap 뒤의 미관측 에너지를 추측하지 않으며 복구·물리 상태 이어받기는 후속 통합 계약이다.

## 증거와 후속

[학습·실행 안내](../learning/m2_battery_model.md), [단위 시험](../../tests/unit/battery_model_test.cpp),
기존 `actuator_demo battery-model`을 확장했다. 30개 신규 unit은 실제 power/zero/unknown,
energy balance·capacity·회로 경계, analytical thermal response, sensor group/hold와 reset을 검사한다.
이 결과는 BMS 한계·보호, contactor/HV lifecycle, CAN 배포나 차량 energy TC의 PASS가 아니다.
다음은 이 관측값의 원천/유효성/age를 검사하는 BMS controller와 charge/discharge limit다.
그 뒤 Power model과 Drive local gate, actual torque/speed→DC conversion을 연결한다.
