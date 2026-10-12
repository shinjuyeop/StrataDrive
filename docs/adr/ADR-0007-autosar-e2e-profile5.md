# ADR-0007 — Steering 통신 보호에 AUTOSAR E2E Profile 5 적용

## Status

2026-10-12 사용자 요청으로 채택한 **Host Profile 5 Protect/Check 구현·검증 / 학습자 review PENDING**.
[ADR-0006](ADR-0006-steering-frame-codec.md)의 자체 CRC wire 설계를 대체한다.
M0 의미 계약, 요구사항 ID, Reference v0.1 및 milestone은 유지한다.
M1 acceptance와 차량 application receiver/vCAN 송수신은 미완료다.

## Standard and implementation scope

기준 판은 **AUTOSAR R25-11**이다.

- [FO E2E Protocol Specification](https://www.autosar.org/fileadmin/standards/R25-11/FO/AUTOSAR_FO_PRS_E2EProtocol.pdf), §6.8 및 공통 Protect/Check 도표.
- [CP SW-C E2E Library Specification](https://www.autosar.org/fileadmin/standards/R25-11/CP/AUTOSAR_CP_SWS_E2ELibrary.pdf), §8.2.5/8.3.5의 설정·상태·초기화·Protect/Check 계약.

[직접 작성한 C++17 구현](../../interfaces/common/e2e_profile5.cpp)은 Profile 5의 CRC,
Protect/ProtectInit, Check/CheckInit 동작을 제공한다. C++ reference/optional/return enum을
사용하는 프로젝트 API이며 AUTOSAR C ABI나 vendor BSW를 가져온 구현이 아니다.
Check 함수의 호출 결과와 profile status를 분리한다. `p05_is_ok`는 호출 성공과
OK/OKSOMELOST를 함께 확인하는 프로젝트 helper다.
Forward, GetHeaderInfo, MapStatusToSM 및 profile-independent E2E State Machine은 구현하지 않았다.
OS/RTE/COM/BSW 통합이나 전체 AUTOSAR 적합성·안전 인증 완료를 뜻하지 않는다.

## Decision

고정 길이 32-byte Steering Command/Actual에 P05를 적용한다.
P05의 byte 단위 배치와 3-byte header는 기존 byte-aligned codec과 연결하기 쉽다.
Profile 4의 더 큰 header와 CRC32도 대안이지만, 이번 학습 범위에서는 P05를 선택했다.
필요한 오류 검출 성능/잔여 오류율과 safety allocation은 이후 분석 범위이며
이번 선택만으로 ASIL이나 Hamming Distance의 프로젝트 보장치를 확정하지 않는다.

| 설정 | Command | Actual |
| --- | --- | --- |
| CAN ID | 0x180 | 0x280 |
| Data ID | 0x1001 | 0x1002 |
| DataLength (bits) | 256 | 256 |
| Offset (bits) | 232 | 232 |
| MaxDeltaCounter | 10 | 10 |

Data ID 두 값은 이 프로젝트에서 서로 다르게 할당한 값이며 CAN 표준 번호가 아니다.
후속 Brake/Drive/DDS 설정에서도 중복되지 않도록 관리한다. CAN ID는 transport identity이고
Data ID는 보호 대상 identity다. DBC에는 프로젝트 정의 attribute로 설정을 기록하며
이 attribute를 AUTOSAR ARXML이나 자동 COM 설정으로 간주하지 않는다.
MaxDeltaCounter=10은 기존 10 ms stream의 실험 후보이며 측정으로 확정한 값이 아니다.

CRC는 poly=0x1021, init=0xFFFF, refin/refout=false, xorout=0이며,
전체 payload에서 CRC 두 byte만 제외한 뒤 Data ID를 low/high 순서로 붙여 계산한다.
기존 CAN ID/length prefix는 제거한다. Envelope의 종류·ID·길이·flags는 별도 검사한다.
CRC는 byte 29–30에 little-endian으로, Counter는 byte 31에 기록한다.
Angle/metadata byte 0–25를 유지하고 Reserved를 byte 26–28의 3 bytes로 줄인다.
SchemaVersion을 **1 → 2**로 변경하며 이전 wire payload는 지원하지 않는다.

## State and application responsibilities

송신 stream별 Protect state는 첫 Counter=0이며 성공한 보호 호출마다 증가한다.
255 다음은 0이다. Counter는 message나 trace Sequence에서 복사하지 않는다.
수신 Check 초기 상태는 Counter=255, Status=ERROR다.
CRC 정상 frame의 modulo-256 delta가 0이면 REPEATED, 1이면 OK,
2…MaxDeltaCounter면 OKSOMELOST, 그 밖이면 WRONGSEQUENCE다.
WRONGSEQUENCE에서도 규격대로 수신 E2E counter를 갱신한다.
CRC 오류와 NONEWDATA는 E2E counter를 갱신하지 않는다.
API 입력 오류는 state를 변경하지 않으므로 return 값도 반드시 확인한다.

E2E state와 application의 last-accepted Sequence/source time/snapshot/last-valid RX는 별도다.
WRONGSEQUENCE 뒤 다음 frame의 E2E OK만으로 FAIL_SAFE를 해제하지 않는다.
32-bit trace Sequence와 Epoch는 기존 application replay/인과관계 정책을 유지한다.
Trace Sequence wrap은 새 Epoch + explicit INIT를 요구하고, E2E Counter wrap은 정상이다.
Freshness, 물리 한계, mode/Origin, timeout, explicit INIT 및 last-valid RX 갱신은 후속 receiver에서
검사한다. Profile-independent E2E State Machine 채택·설정도 별도 receiver 설계 항목이다.
현재 CLI와 unit test는 이 전체 command 수용/gate를 구현한 것이 아니다.

## Evidence and consequences

새 C++/Python runtime dependency는 추가하지 않았다. 기존 cantools와 Python binascii로
DBC/independent CRC를 확인한다. 공식 §6.8.5의 두 예제 CRC **0xCA1C/0x9128**와
프로젝트 golden vectors를 별도로 검사한다.
기존 자체 CRC vectors는 schema 2 P05 vectors로 교체하고 malformed/invalid/uint64 시험을 유지했다.

2026-10-12 normal/ASan·UBSan **25개 PASS**, DBC parser/golden/demo 교차 검증 PASS,
clang-tidy 및 cppcheck의 변경 production source 검사에서 소스 진단 없음.
명령과 한계는 [실행 기록](../learning/m1_autosar_e2e_profile5.md)에 있다.
기존 차량 TC를 VERIFIED로 바꾸지 않으며 학습자 직접 재현/review는 PENDING이다.
