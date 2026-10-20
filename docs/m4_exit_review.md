# M4 기술 종료 검토 — Host component와 원격 경계

Date: 2026-10-20. Status: **IN PROGRESS / NOT CLOSED**. 현재 상태 기준은 [project_status](project_status.md)다.
학습자 직접 재현/설명은 **REVIEW PENDING**, system32요구/29TC·Target/전체 원격 배포는 **NOT RUN**이다.
이 검토는 위 상태를 PASS로 바꾸지 않는다.

| 종료 항목 | 구현/실제 시험 | 근거/판정 | 차단 여부 |
| --- | --- | --- | --- |
| 정상 request/arm/TX result/status/Actual/protection 소유권 | AsyncCoordinatorPort·AsyncZoneOwner·AsyncLeafOwner; M4AsyncRuntime·AsyncOwnerTest | 실제 BMS/HV/센서 준비·arm 뒤 정상 배분; 함수→시험→두 빌드 결과86개 연결 | Host component PASS |
| owner stop/방향별 loss/delay/부분 송신/보호·재가입 | M4FaultRuntime/Wall·M4OwnerStop/M4Direction; Network::replace_joined_links | 원래 source/deadline, stopped ACK 부재, 별도 physical watchdog, failed link join/교체, 새 durable Epoch/full readiness/arm, 모델/SOC/energy 연속 | Host component PASS; 원격 격리 증거 아님 |
| 실행/메시지/복구 구조 정리 | ADR-0057, boundary compile, CTest disjoint labels | 원본948개 이름/assertion 보존 +18개; `1989477` normal/ASan·UBSan 각각966/966, 논리 물리 CSV37개가 `5eb1b3b`와 byte 동일 | PASS; 실행 시간 동일성 증거 아님 |
| 원격 Leaf composite authority/INIT/arm/stop/protection | ICD owner-wire v1; RemoteLeafTest·RemoteZoneIntegration·RemoteOldRequestTest | 이전 Epoch 응답 identity, 최초 sent 기반20ms envelope, issuer/Epoch/token ACK8개씩 불변 보관. 실제 Zone 생산→codec→다섯 Leaf의 arm/명령/Actual/Power/Stop·만료 거부; 신규 계약15개 PASS | Host 계약/component PASS; 전체 원격 process 배포 미실행 |
| 원천 feedback/parent/epoch/sequence/expiry | owner_wire explicit catalogue; NoInnerCanCounterSourceOrCrcIsRegenerated·BMS unknown/zero·real Leaf Actual | CAN/DBC/P05 불변; byte/uint64/binary64 보존; 지연 도착이 원래 expiry로 거부 | PASS component; 전체 DDS Actual 왕복은 M5 |
| clock/source-age/skew/rejoin | RunLeaseGate·mapped_time; RemoteClock/PeerFixture | common kernel monotonic profile 고정; 불확실성 산술 경계 검사; 다른 clock runtime 거부 | Host 계약 PASS; Target sync 후속, Host M5 자체 차단 아님 |
| TBD-05/15 API/QoS/queue/프로세스 | optional DDS/Zenoh6조건×3회, netns/veth/실제 tc/실제 thread·load | v1 30 PASS/6 FAIL 보존, 관측 보완 v2 별도36/36 PASS. QoS만으로 로컬 SPSC/atomic 의미를 재현할 수 없음; 첫 adapter는 bounded lane/실패 latch·full handshake 필요 | 후보 실험과 실제 배포 구분; 세부 결과 공유 근거 참조 |
| 새 workload M3 감시/타이밍 수용 | 기존48회 프로토콜을 `1989477`에 새 실행 | **41 PASS/7 FAIL**, control48/48. OTHER loaded6 FAIL + FIFO monitor-overrun1 FAIL(주입 전662ms slot 누락). FIFO23/24. 원본41/7·603fe24/77d411c 각각42/6 보존 | **BLOCK: OPEN-M4-TIM-01**; 새 FIFO 실패 원인 미확정, 시한/분모 유지 |
| 변경 동시성 sanitizer | `1989477` TSan 경계67+wall9; `f895dc6` full trace native20+TSan20 | 최신67/67·9/9 및 별도40/40 PASS, 경합 경고0. `d7115ff`8/9의 CommandDelivery 실패 미재현; 두 논리 지연 경계로 expiry/pending 보호 경로 구분 | **BLOCK: OPEN-M4-TSAN-01**; 역사적 failure path 미확정, 전체966 TSan NOT RUN |
| Middleware 동시성 검증 | 기존 wrapper TSan4 FAIL·SDK 재계측 DDS2 FAIL의 version source/stack 분석 | DDS GC progress의 vendor volatile atomic helper가 `no_sanitize("thread")`; 계측 공백 확인이나 실제 lifetime 안전성은 미확정. Zenoh binary/Rust handoff도 미확정. 새 SDK 실행 NOT RUN | **BLOCK: OPEN-M4-MWTSAN-01**; suppress/false positive 종결 없음 |
| 기존 M3 예외 | OPEN-M3-01/02·ADR-0042/43 | 원본 OTHER sanitizer2 FAIL과 kernel trace 권한 제약 유지 | 전체 M3 수용 PENDING; 새 성공으로 닫지 않음 |

최신 commit/환경/명령·수정 전후·원본·CSV/그래프는 [계약 검토 evidence](test-plan/evidence/m4_contract_review/README.md),
원본948개와 이전 실패는 [이전 evidence](test-plan/evidence/m4_followup/README.md)에 묶는다.
기능 PASS, 정상 timing FAIL, TSan race warning 부재, 학습자 이해 확인은 서로 다른 판정이다.

## 남은 차단과 필요한 결정

1. **실행 타이밍:** 최신 FIFO 실패는 예정1.2s 주입 전 Front/Rear slot281의 release662ms/deadline666ms 누락이다. 검출666.004077ms·물리 override666.009677ms이며 정상 arm 전 보호했다. 직전 Rear body CPU1.107494ms, 다음 observed wake 지연2.151891ms를 확인했으나 원인/인과 분해는 불가능하다. 공통 release grid·실제 FIFO/CPU 배치는 정상이다. Tracefs EACCES/perf_event_paranoid4 때문에 timer→wakeup→switch·IRQ/preemption/경쟁 작업을 구분하지 못했다. 권한 있는 같은 Host 캡처와 동일 고정 cohort의 실패 보존 재측정이 필요하다. 정상6 OTHER loaded 실패와 기존 M3 실패도 유지한다.
2. **TSan native 정상 기능 실패:** 최초부터 original source/deadline→enqueue→Zone RX/dispatch→Leaf 완료→결과 enqueue/수신을 연결한40회에서 재현되지 않았다. Max Command enqueue→result는 normal0.440508ms/TSan0.465624ms였다. TSan 부담이 과거 실패 원인이라는 증거는 없다. 논리 시험은 결과가 늦으면 이전 명령 expiry 또는 다음 allocation의 pending 충돌이 먼저 보호할 수 있음을 구분했다. 다음 단위는 정상 batch의 settlement 허용 지연과 allocation 경계 계약 검토, 실패 시 동일 full trace 캡처다. 임의 timeout 증가나 원래 untraced 사건의 원인 확정은 하지 않는다.
3. **Middleware SDK 검증:** [정확한 source/stack 분석](test-plan/evidence/m4_contract_review/middleware/analysis.md)을 완료했다. DDS SDK-wide TSan 빌드에도 vendor atomic helper 계측 제외가 있어 기존 “완전 계측” 표현은 모든 동기화 계측을 뜻하지 않는다. 지원되는 TSan-aware atomic/reclamation 설정·동일 memory-order 검토와 최소 index/GC 재현이 필요하다. 단순 강한 atomic 교체는 원래 알고리즘의 안전성 증명이 아니다. Zenoh는 compatible Rust std/dependency 계측 toolchain·binary provenance/debug symbol이 필요하고 cargo/rustc가 없다. Wrapper와 SDK 내부/계측 인식 문제를 확정 분류할 근거가 부족하여 원래 경고는 OPEN이다.
4. **수용 범위 판단:** **Host IO/FIFO 한정 기술 수용 검토**는 가능하지만 이번23/24 결과로 수용할 수 없다. 추천 선행 조건은 새 FIFO 누락 분석·고정 cohort 정상 조건 충족, 정상 result/명령 settlement 계약 검토, SDK 경고에 대한 지원 계측/검토 근거다. 그 뒤 지원 profile/남은 예외에 대한 명시적 검토가 필요하다. OTHER·Target/system·학습자 상태와 원본 실패를 삭제하거나 기본 policy/4ms를 바꾸지 않는다.

## M5 첫 구현 단위

이번에는 M4 원격 계약·candidate probe까지 진행했고 **M5 Central↔Zone 제어 adapter는 미착수**다. M4 전체 종료 선행 조건이 아직 충족되지 않았다.
다음 단위는 위 실행 예외/수용 범위 검토 뒤, Cyclone direct API의 독립 Central↔Front process에서 기존 request→arm→normal command→원천 Actual/result를 왕복시키는 것이다.
공통 clock/netns profile과 원래 source/parent/expiry를 유지하고 방향별 tc loss/delay·이전 message/late ACK 거부·새 durable Epoch/전체 INIT·readiness·arm 재가입을 검증한다.
Front 먼저여도 Central–Front/Rear 병렬 topology와 Rear Drive/BMS/power 책임은 유지하며 fixture/실제 원격 범위를 명시한다.
