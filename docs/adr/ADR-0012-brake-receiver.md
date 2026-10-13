# ADR-0012: Brake application 수신부와 공통 수신 상태

Date: 2026-10-13. Status: **Host 구현·시험 실행 / 학습자 review PENDING**.
관련: [Brake wire](../icd/brake_frame_draft.md), [Steering 수신 정책](ADR-0008-steering-receiver.md),
[회생제동 범위](ADR-0011-regenerative-braking-scope.md). 요구사항의 새 revision을 추가하지 않는다.

## 문제와 결정

Brake의 DBC/압력/P05/wire 송수신은 있었지만 유효 demand 수용과 timeout 처리가 없었다.
같은 clock/Epoch/Sequence 규칙을 복제하면 actuator별 수정이 어긋날 수 있다.

- [BrakeReceiver](../../interfaces/brake/brake_receiver.hpp)를 Command/Actual stream별로 둔다.
  Frame에서 Epoch를 자동 학습하지 않고 trusted `start_session`으로만 시작한다.
- [ActuatorReceiverState](../../interfaces/common/actuator_receiver_state.hpp)에 clock/session,
  source freshness, trace Sequence, last-valid RX와 fault latch를 공유한다.
  Steering의 API/정책/기존 시험을 유지한다. 값의 codec/P05 Data ID/압력 한계는 Brake가 맡는다.
- 순서는 clock/timeout → envelope/P05 → payload → metadata → validity/mode/pressure range다.
  모든 검사가 통과한 경우만 snapshot/application cursor/valid RX를 함께 갱신한다.
  P05 raw counter 재동기화는 application 수용으로 취급하지 않는다.
- Caller는 finite `0 <= min_pressure_pa < max_pressure_pa <= wire maximum`을 명시한다.
  fixture는 0–2,000,000 Pa다. 이는 차량 최대 압력/제동 성능 calibration이 아니다.
- 기본 source age는 <=30 ms, RX timeout은 >=80 ms이며 설정은
  `0 < source_age < timeout <=80 ms`다. 100 ms 검출 계약의 dispatch margin을 남기는 후보다.
- 첫 trace Sequence는 0..9, 이후 +1..+10이며 같은 Epoch의 uint32 wrap은 거부한다.
  Source time은 session 시작 이상/now 이하/이전 수용 source보다 엄격히 증가한다.
- Command는 NormalPath + NORMAL/DEGRADED만 수용한다. 보호 command의 실제 압력 정책은
  M2에 정의한다. Actual은 sender state를 보존하며 NoAcceptedInput은 INIT에서만 허용한다.
- Source age가 끝나면 timeout 전에도 `current_sample`이 없다. `last_accepted`는 진단 이력이다.
  Timeout/clock fault는 새 Epoch와 비감소 clock의 explicit INIT으로만 초기화한다.

## 배치와 검증

기존 `actuator_demo`에 `brake-receiver`를 추가하고 기존 CAN TX/RX/runner를 확장했다.
TX/RX의 bounded loop/stdio handshake/trace 경로도 두 actuator가 공유한다.
Brake wire 회귀 2개는 별도로 유지하고 application normal/fault/silent/flood 각 2개 stream을 추가했다.
새 독립 receiver 모듈의 시험은 `tests/unit/brake_receiver_test.cpp`에 둔다.

[실행 기록](../learning/m1_brake_codec.md#application-수신부-추가)에 명령과 결과 범위를 남긴다.
Pressure dynamics, timeout 이후 압력 hold/release/ramp, vECU task/watchdog/가용성 및
Host apply/tick gate 통합은 미구현이다. `Receiving`은 정상 주행 허가나 실제 제동 성공이 아니다.
회생 runtime과 Drive wire도 후속 작업이다.
이후 [ADR-0013](ADR-0013-drive-feedback-wire.md)에서 Drive wire/receiver를 구현·시험했다.
물리 응답·회생 배분은 계속 후속 범위다.
