# M9 입력 snapshot 순서와 full-queue 종료

2026-11-04, base `81be788`. 이 후보의 고정 서비스는 **29/30**
(Normal6/6·ASan6/6·TSan17/18), 기능 회귀는 **12/12**다.
[사전 protocol](../../feedback-order-protocol.md), [ADR-0099](../../../archive/design-decisions.md#adr-0099).
이전27/30·11/12 원본을 변경하지 않는다. 전체 timing/M9 수용은 OPEN이다.

Central은 bounded ingress와 원래 result deadline을 처리한 뒤 validated snapshot을
만든다. 수정 전 새 Actual이 큐에 있어도 이전 값을 복사하던 순서를 단위 시험으로
재현했다. Source/expiry·18ms support·10ms/+4ms VM과 allocation10ms는 유지한다.
이전 실패의 Actual은 관리 주기 뒤 도착했으므로 이 수정만으로 전체 원인이 해결됐다고
주장하지 않는다. 원래 source 검색/CRC stage 대조는 `historical-input-chain.json`에 있다.

Full-queue 종료는 기존20ms cleanup 구간 동안 owner admission을 닫은 채 추가8개를
거부한다. Normal/ASan 모두 첫8+추가8의 original token/source/deadline과 Central16건
negative 결과가 대조됐고 expiry/late0, SDK 오류0, sender 생존·Epoch2 재시작을 확인했다.
SDK 오류 예외를 추가하지 않았다. 실제 drain end와 SDK stop/join 시각은 원본에 남긴다.

## 남은 실패

`tsan-actual-loss`는 의도한 Actual 손실 주입 전에 Epoch2 정상 정지 중 실패했다.
따라서 의도한 fault 성공으로 세지 않는다. 순서·배치·accepted-response 감사 통과도
서비스 실패를 덮지 않는다. `analysis.json`, `renewal-chain.json`과 raw archive를 따른다.

- Permission141 발행803882775947373ns → allocation ready803882780983449ns:5.036076ms.
- Front token495 송신803882781014397ns → 수신803882781648652ns:0.634255ms.
- 직전 token489 expiry803882781644860ns보다 **3,792ns 늦었다**. 원래 보호/negative 결과를 유지했다.
- Rear 결과의 기존 send 구간2.591727ms/thread CPU39,949ns 뒤 grant sender queue2.850925ms를
  관측했다. 기존 trace mutex 대기·SDK 내부·scheduler를 이 수치만으로 구분할 수 없다.
  이어지는 별도 timing-trace 후보에서 기록 잠금과 SDK 호출 계측 경계를 분리한다.

Host23216표본, 최대100°C, thermal counter+900. 실패 전후25ms는5표본/최대87°C,
thermal 증가0이며 CPU4/5의 약800MHz 표본은 있지만 모든 CPU1–7의 동시 저하는 없다.
외부 부하/냉각을 통제하지 않았고 시스템 governor/EPP/thermal 설정을 바꾸지 않았다.
29/30과 이전27/30의 차이를 통계적 성능 입증으로 해석하지 않는다.

## 검증·보관

관련 C++152개씩 Normal/ASan·UBSan/TSan, Python30개, 변경2TU cppcheck/clang-tidy 통과.
152는 Async23+control124+CoordinatorIntegration5의 고유 시험 수다. Integration target명
오입력1회와 올바른 target 재빌드 로그도 보존했다. 새2개 단위의 수정 전 실패를 포함한다.
전체 root suite/CARLA/Native4ms/Target 재실행으로 세지 않는다.

`results.json`은 서비스30+기능12개의 모든 실행과 명령·manifest·감사 exit를 보존한다.
기능12개 뒤 서비스 runtime30개를 실행하고 독립 감사는 마지막에 수행했다. 재시도/제외는 없다.
Service archive는 profile/repeat별로 나눴다. `service-metadata.tar.gz`에는 공통 manifest와
당시 source snapshot이 있다. `source-final`은 **이 후보 측정 당시** 소스이며 후속 변경과 구분한다.
`identity-checks.json`은 보관 당시 source/binary 일치 검사다. 재추출 감사는 정상 통과와
지연 실패 및 두 close-full 통과를 그대로 재현한다. `SHA256SUMS`로 무결성을 확인한다.
