# M4 기술 종료 검토 — Host component와 원격 경계

Date: 2026-10-20. Status: **IN PROGRESS / NOT CLOSED**. 현재 상태 기준은 [project_status](project_status.md)다.
학습자 직접 재현/설명은 **REVIEW PENDING**, system32요구/29TC·Target/전체 원격 배포는 **NOT RUN**이다.
이 검토는 위 상태를 PASS로 바꾸지 않는다.

`1a4afe5` 후속은 [고정 커널 수집 준비/검사](test-plan/evidence/m4_kernel_campaign/README.md)와
[native·SDK 진단](test-plan/evidence/m4_sdk_followup/README.md)까지 진행했다.
최신 Python112 PASS, 이전 native40 PASS이나 과거 실패 원인은 미확정이다.
사용자의 별도 `d3e7f6d` 고정 수집213425는 **11/11쌍 VALID**, OTHER2 FAIL·FIFO20 PASS다.
FIFO 주입 전 deadline 누락0건, 예정된 Monitor sleep 중 Physical이 원래 deadline 뒤
3.170–5.059µs 검출·그 뒤1.008–3.484µs 출력을 보호했다. 실제 사용자20/20·FIFO 배치·
marker/cleanup·유실0을 확인했다. 이전212418 CPU9 유실/INVALID·FIFO20회 NOT RUN은
보존한다. [전체 분모·시간축·재현](test-plan/evidence/m4_kernel_campaign/completed_213425/README.md).
새20회는 과거 FIFO 누락의 원인 해소나 기존48회 수용 시험의 대체가 아니다.

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
| 고정 kernel 관측/수집 보완 | `d3e7f6d` OTHER1+FIFO10 OFF/ON,22 workload | 11쌍 VALID; OTHER191/186 miss·2 FAIL, FIFO20 PASS·주입 전 miss0·예정된 보호 확인. 버퍼/RT 한도/설정/정리 실제 검증 | 수집 보완 확인; 과거 FIFO 원인 OPEN, 별도 진단이며 timing 수용 대체 아님 |
| 변경 동시성 sanitizer | `97afb35` TSan 경계108+wall9; 동일 source의 full trace native20+TSan20 | 108/108·9/9 및40/40 PASS, 경합 경고0. `d7115ff`8/9의 CommandDelivery 실패 원인 미확정 | **BLOCK: OPEN-M4-TSAN-01**; 전체973 TSan NOT RUN, 논리 수정/새 PASS로 원인 확정하지 않음 |
| 진단 수집·실패 종료 | check_m4_delivery_trace.py; Python runner 실제 child-process 시험8개 | 전체 예정 결과 저장 후 FAIL/timeout/누락/TSan 경고에 exit1, 전부 PASS는 exit0. 수정 전1 PASS/5 FAIL/2 ERROR→8 PASS; 전체 Python71 PASS | PASS; mock은 실행 성능 검증이 아님 |
| Middleware 동시성 검증 | 기존 실패 보존 + DDS 공식 TSan4회·helper9회·Zenoh 초기8회/동일 nightly 비교8회 | DDS4 FAIL, helper 관측 공백 재현; GC lifetime 안전성은 미확정. Rust 설치·nested build-std 전달 보완; 동일 조건 Zenoh partial4 FAIL/full4 PASS. 원래 배포 binary provenance와 전체 feature 수용은 별도 | **BLOCK: OPEN-M4-MWTSAN-01**; SDK atomic 변경/suppression 없음 |
| 기존 M3 예외 | OPEN-M3-01/02·ADR-0042/43 | 원본 OTHER sanitizer2 FAIL과 kernel trace 권한 제약 유지 | 전체 M3 수용 PENDING; 새 성공으로 닫지 않음 |

최신 commit/환경/명령·수정 전후·원본·CSV/그래프는 [settlement evidence](test-plan/evidence/m4_settlement/README.md),
이전966개·41/7 timing은 [계약 검토 evidence](test-plan/evidence/m4_contract_review/README.md),
원본948개와 이전 실패는 [이전 evidence](test-plan/evidence/m4_followup/README.md)에 묶는다.
기능 PASS, 정상 timing FAIL, TSan race warning 부재, 학습자 이해 확인은 서로 다른 판정이다.

## 남은 차단과 필요한 결정

1. **실행 타이밍:** 새 `97afb35`는42/48 PASS이고 FIFO24/24다. OTHER loaded normal6개는 원래4ms 완료 기회를 놓쳐 실패했다. 각 최초 누락·deadline·검출·override·직전 body/CPU/다음 wake는 [failures.csv](test-plan/evidence/m4_settlement/timing48/failures.csv)에 있다. 독립 보호 성공을 정상 timing PASS로 바꾸지 않는다. 이전 `1989477`의 예정1.2s 주입 전 Front/Rear slot281(release662ms/deadline666ms) 누락과666.004077ms 검출·666.009677ms override는 미해결 이력이다. 이번 미재현이 원인을 증명하지 않는다. 사용자 compact-v2 kernel capture 중185513쌍은 OFF243/ON159 miss지만 추적은 유실 없이 VALID다. 최초 조향 timer 초과3.714µs·CPU 배정대기2.856ms·body1.125µs, 최신-slot 선택으로2ms 기회가 누락되고4ms deadline 뒤65.184µs 검출·4.895µs 뒤 physical override를 확인했다. 이 OTHER 구간의 CPU contention 위치를 확인했으며 FIFO의 원인 증명은 아니다. [전체 원본/시간축](test-plan/evidence/m4_kernel_valid/README.md)을 따른다. 앞선183050쌍은 OFF176/ON311 miss, CPU1 event256668개 유실로 INVALID 이력이다. syscall pretty-printer와 relative realtime clock 처리 결함을 수정해762977 event 전부 파싱했어도9076 chain은 UNTRUSTED로 유지한다. 두 시도의 instance 제거/global 불변을 확인했고, 앞선183033 export EBADF는 원인 OPEN이다. [수집기 compact-v2](test-plan/m4_kernel_capture.md)는 필수 event 유지·optional 감소·CPU1 buffer32MiB를 적용했으며95개 Python 검사를 통과했다. 후속185446/185458 두 쌍의 EBADF stack은 종료 trace_marker 쓰기 실패를 가리킨다. Kernel ring reserve 실패/CPU2 포화가 후보이나 실패 통계가 없어 확정하지 않는다. `eecc1d7`의 실패 후 raw/stat 보존·collector CPU2MiB 배분은97개 Python 검사 통과, 당시 새 실제 tracefs 검증은 NOT RUN이었다. 이후212418에서 두 marker·정리 성공과 사용자20/20 복원을 실제 확인했으나 CPU9 유실로 INVALID라서 FIFO는 미실행이다. Background buffer 보완 후213425 고정11쌍은 모두 유효하고 FIFO20회 주입 전 누락은 없었으며 예정된 보호가 PASS다. 해당20회 미재현을 과거 FIFO 원인 해결로 간주하지 않는다. [원본/재분석](test-plan/evidence/m4_kernel_capture_followup/README.md)을 보존하며 OS 원인으로 단정하지 않는다.
2. **TSan native 정상 기능 실패:** `97afb35` full trace40/40 PASS에서 Command enqueue→result 최대 normal0.442994ms/TSan0.446838ms를 관측했다. 이전 `d7115ff` 사건은 여전히 미재현·원인 미확정이다. 논리 pending 충돌 결함은 ADR-0059로 수정했고, Rear19.8ms는1025.4ms exclusive deadline에서 보호한다. 양 Zone12ms는 기존 Rear 적용 명령의1011.000001ms expiry가 먼저 보호하는 결과를 유지한다. 다음 native 실패 시 원래 source/deadline·enqueue·RX/dispatch·Leaf 처리/출력 발행·결과 도착의 최초 실패 identity를 대조해야 한다. TSan 부담이나 이번 코드 결함이 과거 원인이라고 확정하지 않는다. Timeout 증가는 없다.
3. **Middleware SDK 검증:** [후속 근거](test-plan/evidence/m4_sdk_followup/README.md)에서 DDS 공식 `SANITIZER=thread` 빌드4회 모두 경고를 재현했다. Vendor helper의 invisible handoff는 최소9회 대조로 확인했으나 GC/vtime 회수 알고리즘의 정확성은 입증하지 않았다. Zenoh 도구 부재는 해소했다: 프로젝트 전용 Rust1.97.1·nightly/rust-src, nested Cargo에도 build-std를 전달하는 설정으로 전체 Rust 계측 빌드를 완료했다. 동일 nightly/probe/runtime/TCP feature 비교에서 partial4 FAIL/full4 PASS, runtime positive/negative6회 검출 동작을 확인했다. 이는 이 재현의 계측 공백을 뒷받침하며 기존 standalone binary의 모든 경고를 false positive로 종결하는 근거는 아니다. GCC11 runtime 미지원 callback은 동일 Rust LLVM23 runtime 사용으로 분리했고 Clang14 혼합 interop 실험/전체 feature qualification은 별도 검토 대상이다. Suppression·SDK atomic 교체는 없다.
4. **수용 범위 판단:** **Host IO/FIFO 한정 기술 수용 검토**는 가능하지만 이번24/24 결과만으로 수용할 수 없다. Settlement 계약/기능 검증은 완료했지만, 과거 FIFO 누락의 원인 분석·동일 고정 cohort의 근거, SDK 경고에 대한 지원 계측/검토 및 지원 범위의 명시적 결정이 남았다. 그 뒤 지원 profile/남은 예외에 대한 명시적 검토가 필요하다. OTHER·Target/system·학습자 상태와 원본 실패를 삭제하거나 기본 policy/4ms를 바꾸지 않는다.

Host PC + Jetson 한 대 내부 여러 vECU 배치를 유지한다. Jetson 일반 커널/PREEMPT_RT 동일 workload 비교는
Target 성능 검증 PLANNED / NOT RUN이다. 이번 커널 교체·MCU 이식·종료 조건 변경은 없다.

## M5 첫 구현 단위

이번에는 M4 고정 커널 수집기·원래 RT 한도 보존·SDK 계측과 native 진단까지 진행했고 **M5 Central↔Zone 제어 adapter는 미착수**다. M4 전체 종료 선행 조건이 아직 충족되지 않았다.
다음 단위는 위 실행 예외/수용 범위 검토 뒤, Cyclone direct API의 독립 Central↔Front process에서 기존 request→arm→normal command→원천 Actual/result를 왕복시키는 것이다.
공통 clock/netns profile과 원래 source/parent/expiry를 유지하고 방향별 tc loss/delay·이전 message/late ACK 거부·새 durable Epoch/전체 INIT·readiness·arm 재가입을 검증한다.
Front 먼저여도 Central–Front/Rear 병렬 topology와 Rear Drive/BMS/power 책임은 유지하며 fixture/실제 원격 범위를 명시한다.
