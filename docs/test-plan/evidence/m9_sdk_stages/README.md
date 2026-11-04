# M9 커널·SDK 구간 관측

2026-11-04, base `b740c5e`. **응답 지연 미해결, 단일 I/O 후보 미채택, 기본2개 유지.**
[관측 protocol](../../sdk-stages-protocol.md), [후보 protocol](../../sdk-io-threads-protocol.md),
[ADR-0101](../../../archive/design-decisions.md#adr-0101).

## 실행과 판정

| 별도 cohort | 서비스 고장 검증 | 정밀 kernel 시계 검증 | 남은 실패 |
| --- | --- | --- | --- |
| 최초 고정6건, I/O2 | 6/6 | 5/6 | 시계 offset envelope100µs 초과1건 |
| A/B/B/A 고정8건 | 5/8 | 4/8 | A 갱신2건, B 연결 종료1건; 시계4건 |

두 cohort의 통과율을 합치지 않는다. 비교는2→1→1→2의4 block이며 각 block에
ACK-loss/Stop-ACK-loss1회씩이다. A2/4, B3/4다. 모든 runtime 뒤에만 감사했다.
이 고장 recipe는 의도한 거절에서도 runtime exit1을 반환한다. 엄격한 service fault
oracle가 실제 고장 주입·원본 DTC·정상 선행 조건과 정리를 구분하며 runtime을 PASS로 바꾸지 않는다.
Ordering/timing/accepted-response 감사14/14는 service 실패3건을 덮지 않는다.
Sanitizer 진단은14건 모두0이다. SDK 종료 오류는 A Stop-ACK-r1과 B Stop-ACK-r3에 남는다.

B에서 새 SDK 종료 오류가 없어야 한다는 사전 채택 조건이 충족되지 않아 기본 설정을
유지했다. 후보의 비계측30건 및 overflow/close-full4건은 실행하지 않았다.
기존 [28/30](../m9_timing_trace/README.md)을 이번 재실행으로 표시하지 않는다.
Native4ms/Target·CARLA·M9 전체 완료도 주장하지 않는다.

## 연결된 시각과 한계

별도 SDK clone은 pin `4187431d2815bd351845a09d01aa85b2a3163cab`이다.
원래 dependency/install·제어 바이너리를 바꾸지 않았다. SDK 내부262144개 슬롯은
시작 전에 초기화하고 모든 IO/dispatcher writer join 뒤 저장한다. 포화/시계 실패/flush
누락은 오류다. 의도한 Central1 SIGKILL의 미저장 trace는 별도 partial 수로 남긴다.

`tcp-send → kernel packet → tcp-receive → tcp-message → app-message → handler-queued
→ handler-enter/exit`를 SOME/IP service/method/client/session/길이/CRC로 연결한다.
양쪽 TCP stream의 같은 payload SHA를 비교하고 분할·순서 뒤바뀜·재전송을 재조립한다.
Adapter 로그의 CRC가 반복되면 대응이 유일한 API stage만 사용하며 모호한 key를 보고한다.
TCP/SDK identity가 구분하는 수신 chain은 계속 보존한다.

커널 SO_TIMESTAMPNS_NEW는 realtime이며 PCAP us와 별도로 원래 ns와 매 frame의
monotonic→realtime→monotonic bracket을 저장했다. 캡처3개는 CPU0/SCHED_OTHER,
기존 auxiliary8과 물리 코어를 공유한다. Socket drop은 모두0, 실제 library maps와
thread 개수/CPU/policy를 대조했다. SDK IO2와1 모두 추가 관측 부하를 받는다.
외부 부하·냉각을 통제한 성능 개선이나 지연 상한을 입증한 실험은 아니다.

Offset envelope100µs 초과5건은 기존 정밀 실패를 유지한다. 최종 reader는 이 실행도
SDK monotonic 구간을 JSON으로 보고하되 해당 receiver의 kernel 간격을 생략하고 exit1을
반환한다. 큰 시계 오차를 허용하도록 기준을 바꾸지 않았다. 샘플 사이의 관측되지 않은
realtime step을 완전히 배제할 수 없으므로 환산 구간을 정확한 kernel monotonic으로 부르지 않는다.
Outgoing AF_PACKET 시각은 물리 NIC 송신 시각이 아니다.

최초 ACK-loss-r1 정상 armed 구간의 Central→Rear request(session3613, CRC4089537658)는
send→handler **3.000398ms**였다. 수신 kernel→SDK callback 약**2.344–2.422ms**,
handler 실행17.862µs였다. TCP→app 사이의 다른 IO thread 이동도 관측됐다.
재접속 중200ms까지 buffered된 오래된 packet은 정상 armed 구간과 따로 집계한다.
Thread CPU와 voluntary/involuntary switch는 보조 근거이며 runnable/lock 대기의 완전한 분해가 아니다.

## 재현된 갱신 실패

원래 I/O2개 설정의 비교 Stop-ACK-r1/r4에서 실제 손실 주입 전 Front 갱신이 실패했다.
`renewal-correlation.json`은 원래 token/expiry·permission-limit/readiness 및 원본
PowerStatus bytes의 CRC32C/P05 CRC와 SDK 행을 연결한다.

| Case | Front token | 새 명령 send→수신 | 기존 만료보다 늦음 | release+18ms 대비 grant support 부족 |
| --- | --- | --- | --- | --- |
| A Stop-ACK-r1 | 455 | 0.485692ms | 21.471µs | 109.276µs |
| A Stop-ACK-r4 | 457 | 0.467825ms | 101.949µs | 668.676µs |

VM의 새 grant가 이전 AcknowledgedPower 만료에 묶여 readiness3으로 한 회차 대기했고,
다음 grant가 사용 가능해진 뒤 새 command가 이전 만료를 넘겼다. 따라서 네트워크 전달
시간 하나만으로 이번 실패 연쇄를 설명할 수 없다.

r1 PowerStatus136(source818961102733806, causal135)의 SDK rx-queued는818961105569946,
짧은 grant136의 source는818961105629713이다. 새 status가 grant 발행 시각보다 앞서
SDK queue에 있었지만 **VM 입력 snapshot을 자른 시각은 기록하지 않았다.** 이 기록만으로
snapshot 전에 도착했거나 정상 입력으로 채택됐다고 단정하지 않는다. 다음 경계는 실제
Power ACK 수신→owner ingress 소비→VM snapshot→권한 발급이다. 현재 주기/18ms support,
원래 source/expiry와 엄격한 SDK 오류 판정은 유지했다.

## 검증과 재현

Python 기존 bookkeeping30개와 신규8개가 통과했다. 신규 검사는 timestamp 누락/중복/
잘림, clock bracket, TCP 분할/순서/재전송/변조, thread가 다른 CPU clock의 분리와
실제 SDK thread 개수/정책을 다룬다. 최초 reader의 헤더 변조 미검출을 시험이 잡았고
수정 전 실패도 보존했다. 초기 SDK patch anchor의 중복 guard 실패는 native 실행 전에
발생했다. 해당 clone 로그는 보존했지만 오류 traceback은 파일로 저장하지 않았다.

실제 계측 SDK3TU의 clang-tidy는 GCC 전용 warning/link-only/-pie 인자를 분석용 DB에서
제거한 뒤 통과했다. 최초 호환성 실패 로그도 보존한다. Helper cppcheck는 통과했고,
전체 SDK3TU cppcheck는 원본 SDK에서도 나오는 기존 진단으로 exit1이다. 동일 설정의
base/계측 비교에서 신규 진단0이며 전체 SDK cppcheck 무경고로 표시하지 않는다.

초기 offline reader는 반복 adapter CRC와 TCP→app thread 이동을 단일 대응/동일 thread로
가정해 실패했다. 이를 각각 모호한 key 보고와 thread 내 CPU delta로 바로잡았다.
원본 runtime·처음 감사 결과를 보존하고, 최종 reader의 재감사 결과를 별도로 둔다.

재현 명령(기존 pinned SDK build/권한이 갖춰진 checkout에서 새 output 사용):

```sh
python3 tests/integration/someip/build_sdk_observation.py tsan build/new-sdk-observation
python3 tests/integration/someip/sdk_stages_campaign.py build/new-sdk-observation build/new-stage-cohort
python3 tests/integration/someip/sdk_stages_campaign.py build/new-sdk-observation build/new-stage-comparison --compare-io-threads
python3 tests/unit/sdk_stages_test.py
```

`summary.json`, `renewal-correlation.json`, `analysis-final-results.json`, `identity.json`,
`validation.json`은 요약/추적 근거다. Run별 tar는 PCAP·kernel sidecar·SDK·owner·journal·
설정·process maps를 포함한다. `metadata-and-tools.tar.gz`는 두 SDK patch/helper/manifest,
빌드 로그/분석 DB·처음과 최종 reader·native source snapshot·감사 실패를 보존한다.
`source-final.tar.gz`와 manifest는 최종 도구 소스이며 측정 당시 snapshot과 구분한다.
비교 당시 source hash 전체와 일치하는 snapshot은 metadata 안의
`compare-io/runtime-sources-complete.tar.gz`다. 그 이전의 불완전한 snapshot도 별도로 남겼다.
`archive-reaudit.json`과 `archive-reaudit.tar.gz`는 최종 소스와 대표4건을 재추출해
정상 고장 거절·실제 갱신 실패·시계 품질 실패 및 실제 thread 배치 판정을 재현한다.
`SHA256SUMS`는 전체 파일의 무결성을 확인한다.
