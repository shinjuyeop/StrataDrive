# Steering actuator response study

Status: **학습 자료 / 상세 이해 확인 PENDING**. 정상 응답을 설명하기 위한 계산 예제다.
M2의 actuator model 선정·구현, parameter calibration, fault 검출 기준과 차량 시험은
**PLANNED / NOT RUN**이다. 예제 수치를 profile/ICD의 TBD 값으로 채택하지 않는다.

[Interactive graph 열기](steering_response.html): HTML 파일을 로컬 browser로 열면 된다.
외부 library나 서버 설치 없이 동작한다. 이 자료의 계산은 학습용이며 Host에서 실행하는
AI inference나 Jetson Target의 성능 측정이 아니다.

## Starting point

2026-09-28 대화에서 사용자가 설명한 내용:

> 조향 명령이 마찰같은 물리적인 요인으로 늦게 추종된 걸 수도 있으니까 정상 작동의 범주에 있는데 jam으로 판단하면 오히려 위험한거지?

이 발언은 정상 응답 지연과 오검출의 위험을 연결한 이해 기록이다. 아래 parameter와
모델의 타당성 검토, 구현·실행 능력을 확인한 결과는 아니다. 마찰이 원인이더라도 허용된
정상 응답 범위를 넘으면 이상일 수 있다. 고장 원인과 정상 허용 범위를 함께 살펴본다.

## Signal meaning

프로젝트의 Steering Command / Steering Actual은 **equivalent front road-wheel angle**이며
단위는 **rad**, 좌회전은 양수다. Steering wheel 자체의 회전각과 구분한다.
[ICD](../icd/interface_overview.md#semantic-payload-contract)가 의미의 기준이다.

학습 그래프에서는 각도를 읽기 쉽게 deg로 표시하고 내부 계산은 rad를 사용한다.
`rad = deg × π / 180`이다. 이 표시 방식으로 CAN/ICD 단위를 변경하지 않는다.
그래프의 Step 입력은 현상을 살펴보는 수학적 입력이며 유효 CAN command를 뜻하지 않는다.

## Three response characteristics

| 개념 | 관찰할 현상 | 단위 / 구분 |
| --- | --- | --- |
| Dead time | 입력이 바뀐 뒤 실제 움직임이 시작되기까지 기다리는 시간 | s 또는 ms; 조향 변화가 시작된 뒤의 속도와 구분 |
| Rate limit | 조향각이 한 번에 뛰지 않고 제한된 속도로 변하는 현상 | rad/s; task period나 최대 조향각과 구분 |
| Angle saturation | 조향각이 허용된 상·하한 밖으로 나가지 못하는 현상 | rad; 시간이 충분해도 물리 한계 밖의 목표에는 도달할 수 없음 |

기본 개념은 MathWorks의 [Transport Delay](https://www.mathworks.com/help/simulink/slref/transportdelay.html),
[Rate Limiter](https://www.mathworks.com/help/simulink/slref/ratelimiter.html),
[Saturation](https://www.mathworks.com/help/simulink/slref/saturation.html) 설명을 참고한다.
Simulink 사용을 결정하거나 설치한 것은 아니다.

이 세 요소만으로 마찰·관성의 전체 물리 동작을 재현할 수는 없다. 여기서는 효과를
구분하는 간단한 표현을 사용한다. 마찰, 부하 의존성, 1차 지연, 가속도 제한, overshoot,
noise 등의 필요성과 결합 순서는 M2에서 근거를 검토한다(TBD-02/03).

Dead time은 CAN 통신 손실 timeout과 다르다. 같은 유효 command를 계속 수신해도
actuator는 정해진 응답 특성에 따라 움직일 수 있다. 기존 100 ms stream loss 검출 상한을
조향 완료 시간이나 jam 검출 deadline으로 사용하지 않는다.

## Teaching model

아래는 현상을 분리해서 보기 위한 **선택된 교육용 모델**이다. 실제 actuator의
상·하한, 변화율과 응답 시간을 보장하는 모델이 아니며 M2 구현으로 채택하지 않았다.

- 초기 actual angle은 0이고, 시각 0에 일정 Step 입력 `u`를 준다.
- 각도 한계는 대칭인 `−delta_max`와 `+delta_max`로 단순화한다.
- 제한 후 목표 `u_limited = clamp(u, −delta_max, +delta_max)`를 계산한다.
- `delay_s` 동안 actual angle은 0이다. 이후 `max_rate`로 움직이다 목표에 도달하면 유지한다.
- 통신, task scheduling, 센서, 마찰, 차량 거동과 fault는 이 그래프에 모델링하지 않는다.

`max_rate > 0`, `t >= 0`에서 그래프의 정의는 다음과 같다.

```text
delta_model(t) = sign(u_limited)
                 × min(abs(u_limited), max_rate × max(0, t − delay_s))
```

Rate limit은 본래 변화율의 **상한**이다. 그래프에서는 비교를 쉽게 하려고 대기 후 그
상한으로 계속 움직이는 경우를 선택했다. 실제 actuator가 항상 이 속도로 움직인다는
뜻이 아니다. 초기값 0에서 0이 아닌 제한 후 목표에 도달하는 예제 시간은 다음과 같다.

```text
t_example = delay_s + abs(u_limited) / max_rate
```

목표가 0이면 처음부터 도달한 상태다. 실제 시스템에서는 이 계산을 안전 deadline이나
정상 허용 시간으로 바로 사용할 수 없다. 정상 model·부하·측정 오차와 위험 분석이 필요하다.

## Worked example

아래 수치는 **설명용 가정**이다. 실제 차량 사양이나 StrataDrive parameter가 아니다.

| 항목 | 예제 값 |
| --- | --- |
| 초기 actual / Step 입력 | 0° / +10° |
| Dead time | 50 ms |
| Rate limit | 20°/s |
| Angle limit | ±15° |

0–50 ms에는 아직 움직이지 않는다. 이후 +10°까지 움직이는 데 `10 / 20 = 0.5 s`가
걸리므로 이 예제 곡선은 입력 변경 후 **550 ms**에 목표에 도달한다.
그때까지 Command와 Actual의 차이가 존재하는 것만으로 jam이라고 판정할 수 없다.

프로젝트의 10 ms logical control period를 계산 간격으로 가정하면 한 간격에 가능한
최대 변화는 `20°/s × 0.010 s = 0.2°`다. 주기 10 ms가 조향 완료 시간 10 ms를 뜻하지 않는다.
그래프 자체는 위 연속시간 식을 그리며 discrete scheduler나 실시간 실행을 검증하지 않는다.

Step 입력을 +25°로 바꾸고 한계를 ±15°로 유지하면 제한 후 목표는 +15°다.
예제 모델은 800 ms에 +15°에 도달하며 원래 입력과는 10° 차이가 남는다.
이것은 그래프의 saturation 동작이다. **실제 수신한 범위 밖 command를 조용히 clamp하고
수용하라는 구현 정책이 아니다.** 기존 수신 validation 계약은 유지하고, 유효 범위와
allocation/물리 한계의 일관성은 TBD-01/02/03/06에서 검토한다.

## Try and explain

Interactive graph에서 한 번에 한 값만 바꾸고 곡선의 변화를 먼저 예상한다.

1. Dead time을 늘리면 움직임의 시작 시각과 움직인 뒤의 기울기가 각각 어떻게 바뀌는가?
2. Rate limit을 절반으로 낮추면 움직이는 구간의 시간은 어떻게 바뀌는가?
3. Step 입력을 Angle limit보다 크게 주면 시간이 지나도 남는 오차를 무엇으로 설명할 수 있는가?
4. 부호를 음수로 바꾸면 우회전 방향에서도 같은 모델의 제한이 유지되는가?

답변과 이해 기록은 학습자가 직접 남긴다. 그래프를 표시하거나 계산 예제를 확인했다는
이유로 학습자 검토나 runtime TC를 PASS로 표시하지 않는다.

## Connection to fault detection

다음 검토에서는 정상 응답이 가질 수 있는 오차·지연 범위를 먼저 정리한다. Command와
Actual의 추종 오차, 정상 모델의 예측과 Actual의 차이, feedback의 validity/freshness를
구분해서 관측할 계획이다. 정상 상태에서 계속 fault가 발생하는지와 실제 fault를 놓치거나
늦게 검출하는지를 함께 검토한다. Threshold/dwell은 아직 TBD-03/04다.

모델과 관측의 차이가 크다고 원인을 바로 jam으로 확정하지 않는다.
[조향 fault 비교](../safety/concept_study.md#first-exercise-steering-fault-comparison)와
[fault architecture](../architecture/fault_diagnostics_architecture.md)의
STEERING_TRACKING_FAULT를 함께 읽는다. 이 학습은 M1 준비 중 개념 공부이며 M2 runtime의 착수·완료 기록이 아니다.
