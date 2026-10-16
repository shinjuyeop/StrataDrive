# ADR-0020: 첫 마찰제동 압력 응답 모델

현재 배치: [ADR-0021](ADR-0021-central-coordination-and-parallel-zones.md). 후속 차량 전체 회생 배분/session/feedback owner는 2026-10-14 ADR-0021의 Central component다. 아래 Front 배분 언급은 당시 배치이며 Brake 모델/보호 fixture는 유지한다.

Date: 2026-10-14. Status: **Host functional SIL 부분 구현 / 학습자 review PENDING**.
Owner: project owner. IF-CAN-BRAKE, BRAKE_COMMAND_LOSS, TBD-02/03/04/06에 연결한다.

후속 구조 변경: [ADR-0032](ADR-0032-ecu-and-sil-execution-boundaries.md)에서 ECU의 plant 소유/호출을
외부 SIL 연결 코드로 옮겼다. 아래는 이 ADR 채택 당시의 설계·시험 이력이다.

## 결정

`vecu/brake/BrakeActuator`가 기존 Brake Command receiver를 소유하고 외부 monotonic clock으로
정상 압력 응답과 local 보호를 계산한다. Codec/receiver는 `interfaces/brake/`에 유지한다.
Control/publication 최소 간격 10 ms, single-owner 호출, bounded delay FIFO와 독립 Actual/P05
방식은 [Steering 첫 모델](ADR-0019-first-steering-response-model.md)을 따른다.
모델은 물리 압력 상태를 유지하며 Command를 Actual로 복사하지 않는다.

Fixture는 Command 0..2 MPa, model 0..1.5 MPa, 초기 0 Pa, 가압 5 MPa/s, 감압 10 MPa/s,
정상 목표 변경의 지연 50 ms, control gap 상한 30 ms를 사용한다.
Source age 30 ms/RX timeout 80 ms는 기존 receiver 설정이다. 이 수치는 OEM calibration이 아니다.
유효한 0 Pa는 해제 목표다. Unavailable/CRC 오류/범위 밖 command를 해제로 바꾸지 않는다.
같은 목표를 반복 수신하면 freshness만 갱신하며 물리 지연을 다시 시작하지 않는다.
정상 가압과 정상 해제에 같은 delay를 적용하는 첫 단순 모델이다.

## local fault 정책

Command source expiry, receiver timeout, 수신 continuity loss 또는 control deadline 위반을
감지하면 normal pending target을 폐기하고 FAIL_SAFE/LocalProtection을 latch한다.
최초 fault 시각의 `max(current_pressure, fault_pressure_floor)`를 보호 목표로 고정한다.
Fixture의 floor는 1 MPa다. 이미 높은 압력을 이 floor로 낮추지 않는다.
보호 목표는 정상 지연 FIFO를 우회하지만 실제 압력은 가압 rate를 지키며 접근한다.
Fault를 관측한 시각부터만 보호 이동을 적분하며 즉시 압력 jump나 과거 interval backfill은 없다.
이후 tick의 반복 fault 관측/늦은 release command가 목표나 시작 시각을 재설정하지 못한다.

Deadline을 놓친 interval에서는 압력 이동을 생략한다. 이후 clock/호출 간격이 정상이라면
local protection을 계속 계산한다. Clock 역행 시에는 physics/publication을 중단한다.
복구는 더 큰 trusted Epoch와 비감소 clock을 요구하며 기존 physical pressure를 보존한다.
보호 pressure가 유효 Actual이어도 정상 주행 가능을 의미하지 않는다.
수용 Command가 없는 startup timeout은 causal context가 없으므로 진단 unavailable Actual을
발행한다. 내부 modeled pressure/protection은 계속 유지하며 0 Pa로 의미를 바꾸지 않는다.
이 제한은 현재 wire의 causal 표현에 따른 첫 모델 정책이다.

이 retain-or-increase 정책/floor는 검증할 SIL 선택이다. 차량 정지/타이어 lock 방지나 안전한
제동 압력의 보장은 아니며 차량 상태·ABS·arbitration·위험 분석과 결합한 값은 TBD-03/06이다.

## 학습과 증거

[Brake 모델 학습·실행 안내](../learning/m2_brake_model.md)에 압력/토크의 차이, 단위,
가압/감압 계산, 0/unavailable, metadata와 실행 결과를 둔다.
기존 integration participant의 model loop와 runner를 Steering/Brake가 공유한다.
별도 feature executable은 만들지 않고 `actuator_demo brake-model`을 추가한다.

Pressure→wheel friction torque calibration과 차량 감속은 Plant 단계다.
Drive 회생 응답/Front 배분, hydraulic sensor/valve/pump/ABS, stuck/leak response detector,
독립 watchdog/Target timing, 차량 보호/closed-loop 및 full system TC는 후속이다.
공식 참고: [MathWorks Disc Brake](https://www.mathworks.com/help/sdl/ref/discbrake.html)는
pressure와 마찰·피스톤·디스크 geometry의 torque 관계를 설명하고,
[Bosch iBooster](https://www.bosch-mobility.com/en/solutions/driving-safety/ibooster/)는
전동 booster의 master-cylinder 압력 생성 및 자동 압력 제어 사례다. Fixture 수치의 출처는 아니다.
