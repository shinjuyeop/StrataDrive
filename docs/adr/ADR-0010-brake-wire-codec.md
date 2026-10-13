# ADR-0010: Brake wire codec과 공통 actuator payload

Date: 2026-10-13. Status: **PROPOSED / Host 구현·시험 실행, 학습자 review PENDING**.

## 문제

Steering의 angle/frame/P05/receiver/vCAN을 구현했다. 다음 M1 작업은 Brake Command/Actual이다.
M0 의미 계약은 nonnegative aggregate pressure, Pa다. 모듈 추가마다 metadata·E2E·예제·통합
시험을 복사하면 배치가 흩어지고 같은 계약의 수정이 서로 어긋날 수 있다.

## 결정

- Pressure는 unsigned 16-bit LE, 1,000 Pa/raw, 0–65,534 유효, 65,535 invalid로 표현한다.
  0 Pa는 유효한 release demand이며 invalid와 구분한다. 범위 검사 후 반올림하고 clamp하지 않는다.
- CAN ID 후보 `0x181`/`0x281`에 P05 Data ID `0x1101`/`0x1102`를 할당한다.
  기존 Steering stream과 중복되지 않으며 profile/config와 Counter state를 stream별로 유지한다.
- Schema 2의 공통 metadata/CRC 배치를 `interfaces/common/actuator_payload_codec.*`로 추출한다.
  Steering의 기존 golden bytes와 수신 동작을 유지한다. 압력/각도 codec과 domain의 CAN ID,
  invalid code, 수신 정책은 `interfaces/brake/` 및 `interfaces/steering/`에 둔다.
- 기존 demo를 `actuator_demo`로 확장한다. 기존 DBC 검사기는 `check_actuator_dbc.py` 하나에서
  두 domain을 검사한다. SocketCAN adapter와 integration participant/runner도 공유한다.
  통합 시험은 `tests/integration/can/`, 새 Brake 모듈의 단위 시험은 `brake_codec_test.cpp`에 둔다.

## 대안과 영향

Signed 16-bit는 음수 pressure가 없는 계약에 표현 공간 절반을 쓴다.
Unsigned 32-bit는 더 넓은 범위/더 작은 해상도를 제공하지만 현재 2-byte field와 metadata 위치를
바꿔야 한다. 초안은 기존 배치를 유지하며 16-bit를 선택했다. 100 Pa/raw 등의 더 작은 factor는
같은 bit 수에서 wire 최대값을 줄인다. 실제 calibration 검토에서 표현력이나 해상도가 부족하면
ICD/DBC/schema/codec/vector를 함께 개정한다. 현재 factor와 wire 최대값은 차량 parameter 근거가 아니다.

추출한 common codec은 고정 schema의 직렬화와 CRC 검사를 담당한다. Freshness, timeout,
mode, 물리 범위, pressure dynamics를 여기에 넣지 않는다. Brake의 Actual은 독립 시험 sample이며
command echo나 물리 모델 결과로 주장하지 않는다. 새로운 범용 framework/외부 의존성은 추가하지 않았다.

## 증거와 다음 작업

[Wire ICD](../icd/brake_frame_draft.md)와 [실행 기록](../learning/m1_brake_codec.md)에 설정과
normal/sanitizer unit·DBC·vCAN 검사 범위를 기록한다. 기존 Steering 48개 case를 유지하고
Brake/shared payload/adapter case를 더했다. 다음은 Brake application receiver이고,
이후 Drive wire 확장이다. 영속 coordinator, overflow 주입, six-frame acceptance와 차량 TC는 남아 있다.
