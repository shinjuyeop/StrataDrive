# M2: 브레이크 압력 모델과 공부할 부분

Date: 2026-10-14. Status: **Host functional SIL 부분 구현·검사 / 학습자 설명·직접 재현 PENDING**.
[ADR-0020](../adr/ADR-0020-first-brake-pressure-model.md)의 첫 마찰제동 모델이다.
M2 전체/차량 정지/실차 제동 calibration을 완료한 결과가 아니다.

## 1. 압력과 제동력은 다른 값

우리 Brake Command/Actual의 값은 nonnegative aggregate **마찰제동 압력**, 단위 Pa다.
압력이 피스톤을 통해 패드의 누르는 힘을 만들고, 마찰과 디스크 반경이 wheel 제동 토크로
연결된다. 같은 압력이라도 피스톤 면적·마찰계수·유효 반경 등이 다르면 토크가 다르다.
[MathWorks Disc Brake](https://www.mathworks.com/help/sdl/ref/discbrake.html)는 이 관계를 설명한다.
실제 전동 booster의 압력 생성 사례는 [Bosch iBooster](https://www.bosch-mobility.com/en/solutions/driving-safety/ibooster/)를 참고한다.

이번 모델은 **압력의 시간 응답**까지만 계산한다. 압력을 곧바로 차량 감속값으로 사용하지 않는다.
Pa→N·m calibration, tire/vehicle/road model은 TBD-02의 Plant 작업이다.
회생제동은 Drive signed torque, 회생·마찰 배분은 Central allocation 단일 owner의 별도 책임이다.

## 2. 모델 설정과 단위

| 항목 | 첫 fixture | 의미 |
| --- | --- | --- |
| Command 허용 범위 | 0..2 MPa | 밖이면 수신 거부; wire 최대값과 별개 |
| 물리 모델 한계 | 0..1.5 MPa | 허용된 큰 목표는 model target을 제한 |
| 초기 actual | 0 Pa | 새 process model 생성 때 값; session restart는 압력을 보존 |
| 정상 목표 지연 | 50 ms | control tick에서 새 목표 포착 후 가압/감압을 시작할 시각 |
| 가압 rate | 5 MPa/s | actual이 목표보다 낮을 때 상승 속도 상한 |
| 감압 rate | 10 MPa/s | actual이 목표보다 높을 때 하강 속도 상한 |
| 보호 floor | 1 MPa | 최초 fault의 actual과 이 값 중 큰 값을 보호 목표로 latch |
| Control 최소 간격 / 최대 gap | 10 / 30 ms | gap 초과 interval을 backfill하지 않음 |
| Source age / RX timeout | 30 / 80 ms | 원천 만료와 수신 상실은 다른 검사 |

`1 MPa = 1,000,000 Pa = 10 bar`. 전송 pressure 해상도는 기존 **1000 Pa**다.
Fixture는 C++에서 명시하며 [reference.yaml](../../profiles/reference.yaml)의 `m2_brake_fixture`에 기록한다.
YAML loader는 없고 OEM/실차 근거로 이 값을 확정하지 않는다.

## 3. 가압·감압을 계산하는 방법

```text
target = clamp(valid_command, 0, model_max_pressure)
rate = actual < delayed_target ? rise_rate : fall_rate
max_change = rate × elapsed_seconds
actual += clamp(delayed_target − actual, −max_change, +max_change)
```

10 ms 구간의 가압 상한은 `5 MPa/s × 0.010 s = 0.05 MPa = 50 kPa`다.
감압 상한은 `10 MPa/s × 0.010 s = 0.10 MPa = 100 kPa`다.
목표까지 남은 차이가 작으면 목표에서 멈춘다. 실제 값이 순간적으로 목표로 뛰지 않는다.

0→1 MPa는 목표 포착 뒤 **50 ms delay + 200 ms 가압 = 250 ms**다.
1→0 MPa는 **50 ms delay + 100 ms 감압 = 150 ms**다.
첫 목표를 10 ms tick에서 포착하면 due는 60 ms이고 70 ms actual이 처음 50 kPa로 올라간다.
Delay 경계가 tick 사이에 있으면 경계 이후 구간만 새 목표로 적분한다.
같은 목표를 반복 수신해도 delay를 재시작하지 않는다. 반복 수신은 source freshness를 유지한다.

이 식은 첫 rate/delay 모델이다. 실제 hydraulic compliance, valve/pump, 마찰/온도/ABS와
closed-loop 압력 센서 제어를 구현한 결과는 아니다.

## 4. 0과 unavailable을 구분해야 하는 이유

**유효 0 Pa Command는 해제**, unavailable은 사용할 pressure demand가 없다는 뜻이다.
Unavailable/손상/범위 밖 frame은 last-valid command를 갱신하지 않는다.
0을 unavailable처럼 버리면 정상 해제가 안 되고, unavailable을 0으로 바꾸면 통신 오류가 해제처럼 된다.
Actual도 모델 상태 sample이며 Command echo가 아니다. 유효한 FAIL_SAFE Actual은 보호 상태의
압력 관측이지 정상 운행 허가가 아니다.

## 5. 명령 상실 때 선택한 정책

Source expiry/RX timeout/continuity loss/control deadline을 감지하면 정상 delay FIFO를 취소한다.
최초 fault 시점에 `protection_target = max(actual, 1 MPa)`로 설정하고 latch한다.

- Actual이 0.4 MPa면 1 MPa까지 가압 rate로 접근한다. 그 순간 1 MPa로 jump하지 않는다.
- Actual이 이미 1.5 MPa면 유지한다. 더 낮은 floor라는 이유로 압력을 빼지 않는다.
- 보호 목표에는 정상 50 ms delay를 추가하지 않고, 감지 시각 이후 구간부터 계산한다.
- 늦은 fresh 0 Pa Command도 latch를 해제하지 않는다. 더 큰 trusted Epoch로만 재시작한다.
- Missed control interval에서는 이동을 생략하고 다음 정상 tick부터 보호를 진행한다.
- Clock 역행 후에는 신뢰할 source time이 없어서 publication과 physics를 중단한다.

정상 sample이 interval 끝에서 stale이면 해당 interval의 정상 이동을 생략하는 sampled 정책이다.
수신 함수도 새 frame을 검사하기 전에 이전 Command의 source expiry를 확인한다.
수용 명령이 없는 startup timeout은 causal context 없이 입력 번호를 꾸미지 않도록 unavailable
진단 Actual을 발행한다. 내부 모델의 보호 pressure는 계속 계산하며 getter로 확인할 수 있다.

이는 **첫 SIL 보호 정책**이며 차량의 안전한 floor/정지 성공을 뜻하지 않는다.
차량 감속·타이어·ABS·Zone arbitration과 결합하는 정책/calibration은 TBD-03/06에 남긴다.

## 6. 코드 읽는 순서와 실행

1. [설정/클래스](../../vecu/brake/brake_actuator.hpp): 단위가 붙은 설정과 외부 clock API를 읽는다.
2. [구현](../../vecu/brake/brake_actuator.cpp)의 `receive`: 기존 BrakeReceiver를 재사용한다.
3. `advance`/`move`: delay 경계에서 구간을 나누고 가압·감압 rate를 선택한다.
4. `fail`/`tick`: normal pending 취소, 보호 target latch, Actual/P05 생성과 새 source/sequence를 확인한다.
5. [시험](../../tests/unit/brake_actuator_test.cpp): 결정론적 clock으로 정상·상실·재시작을 비교한다.

Runtime model은 `vecu/brake/`, 수신 wire 계약은 `interfaces/brake/`에 둔다.
두 모델은 기존 [integration model loop](../../tests/integration/can/socketcan_rx.cpp)와
[runner](../../tests/integration/can/check_socketcan.py)를 공유한다. feature별 executable은 추가하지 않았다.

```sh
cmake -S . -B build/m1-angle
cmake --build build/m1-angle -j 4
ctest --test-dir build/m1-angle --output-on-failure
build/m1-angle/actuator_demo brake-model
unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py --family model --model brake
```

Demo는 가압 → 유효 0 해제 → source 상실 → 보호 가압을 가상 시각으로 실행한다.
vCAN은 독립 Command TX → model → Actual RX 세 process와 영속 Epoch/monotonic clock을 사용한다.
Model normal은 2 MPa demand의 1.5 MPa saturation, release, source loss 후 floor 도달을 검사한다.
Loss는 가압 중 상실과 late release 거부, high-loss는 이미 높은 압력의 유지와 late release 거부다.
Actual/P05, source/sequence/causal/state/origin과 pressure 값이 wire에서 보존되는지도 검사한다.
결과 로그는 각 build의 `socketcan-results/brake-model-*.log`다.

Brake 추가 당시 unit 16개를 더해 전체 172개, model vCAN 5개/all 94개였다.
후속 [Drive 응답](m2_drive_model.md)과 [Battery](m2_battery_model.md) 단계 시점은 unit 222개였으며 model vCAN 8개/all 97개 증거를 유지한다.
`--model steering`은 앞선 조향 2개만 선택한다. Actuator family 40/EV family 49는 유지한다.
Normal/sanitizer 실행 기록은 [품질 기록](../quality_policy.md)에 둔다. 기존 system TC는 NOT RUN이다.

## 내 말로 설명해 볼 질문

1. Command가 0인데 Actual이 아직 양수인 시간이 왜 정상일 수 있나?
2. 2 MPa demand와 1.5 MPa Actual의 차이는 이 fixture에서 무엇을 뜻하나?
3. 0 Pa와 unavailable을 같은 것으로 처리하면 각각 어떤 문제가 생기나?
4. FAIL_SAFE 압력이 유효하다는 사실만으로 차량이 멈췄다고 말할 수 있나?

답변과 직접 재현 기록은 학습자가 남긴다. [Drive의 양·음수 torque 응답](m2_drive_model.md)도 구현·시험했다.
[Battery 물리·관측](m2_battery_model.md), BMS/Power·Drive gate와 [이상적 HV의 DC/SOC 연결](m2_drive_energy.md)도 구현·시험했다.
[실제 RC/접점 에너지 연결](m2_ev_power_circuit.md)도 시험했다. 회생·마찰 배분, pressure→wheel torque와 차량 closed-loop는 후속이다.
