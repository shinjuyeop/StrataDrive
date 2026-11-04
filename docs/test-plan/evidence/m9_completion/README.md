# M9 후속: 실제 고장 주입·최초 원인·정지 복구

2026-11-04. Base `07a071d238cbb46dd3edb6bc951d607fd8ef97f3`.
**M9 전체 수용은 OPEN이다.** [결과](results.json), [최종 소스](source-final-manifest.json),
[실행 산출물](artifacts.json), [사전 CARLA protocol](../../carla-diagnostics-protocol.md)을 따른다.
이번 구현은 아래 범위를 해결했다. 미해결 조건을 실패 분모와 함께 남긴다.

## 구현과 검증

- 보호로 allocator 상태가 바뀌기 전에 실제 최초 fault/VehicleRequest를 복사한다.
  Async transport도 최초 enum·operation·token·sent·exclusive deadline·검출 시각을 보존한다.
  Allocator reason은 `0x10000 | enum`, transport는 `0x20000 | enum`이며 기존 NormalStop
  reason으로 바꾸지 않는다. 실제 Stop ACK timeout은 SD-1102, 다른 transport 원인은 SD-1002다.
- 정지 고장은 새 Epoch의 동일 설정 native Braking→handoff ACK→PowerDown→Complete로
  재검증한다. 7개 원인×4가지 조건에서 정상·설정 변경·session 누락·오래된 Complete를
  비교한다. 6개 원인은 정상 새 cycle에서만 Passed/명시적 clear가 가능하며 Clock은 계속 차단한다.
  별도 Speed SD-1002 시험은 실제 coordinator가 새 request를 수용하기 전에는 Passed를 막는다.
  이는 coordinator/component 경계다. 모든 실제 차량·remote 서비스의 code별 clear 완료를 뜻하지 않는다.
- BMS 센서의 8개 개별 trip bit와 복합 mask170을 실제 dwell/release/new-Epoch predicate로
  검사한다. Power는 실제 electrical model의 contactor response, precharge timeout, unsafe condition,
  request loss, shutdown current block, startup energized, bus-not-ready, discharge timeout 8종을
  검사한다. 각 새 실제 Ready와 손상된 proof 거절을 확인한다. 전체8-role 차량 matrix와 구분한다.
- 기본 store의512개 event를 durable commit한 뒤513번째를 거절한다. journal/commit bytes를
  변경하지 않고 incomplete/clear 차단을 재기동 뒤에도 유지한다. 측정한512개 쓰기는 약0.839s다.
  장기 보존 기간·rotation·운용 부하의 적합성을 주장하지 않는다.

## 실제 CARLA30

기존 STOP30 route/20s ramp/35s trigger/1m/s²/10s braking/60ms hold/2s HV-off 기준을 유지했다.
실제8-role owner에서 얻은 canonical event를 별도 process의 FileJournal/Recorder에 기록한다.
Native P05/원본 acquisition, 물리 응답, 독립 solver/work/단일 EV 정산을 각각 감사했다.

| 실행 | 실제 DTC | 물리 구간/EV 정산 | DTC event | 최종 실제 정지 |
| --- | --- | --- | --- | --- |
| nominal-01 | 없음 | 6000/6000 | 13 | 확인 |
| input-loss-01 | SD-1001, reason0x300 | 6000/6000 | 15 | 확인 |
| stop-ack-loss-01 | SD-1102, native timeout0x20007 | 6000/6000 | 19 | 확인 |
| front-link-failure-01 | SD-1002, native continuity0x20002 | 6000/6000 | 14 | 확인 |
| braking-timeout-02 | SD-1101, native BrakingTimeout8 | 6000/6000 | 16 | 확인 |

각 plateau 최대 오차는0.074842km/h다. DTC 감사는 nominal2개·고장별5개의 손상을 거절했다.
각 독립 work 감사는 원본 integrator/EV ledger 손상을 별도로 거절한다. 최종 native 바이너리에
원본 WORK/POSE/WHEEL을 재생해 **각6001개의 전체 native JSON이 동일함**도 확인했다.
재생은 새 물리 실행으로 세지 않는다. 원본/서버/probe/binary는 `carla/`, 원본 DTC 요약은
[carla-event-summary.json](carla-event-summary.json)에 있다.

첫 `braking-timeout-01`은 실패했다. 기존 독점 gate가 legacy `add_actor_force`를 차단했는데
client 호출만으로 적용을 가정했기 때문이다. 원본6,000개 구간과 서버 거절 로그를 보존한다.
후속은 명시적 서버 flag와 authenticated stage 안에서 고정1800N을 pre-physics에 적용하고,
**서버 receipt**가 적용 벡터를 기록한다. Legacy force RPC 차단·native torque/pressure·물리
wheel·10s 제한을 유지한다. 이것은 지속 외력이 정상 제동을 방해하는 환경 주입이다.
Brake 하드웨어 고장이나 타이어 모델 변경으로 표현하지 않는다. 원래 work 감사도 통과했다.

Silent Front command drop은 현재 whole10ms adapter의 command expiry가 native ACK timeout보다
먼저 다음 물리 구간을 막는다. 최초 실패 소스/로그와 최종 expected-refusal 회귀를 보존한다.
이 결과는 차량 정지가 아니다. 명시적 link failure 시험으로 silent loss를 대체하지 않는다.

## 실제 native 서비스와 실패 분모

중앙/전륜/후륜 CPU1/2/7, plant3, writer15의 별도 profile을 기록했다. SCHED_OTHER 기능 시험이며
Native4ms·Target 수용이 아니다. 실패 시 peer drain/보호 ACK 뒤 종료하고 fixture trace capacity를
196608로 고정했다. Command·Actual age·18ms support·handshake·제동/drain budget은 늘리지 않았다.

각 cohort는 Normal/ASan/TSan마다 정상 서비스, durable ACK 손실, 실제 Brake Actual 손실,
정지 요청 갱신 손실, 실제 Stop ACK 손실의5개 실행이다. 고장 실행의 **runtime FAIL은 유지**하며
별도 감사가 의도한 거절/무commit을 검증한다. 실제 service review/clear의 기존17개 mutation과
새 고장별4–6개 mutation을 구분한다.

| 원본 cohort | Normal | ASan | TSan | 의미 |
| --- | --- | --- | --- | --- |
| final-* | 5/5 | 4/5 | 3/5 | transport 최초 원인 보강 전 |
| transport-* | 5/5 | 5/5 | 1/5 | 원본 감사 결과, 실패 cleanup 보강 전 |
| verified-* 원본 감사 | 4/5 | 4/5 | 2/5 | 최종 실행15개 |
| verified-* 원본 근거 재심사 | 4/5 | 4/5 | 3/5 | 아래 ResultLate 원인 확인1개 추가 |

재심사한 TSan 정지 요청 손실은 native **ResultLate**가 RequestLost/timeout보다 먼저였다.
원본 token과 deadline이 최초 Braking 요청의 `min(expiry, source+50ms+1)`에 정확히 일치한다.
이를 확인하는 감사와 deadline/만료 전 시각 mutation2개를 추가했다. 원래 감사 FAIL은 보존했고
기한이나 기대 DTC를 바꾸지 않았다. 재심사는 새로운 runtime 실행이 아니다.

최종4개 미통과는 Normal Stop ACK·ASan Actual·TSan 정상 case의 Epoch2 재가입 선행 실패3개와,
TSan Stop ACK case에서 실제 ACK 유실 주입 전에 발생한 command rejection1개다.
후자는 원본 SD-1002/0x20006이며 SD-1102로 바꾸지 않았다. 전체15개에서 sanitizer report,
SDK error, 강제 cleanup은 없었다. 그러나 목표 시나리오의 성공으로 세지 않는다.
[원본15개](verified-native-results.json), [실패 분석](verified-failure-analysis.json),
[재심사 포함 결과](results.json)를 함께 읽는다.

이보다 앞선 `service-*`, `qualified-*`의 초기 고장/trace overflow/SDK 정리/선행 실패도 각각
archive와 명령 manifest에 보존했다. 재시도 통과만 골라 전체 분모를 만들지 않는다.
원래 이전 milestone TSan의 grant expiry 실패는 다음과 같이 재현했다.

- old support expiry730158390823384ns, fresh matching receive730158390857467ns: **34083ns 늦음**.
- allocator 검출730158390877029ns. 지원 정보가 만료된 뒤 새 grant로 옛 authority를 살릴 수 없다.
- 원본 PCAP에는 더 새 PowerStatus가 있었으나 VM이 그때 사용한 원본은 이전 sample이었다.
  CPU 경쟁을 유일한 원인으로 단정하지 않는다. deadline−1/동일/34083ns 이후 경계 회귀를 추가했다.

## 최종 품질 검사와 보존

- 일반/논리/transport1238 + 기존 wall9 =1247개 통과.
- ASan/UBSan 단위1025개, CARLA 관련135개 통과. 이후 silent-loss refusal를 확장한 해당 시험도 통과.
- Debug·ASan·CARLA 전체 target·SDK Normal/ASan/TSan·Release 빌드 통과.
- 변경7개 TU clang-tidy와 cppcheck 확인. 최초 clang14/GCC13 header 혼용은 실제 GCC11 header로
  다시 검사했다. cppcheck의 기존 AllocationConfig 값 복사 경고 한 곳은 명시적 baseline suppression;
  새 null-flow 경고와 string_view 전달, Report의 noexcept copy/indentation 문제는 수정했다.
- 모든 compile/test/audit 실패와 최종 로그는 `validation-logs.tar.gz`에 있다. 과거 bundle을
  변경하지 않고 별도 checksum으로 확인했다. `.jsonl.gz` 원본은 기존 convention처럼 Git LFS에 둔다.

## 남은 완료 조건

1. Native 서비스의 재가입/정지 선행 timing 안정성. 실제 실패를 제거하거나 수용할 실행 환경을
   측정해야 하며 timeout 연장·임의 Passed로 해결하지 않는다.
2. Silent packet loss에서도 물리 시간 안에서 native 검출/보호가 진행되는 CARLA subinterval adapter.
   기존 fixed10ms whole-interval admission을 느슨하게 만드는 것은 해결이 아니다.
3. Trusted Clock의 새 agreement/release/identity와 gap 없는 검사 구간을 증명하는 복구 predicate.
4. Trusted proposal 이전 EpochStore/journal bootstrap 실패를 가짜 application Epoch 없이 식별·보존하는 계약.
5. 확장한 BMS/Power8-role 차량 matrix·동시 고장 원인/복구와 실제 부하·장기 보존 운용 수용.
6. 학습자 이해 review. 아래 내용을 설명하기 전 개인 학습 완료를 기록하지 않는다.

DDS control gate CLOSED는 별도 middleware 대안이며 이번 SOME/IP 경로의 누락 구현으로 세지 않는다.

## 이해 review

- 입력 손실에서 검출, 보호 선택/ACK, 실제 torque/pressure/wheel, DTC journal은 각각 무엇을 증명하는가?
- Stop ACK 유실이 SD-1102인 반면 다른 command rejection은 SD-1002로 남는 이유는 무엇인가?
- 새 INIT, 같은 설정의 정상 cycle Passed, 명시적 clear의 차이는 무엇인가?
- 10ms physics 구간을 막은 것과 실제 차량 정지를 왜 구분하는가?
- Clock 오류나 저장 gap 뒤에는 왜 정상 frame 하나만으로 해제할 수 없는가?

정답의 핵심은 원본 시간·identity·검사 소유자·실제 물리 취득·영속 commit의 구분이다.
이 문서는 질문과 근거를 제공하며 학습자가 답했다고 대신 기록하지 않는다.
