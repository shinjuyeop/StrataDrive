# 서비스 검증의 기능·동시성·실행 시간 분리

2026-11-05. 사용자 승인 [사전 protocol](../../service-validation-protocol.md)과
[ADR-0102](../../../archive/design-decisions.md#adr-0102-m9-서비스-수용에서-sanitizer와-wall-성능을-분리)의
**Host quiet 서비스 분리 판정을 통과했다.** 전체 M9/Target 수용은 아니다.

| 필수 검사 | 이번 결과 |
| --- | --- |
| 비계측 RelWithDebInfo 실제3-ECU 서비스6조건×3회 | **18/18** |
| 위18건의 서비스·ordering·placement·response 독립 감사/변조 검사 | **전부 통과** |
| ASan/UBSan component·논리 SIL·동시성21 targets | **309/309**, 경고0 |
| TSan 같은21 targets | **309/309**, 경고0 |
| 비계측 M4AsyncWall 정상·피드백 손실 | **2/2** |
| Python 분리 판정·SDK 원인·배치 회귀 | **49/49** |

정상과 signal writer250ms 지연은 각각3회 정상 종료했다. 나머지12건은 의도한
고장으로 runtime FAIL을 유지하며 독립 auditor가 원래 주입·검출·보호·DTC와
허위 서비스 성공/clear 거절을 확인했다. 이번18건의 SDK 오류는0이다.
[현재 분리 판정](acceptance.json), [고정 native 분모/명령/결과](results.json),
[빌드·실행 순서](preflight.json)를 따른다. 통과할 때까지 반복하지 않았다.

## 유지한 제품 계약과 달라진 시험 조건

C++/header/CMake1020개와 native normal binary는 선행 egress 후보와 같다.
20ms envelope·10ms 갱신/18ms support·원래 source/expiry·물리 보호 기준을
늘리지 않았다. 코드의 응답 지연이 새로 줄었다고 주장하지 않는다.
TSan의 계측 비용까지 같은 wall 정상 운행 보장으로 요구하던 조건을 분리했다.
두 `M4AsyncWall.*`만 sanitizer suite에서 제외하고 위 비계측2건으로 검증했다.
전체 CTest 목록은 그대로며, 논리 SIL의 실제 만료/보호 assertions는 계속 실행한다.
이21 targets는 SDK 전체의 sanitizer 수용을 대신하지 않는다.

ASan 첫 runner는 전체 executable 운영 watchdog180초, TSan 시작 전 정한
runner는600초다. 제품 deadline과 무관하며 timeout으로 실패한 재시도는 없다.
[사전 검토 기록](harness-timeout-review.json)과 두 runner 원문/hash를 보존한다.

`retired-central-feedback-v2`는 Central1 SIGKILL 뒤·Central2 boot 이전의
원래 Front/Rear feedback 연결 reset/broken pipe만 원문과 함께 분리한다.
실제 두 surviving PID·원래100ms 보호/물리 반응·새 Epoch8-role 재가입을 요구하며,
연결 오류가 보호보다 먼저 관측되는 순서도 허용한다. 새 세션 오류, 다른 SDK 오류,
큐 포화와 sanitizer 경고는 계속 실패다. 이후 서비스/DTC는 독립 auditor가 판정한다.

## 과거 실패 보존과 재분류

선행 [egress cohort](../m9_egress/README.md)의 원래 결과는 **27/30**이다.
원본을 수정하지 않은 [메모리 내 재감사](reclassification.json)는 **28/30**이며,
차이는 ASan stop-ack-loss의 이전 연결 reset1건뿐이다. 이는 새 runtime 실행이 아니다.
TSan actual-loss-r2/stop-request-loss-r3의 실제 만료·미완료는 그대로 실패다.
기존 M4 TSan wall 실패도 성공으로 재작성하지 않는다. 새 비계측18건의 분모와
합치지 않으며, 이번 판정이 계측 native의 지연 자체를 제거했다는 뜻도 아니다.

## 원본과 재현

`normal-r1/r2/r3.tar.gz`는 각6건의 원본 로그·PCAP·journal·physical trace·감사다.
`validation.tar.gz`에는 sanitizer XML/로그, 빌드 명령, 재감사/포장/검증 script가 있다.
`runtime-sources.tar.gz/json`은 실행 시2456개 source/hash다. [보관본 검증](archive-verification.json)은
원본 바이트 대조와 정상·고장 감사의 압축 해제 후 재현을 기록한다. `SHA256SUMS`를 따른다.

새 출력 경로로 native를 실행한다. 아래 명령은 sanitizer gate를 대신하지 않는다.

```sh
python3 tests/integration/someip/service_timing_campaign.py build/service-split-new --validation-profile split-v1 --split-owner-io --separate-aux-io --owner-fifo --response-audit --defer-audits
python3 tests/integration/diagnostics/service_sanitizer_suite.py build/service-asan-new --build build/m1-angle-sanitized --profile asan
python3 tests/integration/diagnostics/service_sanitizer_suite.py build/service-tsan-new --build build/m9-service-timing/tsan-unit --profile tsan
```

Sanitizer targets의 빌드는 보관한 `preflight.py`와 로그를 따른다. 서로 순차 실행하며
native 중 build/무거운 분석을 겹치지 않는다. Legacy mixed profile은 과거 재현용으로
남았다. 부하/장시간, Clock, CARLA silent loss subinterval, bootstrap와 전체 fault matrix 등
나머지 완료 조건은 [프로젝트 상태](../../../project-status.md)를 따른다.
