# M4 기술 종료 검토 — Host component와 원격 경계

Date: 2026-10-20. Status: **IN PROGRESS / NOT CLOSED**. 현재 상태 기준은 [project_status](project_status.md)다.
학습자 직접 재현/설명은 **REVIEW PENDING**, system32요구/29TC·Target/전체 원격 배포는 **NOT RUN**이다.
이 검토는 위 상태를 PASS로 바꾸지 않는다.

| 종료 항목 | 구현/실제 시험 | 근거/판정 | 차단 여부 |
| --- | --- | --- | --- |
| 정상 request/arm/TX result/status/Actual/protection 소유권 | AsyncCoordinatorPort·AsyncZoneOwner·AsyncLeafOwner; M4AsyncRuntime·AsyncOwnerTest | 실제 BMS/HV/센서 준비·arm 뒤 정상 배분; 함수→시험→두 빌드 결과93개 연결 | Host component PASS |
| owner stop/방향별 loss/delay/부분 송신/보호·재가입 | M4FaultRuntime/Wall·M4OwnerStop/M4Direction; Network::replace_joined_links | 원래 source/deadline, stopped ACK 부재, 별도 physical watchdog, failed link join/교체, 새 durable Epoch/full readiness/arm, 모델/SOC/energy 연속 | Host component PASS; 원격 격리 증거 아님 |
| 실행/메시지/복구 구조 정리 | ADR-0057, boundary compile, CTest disjoint labels | 원본948+이전 검토18+이번7개; `97afb35` normal/ASan·UBSan 각각973/973. Baseline966 이름 유지;19.8ms oracle만 ADR-0059에 따라 수정·원본 보존 | PASS; 실행 시간 동일성 증거 아님 |
| 명령 settlement·주기·실제 authority | ADR-0059; AsyncCoordinatorPort::allocation_ready, VehicleCoordinator::allocate, ControlAllocation::poll | pending이면 due 배분 한 건 보류; 새 명령/완료 tick/기준 시각을 만들지 않음. 성공 후 fresh 입력·기존20ms grid; 원래 TX20ms·request/support/적용 명령 expiry·30ms gap 검사 유지. 지연/만료·Stop·새 Epoch 회귀 PASS | 코드 결함 수정 PASS; wall timing 수용과 별도 |
| 원격 Leaf composite authority/INIT/arm/stop/protection | ICD owner-wire v1; RemoteLeafTest·RemoteZoneIntegration·RemoteOldRequestTest | 이전 Epoch 응답 identity, 최초 sent 기반20ms envelope, issuer/Epoch/token ACK8개씩 불변 보관. 실제 Zone 생산→codec→다섯 Leaf의 arm/명령/Actual/Power/Stop·만료 거부; 신규 계약15개 PASS | Host 계약/component PASS; 전체 원격 process 배포 미실행 |
| 원천 feedback/parent/epoch/sequence/expiry | owner_wire explicit catalogue; NoInnerCanCounterSourceOrCrcIsRegenerated·BMS unknown/zero·real Leaf Actual | CAN/DBC/P05 불변; byte/uint64/binary64 보존; 지연 도착이 원래 expiry로 거부 | PASS component; 전체 DDS Actual 왕복은 M5 |
| clock/source-age/skew/rejoin | RunLeaseGate·mapped_time; RemoteClock/PeerFixture | common kernel monotonic profile 고정; 불확실성 산술 경계 검사; 다른 clock runtime 거부 | Host 계약 PASS; Target sync 후속, Host M5 자체 차단 아님 |
| TBD-05/15 API/QoS/queue/프로세스 | optional DDS/Zenoh6조건×3회, netns/veth/실제 tc/실제 thread·load | v1 30 PASS/6 FAIL 보존, 관측 보완 v2 별도36/36 PASS. QoS만으로 로컬 SPSC/atomic 의미를 재현할 수 없음; 첫 adapter는 bounded lane/실패 latch·full handshake 필요 | 후보 실험과 실제 배포 구분; 세부 결과 공유 근거 참조 |
| 새 workload M3 감시/타이밍 수용 | 기존48회 프로토콜을 `97afb35`에 새 실행 | **42 PASS/6 FAIL**, 설정·부하·grid·사전 할당 control48/48. OTHER loaded normal6 FAIL; FIFO24/24·intentional fault24/24 PASS. `1989477`41/7·FIFO23/24와 이전 실패 보존 | **BLOCK: OPEN-M4-TIM-01**; 과거 FIFO 누락 원인 미확정, 시한/분모 유지 |
| 변경 동시성 sanitizer | `97afb35` TSan 경계108+wall9; 동일 source의 full trace native20+TSan20 | 108/108·9/9 및40/40 PASS, 경합 경고0. `d7115ff`8/9의 CommandDelivery 실패 원인 미확정 | **BLOCK: OPEN-M4-TSAN-01**; 전체973 TSan NOT RUN, 논리 수정/새 PASS로 원인 확정하지 않음 |
| 진단 수집·실패 종료 | check_m4_delivery_trace.py; Python runner 실제 child-process 시험8개 | 전체 예정 결과 저장 후 FAIL/timeout/누락/TSan 경고에 exit1, 전부 PASS는 exit0. 수정 전1 PASS/5 FAIL/2 ERROR→8 PASS; 전체 Python71 PASS | PASS; mock은 실행 성능 검증이 아님 |
| Middleware 동시성 검증 | 기존 wrapper TSan4 FAIL·SDK 재계측 DDS2 FAIL의 version source/stack 분석 | DDS GC progress의 vendor volatile atomic helper가 `no_sanitize("thread")`; 계측 공백 확인이나 실제 lifetime 안전성은 미확정. Zenoh binary/Rust handoff도 미확정. 새 SDK 실행 NOT RUN | **BLOCK: OPEN-M4-MWTSAN-01**; suppress/false positive 종결 없음 |
| 기존 M3 예외 | OPEN-M3-01/02·ADR-0042/43 | 원본 OTHER sanitizer2 FAIL과 kernel trace 권한 제약 유지 | 전체 M3 수용 PENDING; 새 성공으로 닫지 않음 |

최신 commit/환경/명령·수정 전후·원본·CSV/그래프는 [settlement evidence](test-plan/evidence/m4_settlement/README.md),
이전966개·41/7 timing은 [계약 검토 evidence](test-plan/evidence/m4_contract_review/README.md),
원본948개와 이전 실패는 [이전 evidence](test-plan/evidence/m4_followup/README.md)에 묶는다.
기능 PASS, 정상 timing FAIL, TSan race warning 부재, 학습자 이해 확인은 서로 다른 판정이다.

## 남은 차단과 필요한 결정

1. **실행 타이밍:** 새 `97afb35`는42/48 PASS이고 FIFO24/24다. OTHER loaded normal6개는 원래4ms 완료 기회를 놓쳐 실패했다. 각 최초 누락·deadline·검출·override·직전 body/CPU/다음 wake는 [failures.csv](test-plan/evidence/m4_settlement/timing48/failures.csv)에 있다. 독립 보호 성공을 정상 timing PASS로 바꾸지 않는다. 이전 `1989477`의 예정1.2s 주입 전 Front/Rear slot281(release662ms/deadline666ms) 누락과666.004077ms 검출·666.009677ms override는 미해결 이력이다. 이번 미재현이 원인을 증명하지 않는다. 사용자가 같은 Host의 sudo tracefs/perf 접근 성공을 확인했다. 비대화형 agent probe는 여전히 암호를 요구하며 실제 timer/wakeup/sched_switch/IRQ/owner 동시 캡처는 NOT RUN이다. [새 수집기](test-plan/m4_kernel_capture.md)는 별도 instance·원래 사용자 workload·고정 OFF/ON 조건·bounded cleanup/분석을 준비했다. Python90개와 비관리자 smoke만 실행했고, 사용자 터미널의 실제 sudo 캡처와 실패 보존 분석이 다음 단계다. OS 원인으로 단정하지 않는다.
2. **TSan native 정상 기능 실패:** 이번 full trace40/40 PASS에서 Command enqueue→result 최대 normal0.442994ms/TSan0.446838ms를 관측했다. 이전 `d7115ff` 사건은 여전히 미재현·원인 미확정이다. 논리 pending 충돌 결함은 ADR-0059로 수정했고, Rear19.8ms는1025.4ms exclusive deadline에서 보호한다. 양 Zone12ms는 기존 Rear 적용 명령의1011.000001ms expiry가 먼저 보호하는 결과를 유지한다. 다음 native 실패 시 원래 source/deadline·enqueue·RX/dispatch·Leaf 처리/출력 발행·결과 도착의 최초 실패 identity를 대조해야 한다. TSan 부담이나 이번 코드 결함이 과거 원인이라고 확정하지 않는다. Timeout 증가는 없다.
3. **Middleware SDK 검증:** [정확한 source/stack 분석](test-plan/evidence/m4_contract_review/middleware/analysis.md)을 완료했다. DDS SDK-wide TSan 빌드에도 vendor atomic helper 계측 제외가 있어 기존 “완전 계측” 표현은 모든 동기화 계측을 뜻하지 않는다. 지원되는 TSan-aware atomic/reclamation 설정·동일 memory-order 검토와 최소 index/GC 재현이 필요하다. 단순 강한 atomic 교체는 원래 알고리즘의 안전성 증명이 아니다. Zenoh는 compatible Rust std/dependency 계측 toolchain·binary provenance/debug symbol이 필요하고 cargo/rustc가 없다. Wrapper와 SDK 내부/계측 인식 문제를 확정 분류할 근거가 부족하여 원래 경고는 OPEN이다.
4. **수용 범위 판단:** **Host IO/FIFO 한정 기술 수용 검토**는 가능하지만 이번24/24 결과만으로 수용할 수 없다. Settlement 계약/기능 검증은 완료했지만, 과거 FIFO 누락의 원인 분석·동일 고정 cohort의 근거, SDK 경고에 대한 지원 계측/검토 및 지원 범위의 명시적 결정이 남았다. 그 뒤 지원 profile/남은 예외에 대한 명시적 검토가 필요하다. OTHER·Target/system·학습자 상태와 원본 실패를 삭제하거나 기본 policy/4ms를 바꾸지 않는다.

Host PC + Jetson 한 대 내부 여러 vECU 배치를 유지한다. Jetson 일반 커널/PREEMPT_RT 동일 workload 비교는
Target 성능 검증 PLANNED / NOT RUN이다. 이번 커널 교체·MCU 이식·종료 조건 변경은 없다.

## M5 첫 구현 단위

이번에는 M4 pending/expiry 계약·진단 exit와 회귀검증까지 진행했고 **M5 Central↔Zone 제어 adapter는 미착수**다. M4 전체 종료 선행 조건이 아직 충족되지 않았다.
다음 단위는 위 실행 예외/수용 범위 검토 뒤, Cyclone direct API의 독립 Central↔Front process에서 기존 request→arm→normal command→원천 Actual/result를 왕복시키는 것이다.
공통 clock/netns profile과 원래 source/parent/expiry를 유지하고 방향별 tc loss/delay·이전 message/late ACK 거부·새 durable Epoch/전체 INIT·readiness·arm 재가입을 검증한다.
Front 먼저여도 Central–Front/Rear 병렬 topology와 Rear Drive/BMS/power 책임은 유지하며 fixture/실제 원격 범위를 명시한다.
