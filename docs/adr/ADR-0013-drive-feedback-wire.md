# ADR-0013: 구동·회생 Drive wire와 독립 피드백 유효성

Date: 2026-10-13. Status: **Host 구현·시험 실행 / 학습자 review PENDING**.
관련: [RG-01](ADR-0011-regenerative-braking-scope.md), [wire ICD](../icd/drive_frame_draft.md),
[실행 안내](../learning/m1_drive_codec.md). 기존 requirement revision을 변경하지 않는다.

## 문제와 결정

Drive의 signed motor torque와 회생 가용량은 의미만 정의되어 있었다. Torque sample을
새로 보내더라도 cached 속도·충전 입력으로 산출한 capability가 새 정보가 되는 것은 아니다.

- Command는 0x182 / 32 bytes, Actual은 0x282 / 64 bytes로 정의한다. Data ID는
  0x1201/0x1202, stream별 P05 state를 소유한다. Frame 수는 기존 six-frame을 유지한다.
- Torque는 aggregate driven-wheel 기준 signed int16 LE / 0.1 N·m이며 raw -32768은 invalid다.
  양수 구동/음수 전진 회생/유효 0을 구분한다. 이 wire 범위는 물리 calibration이 아니다.
- Actual은 torque의 metadata와 별개로 wheel-speed source time, capability calculation time,
  가장 오래된 dependency source time을 보존한다. Capability에는 별도 validity/limit/reason이 있다.
  유효한 0 한계와 정보 없음은 다르다. 전체 64 bytes를 하나의 P05 CRC로 보호한다.
- 기존 schema 2 prefix/CRC/Counter 위치를 유지하고 공통 payload codec에 명시적인
  64-byte 경로를 추가한다. Steering/Brake의 bytes/API/golden vectors를 유지한다.
- DriveReceiver는 공통 Epoch/Sequence/clock/valid-RX/timeout 상태를 재사용한다.
  Torque가 수용되더라도 speed/capability는 원천 시각과 caller의 범위로 별도 검사한다.
  사용할 수 없는 보조 값은 current sample에서 제거하고 torque의 유효성과 구분한다.
- 같은 원천 시각의 cached feedback은 값/이유/input time이 불변이어야 한다.
  새 산출 시각으로 오래된 입력을 유효하게 만들지 않는다. 최신 frame의 무효 정보를
  과거 capability로 대체하지 않는다. Fault latch는 새 Epoch의 trusted INIT으로만 초기화한다.
- Application fixture의 범위는 torque -300..500 N·m, speed 0..100 rad/s,
  regen magnitude 0..300 N·m다. Source/input age 30 ms와 RX timeout 80 ms는
  기존 Host budget의 초안이며 실차 성능·안전 calibration이 아니다.

## 범위와 검증

기존 actuator_demo/DBC checker/CAN TX·RX·runner에 Drive를 추가한다.
독립 모듈 시험은 한 파일 tests/unit/drive_test.cpp에 모아 value/frame/receiver를 검사한다.
명령·실행 결과와 제한은 [학습 안내](../learning/m1_drive_codec.md)에 기록한다.

M1 wire는 음수 demand를 표현·수용하지만 local capability에 따른 실제 torque 제한은
M2 모델이 담당한다. Charge acceptance/energy, vehicle state의 DDS 전달, Zone blending,
Plant 적용 및 차량 전체 피드백 loop는 미구현이다. 통신 수용은 제동 성공이나 회생 에너지
발생을 입증하지 않는다. M0 baseline을 소급 변경하거나 전체 TC-REG 결과를 PASS로 바꾸지 않는다.
