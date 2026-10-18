# ADR-0032: ECU 판단과 SIL 실행 연결의 분리

Date: 2026-10-16. Status: **IMPLEMENTED / Host component checks; 실제 task/watchdog는 후속**.
2026-10-18 follow-up: Drive torque의 같은 job 취득 제한·보조 시각 관계는 [ADR-0036](ADR-0036-asynchronous-drive-actual-feedback.md)으로 개정했다.
아래는 경계 분리 당시의 결정 기록이다.
ADR-0019/0020/0023/0027/0030/0031의 같은-thread composition을 세분화한다.
기존 wire·물리 수치·통신 상실 정책과 학습자 수용 상태를 변경하지 않는다.

## 문제와 결정

SteeringActuator·BrakeActuator·DriveActuator·DriveController가 physical response 객체를 직접 소유했다.
M3에서 이 `tick` 전체를 ECU execution으로 측정하면 물리 적분/센서 취득 비용까지 포함된다.
ECU 호출 중단과 plant 진행 중단을 따로 시험하기도 어려웠다.

1. 네 `vecu` 클래스에서 물리 객체·모델 header·고장 주입 인자를 제거한다.
   수신 검증·목표/한계·고장 판단·상태 보고만 소유하고 측정은 typed port로 받는다.
2. `interfaces/{steering,brake,drive}/*actuation.hpp`에 출력 mode·bounded target·issued time을 둔다.
   Drive의 envelope/response calibration도 plain interface data다. Calibration의 initial 값은
   기존 fixture 호환/검증을 위해 남기지만 실제 초기 상태는 SIL plant만 적용한다.
3. Trusted 시작 입력은 `ActuatorSession`으로 app/model epoch·enable time을 묶는다.
   Single-owner job을 `prepare(now)`와 `complete(sensor, now)`로 나눈다.
   Prepare는 clock/period/input을 검사하며, complete는 같은 job 시각의 snapshot을 받아 보고한다.
   미완료 prepare를 새 시각에서 건너뛰면 ControlDeadline, 잘못된/반복 complete는 발행하지 않는다.
   Caller는 두 phase 사이에 나중 시각의 RX/센서 갱신을 끼워 넣지 않고 입력을 직렬화해야 한다.
4. `simulation/steering/SteeringSil`, `simulation/brake/BrakeSil`,
   `simulation/drive/DriveActuatorSil`·`DriveSil`이 기존 예제의 연결을 맡는다.
   물리 진행·센서 생성·고장 주입·출력 적용은 이 SIL 코드에서 수행한다.
   실제 runtime은 ECU/plant를 각각 소유해 독립적으로 진행할 수 있다.
5. 기존 endpoint 상실·gap 정책을 회귀 유지한다. SIL helper는 fault를 확인한 시각 전에 보호 motion을
   소급하지 않고, 관측하지 못한 control gap interval은 catch-up하지 않는다.
   별도 실행자가 이미 진행시킨 물리 상태를 ECU 복귀 때 과거 값으로 되돌리지 않는다.
6. Actual은 센서에서만 채운다. Steering/Brake의 지연된 새 측정은 acquisition source time을 보존한다.
   Drive는 현재 wire의 torque timestamp가 별도로 없고 다른 channel의 생성 시각도 함께 다루므로
   **그 job의 end 시각에 새로 취득한 torque만** 유효 scalar로 발행한다. Cached/지연 측정은 torque unavailable,
   30 ms 초과 age·wrong epoch/time/identity/range·missing은 TorqueFeedbackUnavailable로 latch한다.
   Speed/capability의 기존 독립 validity/원천 metadata는 유지한다. 새 fault enum은 기존 값 뒤에 추가한다.
7. CMake의 ECU library는 simulation library에 의존하지 않는다. SIL library가 ECU와 plant를 조합한다.
   기존 예제/통합 fixture/모델 회귀시험은 명시적인 SIL class를 사용한다.
8. `actuator_demo`는 실행 파일 하나를 유지한다. 명령/도움말은 `tools/actuator_demo.cpp`,
   도메인 구현은 `tools/demo/{steering,brake,drive,ev}_demo.cpp`로 나눈다.

## 검증과 남은 범위

Core만 link하는 `ecu_boundary_test` 18개는 simulation include path/plant library 없이 동작한다.
기존 세 actuator 시험 파일에는 ECU 호출 중단 중에도 외부 plant가 계속 진행하고,
복귀 때 이미 발생한 물리 응답을 되돌리지 않는 3개 case를 추가한다.
기존 470개를 포함해 전체 491개 unit, CLI 90개 출력/exit code 비교, 기존 model vCAN 8개를 회귀 검사한다.
실제 실행 결과는 [품질 기록](../quality_policy.md), API/읽는 순서는 [학습 안내](../learning/m2_execution_boundaries.md)에 둔다.

Prepare/complete는 동기 SIL 경계이며 OS scheduling, mutex/queue나 독립 watchdog의 구현이 아니다.
M3에는 각 ECU phase와 physics 비용을 구분할 trace, release/clock ownership, job deadline,
정지 감시 독립성과 bounded handoff를 별도로 구현·측정해야 한다.
완성된 runner 전체 시간을 ECU execution이라고 보고하지 않는다.
M1/M2 학습자 수용은 PENDING, 32개 요구/29개 system TC 전체 Result는 NOT RUN이다.
