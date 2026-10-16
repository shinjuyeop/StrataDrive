# M2: 통신이 정상인데 조향이 움직이지 않는다면

Date: 2026-10-16. Status: **Host functional SIL 구현·검사 / 학습자 직접 재현·수용 PENDING**.
[ADR-0030](../adr/ADR-0030-steering-local-response-monitor.md)의 local response monitor다.
기존 [조향 응답](m2_steering_model.md)에 sensor/fault 경계를 추가했다.

## Timeout과 응답 고장은 어떻게 다를까?

통신 timeout은 새 유효 메시지를 받지 못한 상황이다. 반면 조향이 물리적으로 jam되면
매번 새 측정이 이루어지고 메시지 번호가 증가해도 각도는 그대로일 수 있다.
**같은 값이라는 사실만으로 stale이라고 할 수 없다.** 목표에 도달한 정상 hold도 같은 값을 계속 측정한다.

이번 monitor는 issued target 이력과 독립 측정으로 정상 응답 범위를 계산한다.
관측값과 정상 동작의 차이를 residual로 쓰는 개념은
[MathWorks의 모델 기반 지표 설명](https://www.mathworks.com/help/predmaint/ug/model-based-condition-indicators.html)을 참고했다.
아래 rate band와 수치는 이 프로젝트의 시험 설계다.

| 책임 | 코드 / 사용하는 정보 |
| --- | --- |
| 물리 응답 | [SteeringResponse](../../simulation/steering/steering_response.cpp): bounded target→delay/rate→실제 angle; jam/rate variation 주입 |
| 센서 취득 | [AngleMeasurement](../../interfaces/steering/steering_angle_sensor.hpp): model epoch, acquisition sequence/time, measured angle; hold/invalid/override는 sensor port에만 반영 |
| 고장 판단 | [SteeringResponseMonitor](../../vecu/steering/steering_response_monitor.cpp): target 이력과 sensor port만 사용; jam flag나 plant getter를 읽지 않음 |
| 통신·보호 판단 | [SteeringActuator](../../vecu/steering/steering_actuator.cpp): 기존 receiver, local fault/latch, hold 요청과 sensor 기반 Actual/P05 |
| SIL 실행 | [SteeringSil](../../simulation/steering/steering_sil.cpp): 출력 적용, 물리 진행·센서 취득과 ECU phase 연결 |

후속 [실행 경계 정리](m2_execution_boundaries.md)에서 SteeringActuator를 ECU 판단만 남긴 core로 바꿨다.
[SteeringSil](../../simulation/steering/steering_sil.cpp)이 같은 thread의 물리/센서·ECU 연결을 맡는다.
파일 경계를 나눈 것이 실제 RTE/OS task 분리나 AUTOSAR stack 구현을 뜻하지 않는다.
SteeringSil의 physical diagnostic getter는 시험·로그용이며 ECU에는 없다. Sensor가 없을 때 Actual을 채우는 데 쓰지 않는다.

## 목표각과 현재각을 바로 비교하지 않는 이유

0.2 rad를 요청해도 정상 모델은 50 ms 기다린 뒤 최대 1 rad/s로 움직인다.
목표가 0.4 rad여도 물리 한계가 0.3 rad면 0.3 rad에서 멈추는 것이 정상이다.
새 명령의 dead time이 끝나기 전에는 이전 목표로 계속 움직일 수도 있다.

따라서 monitor에는 **물리 한계로 제한한 목표와 적용 시각 이력**을 넣는다.
정상 속도 허용 범위는 nominal 1 rad/s의 0.8..1.2배다.
첫 유효 센서로 초기 위치를 잡고, 이후 예측 범위는 목표 이력으로만 진행한다.
매번 센서 위치로 예측을 리셋하면 jam 위치도 정상 기준으로 따라가므로 그렇게 하지 않는다.

각 지연 목표가 적용되는 구간에서 다음 범위를 전파한다.

```text
move(x, rate, dt) = x + clamp(target - x, -rate × dt, rate × dt)
next_lower = min(move(lower, min_rate, dt), move(lower, max_rate, dt))
next_upper = max(move(upper, min_rate, dt), move(upper, max_rate, dt))
residual = max(lower - measured, measured - upper, 0)
```

이 범위는 fixed delay와 bounded-rate라는 현재 모델 가정 안에서 정상 움직임을 허용한다.
Residual에 **0.01 rad** 여유를 두고, 그 밖의 관측이 새 sensor acquisition에서 **60 ms** 이어지면
TrackingError를 확정한다. 0.01 rad는 약0.57°이고 wire step 0.0001 rad보다 크다.
이는 실차 센서 오차/조향 사양을 측정해 정한 threshold가 아니다.

Pending 동안 Actual state는 DEGRADED다. 정상 관측으로 돌아오면 pending을 지우고,
확정 뒤에는 FAIL_SAFE/LocalProtection을 유지한다. 뒤늦은 명령이나 jam 해제만으로 자동 복귀하지 않는다.
새 trusted application epoch로 INIT를 시작해도 실제 angle과 physical sensor sequence는 보존한다.
유효 angle도 DEGRADED/FAIL_SAFE 상태와 함께 해석해야 한다. 상위 주행 허가를 뜻하지 않으며 실제 Zone/Central 연동은 후속이다.

## 센서가 멈췄다면

Fresh acquisition은 sequence와 source time이 함께 증가해야 한다. 같은 acquisition을 재조회하면
시간·값·identity를 바꾸지 않고, 그 재조회 횟수로 60 ms dwell을 채우지 않는다.
Source age 20 ms 초과 또는 fresh acquisition 사이 gap 30 ms 초과는 SensorUnavailable이다.
NaN, 범위 밖 angle, wrong model epoch, future/pre-session time, cached identity의 값 변경은 SensorInvalid다.

CAN의 기존 angle Actual에는 별도 sensor acquisition timestamp 필드가 없다.
이번 adapter는 **새 유효 acquisition만 angle로 발행**하고 sensor hold 동안은 unavailable report를 낸다.
따라서 report sequence가 증가해도 downstream receiver의 last-valid angle RX는 갱신되지 않는다.
센서가 무효일 때 내부 물리 angle을 대신 넣지 않는다.

한 센서가 매번 신선한 identity를 붙여 잘못된 동일 값을 낸다면 기계 jam과 비슷한 residual이 생길 수 있다.
**TrackingError는 응답 이상 검출이며 원인이 기계 jam이라는 확정 진단이 아니다.**
또한 현재 목표와 실제 각도가 같아 움직임을 요구하지 않는 구간에서는 jam이 드러나지 않을 수 있다.
빠른 방향 전환 등으로 정상 예측 범위가 고정각을 포함하는 경우에도 검출을 보장하지 않는다.

## 실행과 로그 읽기

```sh
cmake --build build/m1-angle -j 4
ctest --test-dir build/m1-angle --output-on-failure
build/m1-angle/actuator_demo steering-model jam
build/m1-angle/actuator_demo steering-model slow
build/m1-angle/actuator_demo steering-model sensor-hold
build/m1-angle/actuator_demo steering-model sensor-invalid
build/m1-angle/actuator_demo steering-model transient
```

기존 명령 하나에 scenario를 추가했다. 인자 없는 `steering-model`은 기존 normal/command-loss 예제다.
모든 demo는 manual simulation clock이다. Jam/rate variation은 **begin 100 ms 이후의 물리 구간**에 적용하고,
sensor fault는 그 구간 끝 취득에 적용한다. 새로운 제어 출력이나 고장 주입을 이전 구간으로 소급하지 않는다.

| Scenario | 관측된 결과 / 의미 |
| --- | --- |
| normal | 정상 delay/rate 이후 0.2 rad 도달; 300 ms 뒤 command 중단으로 기존 command-loss 보호 |
| jam | 100 ms부터 물리 angle 약0.04 rad 고정, fresh command/acquisition 유지; 130 ms residual pending, 190 ms TrackingError |
| slow | 100 ms부터 physical rate 0.25배; 140 ms pending, 200 ms TrackingError |
| sensor-hold | 마지막 acquisition 100 ms; 110 ms부터 angle report unavailable, 130 ms SensorUnavailable |
| sensor-invalid | 110 ms NaN acquisition에서 즉시 SensorInvalid, angle unavailable |
| transient | 160 ms 한 번의 sensor outlier는 DEGRADED; 170 ms 정상 범위 복귀 후 pending 해제, latch 없음 |

`expected_min_rad/max_rad`는 정상 응답 범위, `angle_rad`는 발행한 측정값이다.
`physical_rad`는 시험용 truth라 sensor가 없을 때도 보일 수 있다.
`sensor_source_ms`와 `violation_ms`, `fault`를 함께 읽는다. Tracking fault 확정 뒤 range/residual은 검출 당시 증거로 유지한다.
190 ms 검출 중 60 ms는 residual 확인 구간이다. 100 ms stream-loss 계약을 jam 검출 deadline으로 사용한 결과가 아니다.

## 검사한 것과 남은 것

새 시험 39개: 물리 9개, monitor 21개, 기존 adapter 파일의 case 9개다.
전체 normal·ASan/UBSan unit 430개와 production build를 검사했다.
Rate band 양끝·delay·reversal·saturation·transient·양방향 stall, cached/time/identity/unknown,
bounded history·latch/new epoch와 fresh Actual을 확인한다.
기존 model vCAN 8개는 통신/정상·상실 보호의 회귀다. Jam/sensor fault를 넣은 새 vCAN case는 추가하지 않았다.
[품질 기록](../quality_policy.md)에 실제 실행 범위와 로그를 남긴다.

검출기는 bounded-rate predictor이며 motor torque/current controller가 아니다.
실제 noise/관성/마찰/가변 delay·redundant sensor·jam 원인 분리·차량 조향 가용성/안전 정지는 미검증이다.
후속 [Brake stuck/slow-response detector](m2_brake_fault_monitor.md)도 구현·시험했다.
[M2 수용 검토](../m2_acceptance_review.md)의 직접 재현·설명은 PENDING이며 [M3 실행·계측](m3_multirate_runtime.md)은 진행 중이다.
실제 task/watchdog와 timing/trace 측정은 M3에 남긴다. 학습자의 직접 재현·설명은 PENDING이다.

내 말로 확인할 부분은 세 가지다. 목표각과 측정각이 다르더라도 정상일 수 있는 이유,
같은 angle의 새 acquisition과 cached read의 차이, TrackingError와 jam 원인 진단의 차이를 설명해 본다.
