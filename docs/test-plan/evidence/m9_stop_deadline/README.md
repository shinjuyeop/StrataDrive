# 정지 요청 만료의 주기 사이 검출과 원본 DTC

2026-11-05, base `da19483`, [사전 protocol](../../stop-deadline-poll-protocol.md).
NormalStop의 원래 RequestLost를 관리 주기 사이에서도 관측하도록 수정했다.
기능12/12, 서비스 최초25/30이며 엄격한 원본 재감사 후 **27/30**이다.
최초 결과·로그는 [results.json](results.json)에 그대로 보존한다.

## 수정과 확인

앞선 release-slot 후보의 정지 요청 손실은 source+50ms+1에서 generic 보호가
먼저 닫혀 Central RequestLost DTC를 남기지 못했다. Coordinator 관측마다
NormalStop의 원래 시간 한계를 poll하고 Stop 원인을 먼저 보존한다. 이 poll은
관리 job을 실행하거나 last_tick·원래 source/expiry를 갱신하지 않는다.
기존 구현의 경계 회귀 실패와 수정 후 통과, 실제 SD-1105 원본 시각과 중복 억제를 확인했다.

이번 native stop-request-loss5건 모두 원래 요청을 가진 SD-1105가 기록됐다.
[원본 대조](stop-root-analysis.json)를 따른다. TSan r2/r3에는 바로 앞선 실제
transport 고장 SD-1002도 함께 기록됐지만 감사기가 root 한 개만 허용해 거절했다.
서로 다른 두 원인의 native reason·시각·token·공통 expiry·related sequence를
각각 검증하도록 감사기를 보완했다. 각13개 변조를 거절하며 필요한 root 누락과
중복도 실패다. 이 변경은 사후 감사이고 native 재실행이 아니다.

[80건 최종 reader 재검증](reader-revalidation-final.json)은 input-phase/release-slot/SMT/poll의
각20개 fault 실행을 대조했다. 예상한 input-phase3개·poll2개 외에 판정을 바꾸지
않았다. 당시 reader는 원래 source archive, 보완 reader와 모든 재감사 로그는
`post-runtime-analysis.tar.gz`에 별도 보존한다. 두 root의 공통 만료 조건을
명시한 최종 reader와 같은80건 재감사는 `reader-final-revalidation.tar.gz`에 있다.

## 남은 세 실패

| 실행 | 엄격한 실패 근거 |
| --- | --- |
| tsan-ack-loss | SDK local SEND_ID queue limit8192 overflow. 서비스 거절 자체는 정상이어도 SDK 오류로 실패 |
| tsan-actual-loss-r2 | 서비스 fault 검사는 통과했지만 TCP capture의 중간8264/10922byte 누락으로 응답 감사 실패 |
| tsan-actual-loss-r3 | 주입 전 정상 정지 중 grant146의 늦은 수신을 source<current release로 거절해 이전 권한이 만료됨 |

[TCP gap 분석](pcap-gap.json)은 sequence wrap이 아닌 원본 누락을 확인한다.
빠진 bytes를 재구성하거나 성공으로 면제하지 않는다. [grant 원본](remaining-grant-failure.json)은
별도 [due/current 분리 후보](../m9_deferred_grant/README.md)의 출발 근거다.

## 검증 범위

전체 Debug1271/1271·ASan/UBSan1271/1271, 관련 TSan110/110,
Python30+8+4, 변경 구현 cppcheck/clang-tidy가 통과했다. CARLA adapter6개 binary의
논리162개도 통과했으며 실제 CARLA 서버 재실행은 아니다. 원본4548개 command의
배분 회차 감사는0개 불일치였다. [회차 감사](release-audit.json)는 release row에서
grid phase를 추론하므로 독립 Clock agreement 증명으로 쓰지 않는다.

Source·binary hash와 당시 build/test 설정, 기능 및5개 서비스 round archive를
분리 보존한다. [동일성 검사](identity-checks.json)는 포장 당시 후보 기준이다.
SDK 오류·불완전 capture·실제 권한 만료를 포함한 전체 서비스 수용과 M9 전체는 OPEN이다.
