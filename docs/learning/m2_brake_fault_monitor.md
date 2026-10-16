# M2: 브레이크가 가압·감압 요청에 반응하지 않는다면

Date: 2026-10-16. Status: **Host functional SIL 구현·검사 / 학습자 직접 재현·수용 PENDING**.
[ADR-0031](../adr/ADR-0031-brake-local-response-monitor.md)에 설계 결정을 기록했다.
기존 [압력 응답](m2_brake_model.md)과 [Steering monitor](m2_steering_fault_monitor.md)의 후속이다.

## 새 메시지를 받는 것과 제동 응답이 정상인 것은 다르다

압력 목표가 1 MPa여도 정상 모델은 50 ms 기다리고, 가압 속도 5 MPa/s로 올라간다.
정상 가압 중에는 목표보다 압력이 낮다. 반대로 0 Pa로 해제해도 delay와 감압 시간이 필요하다.
그래서 목표와 Actual이 다르다는 사실만으로 고장이라고 판단하지 않는다.

| 책임 | 코드 / 입력 |
| --- | --- |
| 물리 응답 | [BrakePressureResponse](../../simulation/brake/brake_pressure_response.cpp): delayed bounded target, 가압/감압, stuck·방향별 속도 주입 |
| 센서 취득 | [PressureMeasurement](../../interfaces/brake/brake_pressure_sensor.hpp): 물리 epoch, 취득 번호/시각, 압력; cache·invalid·override 분리 |
| 고장 판단 | [BrakeResponseMonitor](../../vecu/brake/brake_response_monitor.cpp): issued target 이력과 센서만 사용 |
| 통신·보호 연결 | [BrakeActuator](../../vecu/brake/brake_actuator.cpp): receiver/P05, 상태·latch와 보호 출력 요청 |

이들은 현재 single-owner SIL adapter에서 실행한다. OS/RTE task나 hydraulic feedback controller를 만든 결과는 아니다.
센서가 없을 때 plant의 diagnostic getter를 대신 사용하지 않는다.

## 정상으로 예상되는 압력 범위

첫 유효 센서로 초기 상태를 잡고, 이후에는 목표 이력으로만 정상 압력 범위를 전파한다.
가압은 **4..6 MPa/s**, 감압은 **8..12 MPa/s**를 허용한다. 각각 nominal의 0.8..1.2배다.
기존 nominal의 순간 변화량을 실제 센서의 매 관측값으로 재설정하지 않는다.
그렇게 하면 움직이지 않는 센서를 정상 기준으로 계속 따라가게 된다.

```text
rate(x) = target >= x ? rise_rate : fall_rate
move(x, dt) = x + clamp(target - x, -rate(x) × dt, rate(x) × dt)
next_lower = min(move(lower, slow_rates), move(lower, fast_rates))
next_upper = max(move(upper, slow_rates), move(upper, fast_rates))
residual = max(lower - measured, measured - upper, 0)
```

각 delayed target의 due time에서 구간을 나누며 물리 한계 1.5 MPa로 제한한 목표를 사용한다.
2 MPa 요청 뒤 1.5 MPa 포화는 이 fixture에서 정상이다.
정상 범위에서 **25 kPa = 0.025 MPa = 0.25 bar**를 더 벗어나는지 본다.
이는 CAN pressure step 1000 Pa의 25배이며, 실제 센서 사양에서 도출한 허용 오차는 아니다.

초과가 새 acquisition의 source time으로 **60 ms** 이어지면 ResponseError다.
확정 전에는 DEGRADED, 정상 범위 복귀 시 pending을 해제한다.
확정 뒤에는 FAIL_SAFE/LocalProtection과 latch를 유지한다. Late command나 물리 고장 해제로 자동 복귀하지 않는다.
이 60 ms는 residual 확인 시간이다. 물리 고장 onset부터의 총 검출 시간이나 기존 stream-loss 100 ms 계약과 다르다.

## 가압 실패와 감압 실패, 그리고 보호 요청

가압 고장에서는 관측 압력이 정상 범위보다 낮다. 감압 고장에서는 정상 범위보다 높다.
두 방향의 rate가 다르므로 예상 범위도 별도로 계산한다.

고장을 확정하면 기존 normal pending을 버리고 **압력을 낮추지 않으며 floor 1 MPa까지 가압하는 출력**을 요청한다.
이는 첫 SIL의 increase-only primitive다. 실제 밸브·펌프 동작이나 안전 제동 정책의 확정이 아니다.
물리 stuck은 이 요청 뒤에도 남으므로 낮은 압력이 그대로일 수 있다.
감압에 실패해 압력이 높은 경우에도 floor가 관측된다는 이유로 고장을 해제하지 않는다.

`protection_floor_observed`는 새 유효 센서에서 압력이 floor 이상인지 알려 준다.
센서가 없거나 같은 acquisition을 재조회했다면 unknown이다. 물리 truth로 true를 채우지 않는다.
True는 감압 성공·차량 정지·센서 정확성을 보증하지 않는다. 단일 센서의 plausible bias도 남을 수 있다.

## 센서가 멈추거나 잘못된 값을 보낼 때

- 같은 압력의 **새 취득**은 정상 hold 또는 물리 stuck에서 모두 가능하다. 번호와 source time은 함께 진행한다.
- **Cached 취득**은 번호/시각/값이 그대로다. 반복 polling으로 dwell을 채우거나 새 pressure Actual을 만들지 않는다.
- Source age 20 ms 초과, fresh 취득 사이 gap 30 ms 초과는 SensorUnavailable이다.
- Missing·NaN·범위 밖·wrong epoch·미래/세션 이전 시각·identity 위반을 구분해 거부한다.

관측 gap은 고장을 latch한다. 그 뒤 개별적으로 유효한 새 측정이 오면 FAIL_SAFE 상태에서 압력을 보고할 수 있다.
CAN Actual에 별도 sensor timestamp field가 없으므로 adapter는 새 유효 취득만 압력으로 발행한다.
Held/invalid report는 unavailable이며 downstream의 마지막 유효 압력 RX를 갱신하지 않는다.

새 trusted application epoch는 ECU latch/command pending을 초기화하지만 실제 압력과 센서 취득 번호를 보존한다.
Old sensor를 재사용하지 않고 새 측정으로 시작한다. 물리 stuck이 계속되면 다시 검출한다.
한 센서의 fresh한 잘못된 값도 response residual을 만들 수 있으므로 ResponseError만으로 기계 원인을 확정하지 않는다.
움직임을 요구하지 않거나 정상 interval 안에 고정 압력이 남는 상황에서는 검출을 보장하지 않는다.

## 실행과 로그

```sh
cmake --build build/m1-angle -j 4
ctest --test-dir build/m1-angle --output-on-failure
build/m1-angle/actuator_demo brake-model stuck-rise
build/m1-angle/actuator_demo brake-model slow-rise
build/m1-angle/actuator_demo brake-model stuck-release
build/m1-angle/actuator_demo brake-model slow-release
build/m1-angle/actuator_demo brake-model sensor-hold
build/m1-angle/actuator_demo brake-model sensor-invalid
build/m1-angle/actuator_demo brake-model transient
```

인자 없는 `brake-model`은 기존 가압→해제→command 상실→floor 예제다.
모든 demo는 manual clock이며 물리 주입은 명시한 begin 이후 구간, 센서 주입은 end acquisition에 적용한다.

| Scenario | 관측 결과 / 의미 |
| --- | --- |
| normal | 정상 saturation/release 후 command 상실을 690 ms에 검출; 유한 보호 가압으로 1 MPa 도달 |
| stuck-rise | 100 ms부터 실제 200 kPa 고정·새 command/sensor 유지; 120 ms pending, 180 ms ResponseError; 보호 뒤에도 200 kPa, floor observed=false |
| slow-rise | 100 ms부터 가압 속도 0.25배; 130 ms pending, 190 ms ResponseError, 당시 312.5 kPa; 이후 느린 보호 가압은 지속 |
| stuck-release | 310 ms 해제 목표, due 360 ms부터 물리 stuck; 370 ms pending, 430 ms ResponseError; 1 MPa가 남아도 해제 성공이 아님 |
| slow-release | 360 ms부터 감압 속도 0.25배; 370 ms pending, 430 ms ResponseError, 당시 825 kPa; 이후 floor까지 보호 가압 |
| sensor-hold | 마지막 취득 100 ms; 110 ms부터 pressure unavailable, 130 ms SensorUnavailable; 내부 압력이 올라가도 floor observed=unknown |
| sensor-invalid | 110 ms NaN 취득에서 SensorInvalid; pressure/floor observed는 unknown |
| transient | 160 ms 한 번 outlier는 DEGRADED; 170 ms 정상 복귀로 pending 해제, latch 없음 |

`pressure_pa`는 발행 측정값, `physical_pa`는 시험용 truth다. `expected_min_pa/max_pa`와
`residual_pa`, `sensor_source_ms`, `violation_ms`, `fault`를 함께 읽는다.
Response fault 뒤 range/residual은 확정 당시 증거로 남긴다. 출력 주기와 acquisition의 freshness를 혼동하지 않는다.

## 검증과 다음 단계

새 unit 40개는 plant 10·monitor 16·기존 adapter 파일의 14개다.
전체 normal·ASan/UBSan **470개 PASS**, production build와 정상/고장 demo를 검사했다.
기존 Brake adapter 16개도 유지한다. Model vCAN 8개 회귀는 새 고장 network 시험과 구분한다.
실행 범위·로그·정적 분석은 [품질 기록](../quality_policy.md)에 둔다.

이 단계로 Steering/Brake response detector의 Host component 증거를 갖췄다.
[M2 수용 검토](../m2_acceptance_review.md)의 학습자 직접 재현·설명은 PENDING이다.
다음 구현은 M3의 실제 task/독립 감시와 trace 설계다. 차량 pressure→wheel torque·ABS·회생/마찰 배분은 후속이다.

직접 설명해 볼 내용은 정상 압력 차이와 고장 residual의 차이, fresh 동일 압력과 cached sensor의 차이,
보호 요청·floor 관측·차량 정지의 차이다. 답변/직접 실행 기록은 학습자가 남긴다.
