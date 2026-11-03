# 실제3-ECU terminal 연속성 서비스

2026-11-03. 실제 SOME/IP3.7.6 Central/Front/Rear와 SimpleVehicle의 local service를 연결했다.
Central 재기동 Epoch2 정상 운전/정지 뒤 별도 operator 요청으로 Epoch3를 열고, 실제8-role Release·
accepted credit 뒤 정상 운전/정지·보호에 진입한다. Source9개의 queue/pending/실제 ACK를 먼저
드레인하고 collector를 닫은 뒤 service가 original journal lifetime flock을 인수한다.

정상 dispatch를 닫은 control/SDK/plant는 실제 현재 Actual을 계속 제공한다. 물리 취득이 전
writer freeze보다 뒤임을 서비스의 독립 monotonic now·PCAP의 CAN Actual·physical acquisition
원본으로 대조한다. 고정 kernel peer/boot 인가 뒤 별도 registry4/store8900에서
proof→Review→Passed와 별도 Clear 요청만 commit한다. 정확한 SD-5001 한 건을 해제하며
원형 unknown history/count/generation·다른 DTC·기존 Event-only merged는 보존한다.

| 실행 분모 | 결과 |
| --- | --- |
| 마지막 service cohort `complete-*` | Normal1/1·ASan1/1·SDK TSan0/1 |
| 직전 service cohort `accepted-*` | Normal1/1·ASan1/1·SDK TSan1/1; 마지막 bool scope 정리 전 |
| 앞선 `verified-*` | Normal1/1·ASan1/1·SDK TSan1/1; std algorithm/scope 정리 전 |
| 기존 native regression | Normal12/12·ASan12/12·SDK TSan3/3; service 전용 경로의 style 정리 전 |
| 일반 unit/logical/transport / wall | 1223/1223 / 9/9; core 구현 변경 없음 |
| 로컬 심사/서비스 ASan component | 17/17 |
| Python runner oracle / fingerprint | 24/24 / 2/2 |
| 정적 분석 | 변경 adapter3 TU clang-tidy PASS; cppcheck3 TU 신규 진단0. 기존 style 진단은 baseline과 별도로 보존 |
| Release / BUILD_TESTING=OFF | 기존 명시적 SDK opt-in을 유지한 최종 build PASS |

마지막 TSan은 Epoch2 정상 정지 중 CoordinatorFault::Allocation(5)을 선택해 서비스 시작 전에
실패했다. Release255였고 owner 최대 poll gap1.686ms·RX/TX overflow0·sanitizer/SDK error 없음이다.
원인은 아직 확정하지 않았다. 서비스 journal entry0·endpoint 없음·DTC 전부 uncleared를 확인했다.
이는 미계획 실패 관측이며 서비스 고장 주입 TC의 통과나 최종 TSan service 수용으로 세지 않는다.
재실행으로 실패를 가리거나 budget을 늘리지 않았다. 앞선 두 TSan feature 실행의 통과와 구분한다.

마지막 Normal/ASan과 앞선 통과 자료는 각3 global Session·24 original Release ACK·27 accepted
credit·11 stream 모든 Data/ACK·9개 source cut·5개 fresh physical sample·9개 local admission 요청·
정확히4 local transaction을 독립 감사한다. 통과 자료별17개 변조를 거절한다. 최종 해제까지
실제 이동/정지했으나 저속 nominal fixture이며 native4ms/Target/실차 성능 수용은 아니다.

초기 실패도 보존했다.

- `attempt-normal`: 서비스 자체는 완료했으나 남은 Unix socket inode를 artifact copy하려다
  실패했다. 소유한 socket만 close 후 unlink하도록 고쳤다. 기본 plant probe이며 최종 이동 fixture와 구분한다.
- `final-*`: Normal/TSan runtime은 성공했으나 초기 독립 감사의 feedback method/길이 선택과
  10ms trace를 acquisition 원본으로 가정한 검사로 실패했다. 실제 method0x70·원형 CAN/CRC를
  읽고 서비스 구간 acquisition을 별도 기록했다. 과거 trace 보간/허용 오차 확대는 하지 않았다.
- 같은 초기 ASan은 EpochStore 동기 fsync 약295ms 동안 owner가 멈춰 remote TX overflow와
  Epoch3 INIT 실패로 끝났다. 실제 보호 ACK 후 비실시간 Epoch IO·계속 수신·old graph의 지연
  폐기로 수정했다. FIFO·40ms handshake·18ms permission·정지/drain budget은 유지했다.
- Physical source field의 초기 compile 실패와 기존/신규 cppcheck style 진단을 보존했다.
  새 algorithm/변수 scope 제안만 수정했고 기존 style 진단은 baseline과 비교했다.

마지막 두 수정은 서비스 전용 함수의 std algorithm 사용/지역 bool scope다. 해당 경로를 다시
빌드·실행했고 이전 regression/검증에 사용한 source·binary hash를 별도 archive/plan에 남겼다.
원래16개 M9 bundle의2866파일 무결성을 확인했다. 당시 source/binary/config/tool·분모·실패와
원본 persistent store와 artifact copy 비교는 [manifest.json](manifest.json), [results.json](results.json)에 있다.

```sh
python3 -B docs/test-plan/evidence/m9_native_service/verify-packaged.py
```

이 SDK-free 검사는 해시·마지막 Normal/ASan 감사·변조와 마지막 TSan 실패의 서비스 미진입/무해제를
재현한다. Archive의 이전 통과와 실패도 원형 보존하며 최신 수용으로 올리지 않는다.
실행 recipe는 [protocol](../../diagnostics-protocol.md#native3-ecu-terminal-연속성-서비스-fixture),
설계는 [ADR-0094](../../../archive/design-decisions.md#adr-0094)를 따른다.

Terminal maintenance 뒤에는 capture/normal 운행을 재개하지 않고 ECU/SDK를 종료한다.
다음은 마지막 TSan Allocation 선행 실패 원인과 서비스 중 ACK/Actual 누락·정지 실패/시간초과의
실제 clear 거절 검증이다. 일반 service/RPC·다른 host/clock/반복 세대·TBD-08·native4ms/Target·
M9/학습자 수용은 OPEN이다.
