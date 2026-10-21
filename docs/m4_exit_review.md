# M4 기술 종료 검토 — Host component와 원격 경계

Updated: 2026-10-21. Status: **HOST IO/FIFO COMPONENT LIMITED ACCEPTANCE / M4 NOT CLOSED**. 현재 상태 기준은 [project_status](project_status.md)다.
학습자 직접 재현/설명은 **REVIEW PENDING**, system32요구/29TC·Target/전체 원격 배포는 **NOT RUN**이다.
이 검토는 위 상태를 PASS로 바꾸지 않는다.

`1a4afe5` 후속은 [고정 커널 수집 준비/검사](test-plan/evidence/m4_kernel_campaign/README.md)와
[native·SDK 진단](test-plan/evidence/m4_sdk_followup/README.md)까지 진행했다.
해당 수집기 단계 Python112 PASS, 이전 native40 PASS이나 과거 실패 원인은 미확정이다.
사용자의 별도 `d3e7f6d` 고정 수집213425는 **11/11쌍 VALID**, OTHER2 FAIL·FIFO20 PASS다.
FIFO 주입 전 deadline 누락0건, 예정된 Monitor sleep 중 Physical이 원래 deadline 뒤
3.170–5.059µs 검출·그 뒤1.008–3.484µs 출력을 보호했다. 실제 사용자20/20·FIFO 배치·
marker/cleanup·유실0을 확인했다. 이전212418 CPU9 유실/INVALID·FIFO20회 NOT RUN은
보존한다. [전체 분모·시간축·재현](test-plan/evidence/m4_kernel_campaign/completed_213425/README.md).
새20회는 과거 FIFO 누락의 원인 해소나 기존48회 수용 시험의 대체가 아니다.

`c52445a` 후속의 [실제 DDS 수명 근거](test-plan/evidence/m4_dds_lifetime/README.md)는
Writer 한 경로의 GC/TSan 가시성을 좁혔지만 SDK 전체 동시성 차단을 닫지는 못했다.
Middleware runner의 오류 exit0를 수정했고 신규8개·전체 Python120개가 통과했다.
**기존 M4 전체 종료는 NO-GO**다. [Host IO/FIFO component 한정 수용 검토안](m4_host_acceptance_review.md)은
검증된 실행 profile과 과거 사건·DDS gate의 명시적 이관안을 제시한다.
사용자는 `7bbafc7` 검토 뒤 **B안을 승인**했다. 승인한 Host profile 안에서만 component를
한정 수용한다. OTHER loaded 실패·과거 FIFO/native 사건·DDS 경고는 OPEN으로 남는다.
DDS는 **M5 정규 제어 연결 전 필수 gate**이며 Target/system/학습자·전체 M4 종료는 승인하지 않았다.
현재 배치·FIFO priority·2ms/4ms·expiry/20ms envelope 및 보호 계약은 유지한다.

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
| 새 workload M3 감시/타이밍 수용 | 기존48회 프로토콜을 `97afb35`에 새 실행 | **42 PASS/6 FAIL**, 설정·부하·grid·사전 할당 control48/48. OTHER loaded normal6 FAIL; FIFO24/24·intentional fault24/24 PASS. `1989477`41/7·FIFO23/24와 이전 실패 보존 | **OPEN-M4-TIM-01 / 승인한 Host 범위의 미확정 예외**; 전체 timing 미충족, 원인·시한·분모 유지 |
| 고정 kernel 관측/수집 보완 | `d3e7f6d` OTHER1+FIFO10 OFF/ON,22 workload | 11쌍 VALID; OTHER191/186 miss·2 FAIL, FIFO20 PASS·주입 전 miss0·예정된 보호 확인. 버퍼/RT 한도/설정/정리 실제 검증 | 수집 보완 확인; 과거 FIFO 원인 OPEN, 별도 진단이며 timing 수용 대체 아님 |
| 변경 동시성 sanitizer | `97afb35` TSan 경계108+wall9; 동일 source의 full trace native20+TSan20 | 108/108·9/9 및40/40 PASS, 경합 경고0. `d7115ff`8/9의 CommandDelivery 실패 원인 미확정 | **OPEN-M4-TSAN-01 / 승인한 Host 범위의 미확정 예외**; 전체973 TSan NOT RUN, 논리 수정/새 PASS로 원인 확정하지 않음 |
| 진단 수집·실패 종료 | check_m4_delivery_trace.py; Python runner 실제 child-process 시험8개 | 전체 예정 결과 저장 후 FAIL/timeout/누락/TSan 경고에 exit1, 전부 PASS는 exit0. 수정 전1 PASS/5 FAIL/2 ERROR→8 PASS; 전체 Python71 PASS | PASS; mock은 실행 성능 검증이 아님 |
| Middleware 동시성 검증 | 기존 DDS4 FAIL/helper9회·Zenoh matched8회 보존 + 실제 Writer 수명12회·wrapper4회 | Writer normal3/ASan3 PASS·TSan3 FAIL, ASan UAF control3 검출; 초기 harness12 setup 실패 별도 보존. wrapper ASan2 PASS/TSan2 FAIL. 실제 awake-vtime→GC 경로의 좁은 계측 공백 근거; bucket/proxy/WHC 안전성 OPEN. Zenoh partial4 FAIL/full4 PASS 이력 유지 | **BLOCK M5 CONTROL: OPEN-M4-MWTSAN-01**; wrapper 종료 결함 확인 안 됨; SDK algorithm/pin 변경·suppression 없음 |
| Middleware runner 실패 종료 | run_probe.py::checked_result/run_trial/main; MiddlewareProbeExitTest 8개 | 수정 전2 PASS/5 FAIL/1 ERROR→8 PASS; 전체 Python120/120. FAIL/경고/timeout/누락을 보존하고 nonzero, 실제 TSan wrapper도 exit1. 기존36 결과 offline 재검사36 PASS는 새 workload 실행 아님 | 도구 결함 수정 PASS; SDK 경고는 FAIL 유지 |
| 기존 M3 예외 | OPEN-M3-01/02·ADR-0042/43 | 원본 OTHER sanitizer2 FAIL·과거 원인 미확정 유지; kernel 접근은 사용자 고정 sudo 수집으로 확보 | 전체 M3 수용 PENDING; 새 성공으로 닫지 않음 |

최신 commit/환경/명령·수정 전후·원본·CSV/그래프는 [settlement evidence](test-plan/evidence/m4_settlement/README.md),
이전966개·41/7 timing은 [계약 검토 evidence](test-plan/evidence/m4_contract_review/README.md),
원본948개와 이전 실패는 [이전 evidence](test-plan/evidence/m4_followup/README.md)에 묶는다.
기능 PASS, 정상 timing FAIL, TSan race warning 부재, 학습자 이해 확인은 서로 다른 판정이다.

## 남은 차단과 필요한 결정

1. **실행 타이밍:** 새 `97afb35`는42/48 PASS이고 FIFO24/24다. OTHER loaded normal6개는 원래4ms 완료 기회를 놓쳐 실패했다. 각 최초 누락·deadline·검출·override·직전 body/CPU/다음 wake는 [failures.csv](test-plan/evidence/m4_settlement/timing48/failures.csv)에 있다. 독립 보호 성공을 정상 timing PASS로 바꾸지 않는다. 이전 `1989477`의 예정1.2s 주입 전 Front/Rear slot281(release662ms/deadline666ms) 누락과666.004077ms 검출·666.009677ms override는 미해결 이력이다. 이번 미재현이 원인을 증명하지 않는다. 사용자 compact-v2 kernel capture 중185513쌍은 OFF243/ON159 miss지만 추적은 유실 없이 VALID다. 최초 조향 timer 초과3.714µs·CPU 배정대기2.856ms·body1.125µs, 최신-slot 선택으로2ms 기회가 누락되고4ms deadline 뒤65.184µs 검출·4.895µs 뒤 physical override를 확인했다. 이 OTHER 구간의 CPU contention 위치를 확인했으며 FIFO의 원인 증명은 아니다. [전체 원본/시간축](test-plan/evidence/m4_kernel_valid/README.md)을 따른다. 앞선183050쌍은 OFF176/ON311 miss, CPU1 event256668개 유실로 INVALID 이력이다. syscall pretty-printer와 relative realtime clock 처리 결함을 수정해762977 event 전부 파싱했어도9076 chain은 UNTRUSTED로 유지한다. 두 시도의 instance 제거/global 불변을 확인했고, 앞선183033 export EBADF는 원인 OPEN이다. [수집기 compact-v2](test-plan/m4_kernel_capture.md)는 필수 event 유지·optional 감소·CPU1 buffer32MiB를 적용했으며95개 Python 검사를 통과했다. 후속185446/185458 두 쌍의 EBADF stack은 종료 trace_marker 쓰기 실패를 가리킨다. Kernel ring reserve 실패/CPU2 포화가 후보이나 실패 통계가 없어 확정하지 않는다. `eecc1d7`의 실패 후 raw/stat 보존·collector CPU2MiB 배분은97개 Python 검사 통과, 당시 새 실제 tracefs 검증은 NOT RUN이었다. 이후212418에서 두 marker·정리 성공과 사용자20/20 복원을 실제 확인했으나 CPU9 유실로 INVALID라서 FIFO는 미실행이다. Background buffer 보완 후213425 고정11쌍은 모두 유효하고 FIFO20회 주입 전 누락은 없었으며 예정된 보호가 PASS다. 해당20회 미재현을 과거 FIFO 원인 해결로 간주하지 않는다. [원본/재분석](test-plan/evidence/m4_kernel_capture_followup/README.md)을 보존하며 OS 원인으로 단정하지 않는다.
2. **TSan native 정상 기능 실패:** `97afb35` full trace40/40 PASS에서 Command enqueue→result 최대 normal0.442994ms/TSan0.446838ms를 관측했다. 이전 `d7115ff` 사건은 여전히 미재현·원인 미확정이다. 논리 pending 충돌 결함은 ADR-0059로 수정했고, Rear19.8ms는1025.4ms exclusive deadline에서 보호한다. 양 Zone12ms는 기존 Rear 적용 명령의1011.000001ms expiry가 먼저 보호하는 결과를 유지한다. 다음 native 실패 시 원래 source/deadline·enqueue·RX/dispatch·Leaf 처리/출력 발행·결과 도착의 최초 실패 identity를 대조해야 한다. TSan 부담이나 이번 코드 결함이 과거 원인이라고 확정하지 않는다. Timeout 증가는 없다.
3. **Middleware SDK 검증:** [기존 근거](test-plan/evidence/m4_sdk_followup/README.md)의 DDS 공식 TSan4회29경고를 publication bucket3·GC bucket7·Writer/WHC4·remote object15로 묶었다. 반복 경고 수를 결함 수로 세지 않는다. [실제 Writer 시험](test-plan/evidence/m4_dds_lifetime/README.md)은 독립 deleter·awake reader·allocator hook으로 마지막 접근→quiescence→실제 mutex/free를 연결했다. Normal3/ASan3 PASS와 고의 UAF3 검출, TSan3 FAIL/각2경고는 해당 경로의 invisible vtime handoff를 뒷받침한다. bucket array·proxy/lease publication·receive AckNack/WHC의 수명은 아직 독립 검증되지 않았다. wrapper ASan 정상/overflow2 PASS, TSan2 FAIL이며 wrapper 소유권·종료 순서 결함은 확인되지 않았다. 초기 harness12 setup 실패를 SDK 결함으로 세지 않고 보존했다. SDK11.0.1 유지; upstream PR2162는 closed/unmerged라 적용하지 않았다. Suppression·SDK atomic 일괄 교체는 없다. 이전 Zenoh matched partial4 FAIL/full4 PASS와 도구 확보 근거는 재사용하며 새 빌드 반복으로 분모를 늘리지 않았다.
4. **수용 범위 판단:** 기존 전체 종료는 **NO-GO**다. 다만 production source/6개 바이너리 동일성, 기존 matched48회 중 FIFO24/24·최신 별도 무부하 고장20회·보호 시간축을 근거로 [Host native IO/FIFO 한정 수용안](m4_host_acceptance_review.md)을 **조건부 권고**한다. A는 비선택 대안으로 보존한다. B는 명시된 FIFO profile만 Host component 수용하고 OTHER loaded 실패와 과거 FIFO/native 사건은 OPEN 예외로 보존하며, DDS 전체 qualification을 M5 transport gate로 이관하는 변경안이다. B는 사용자 승인에 따라 Host component 한정 수용으로 적용했다. 실제 DDS 정규 제어 adapter enable은 그 gate 통과 뒤다. 한정 수용은 M3 전체·Target/system·학습자 종료나 과거 원인의 해결을 뜻하지 않는다. 재발 영향·검증한 보호·필요 기록과 이관 근거는 검토안에 구체화했다.

Host PC + Jetson 한 대 내부 여러 vECU 배치를 유지한다. Jetson 일반 커널/PREEMPT_RT 동일 workload 비교는
Target 성능 검증 PLANNED / NOT RUN이다. 이번 커널 교체·MCU 이식·종료 조건 변경은 없다.

## M5 첫 구현 단위

이번 후속에서는 DDS 실제 수명 진단과 middleware runner 수정·Host 수용 검토까지 수행했고
**M5 Central↔Zone 제어 adapter는 미착수**다. M4 전체 종료 선행 조건은 충족되지 않았다.
승인한 B안에 따라 정상 제어 gate를 닫은 독립 Central↔Front DDS process에서
생성·통신·종료·재시작과 bucket/proxy/WHC 수명을 먼저 검증한다. SDK gate 통과 전 정규 제어는 허용하지 않는다. 조건을 모두 충족하면 추가 승인 없이 adapter를 진행한다.
그 뒤 기존 request→arm→normal command→원천 Actual/result adapter를 구현한다.
공통 clock/netns profile과 원래 source/parent/expiry, 방향별 loss/delay·old message/late ACK 거부·
새 durable Epoch/전체 INIT·readiness·arm·독립 보호를 검증한다.
Front 먼저여도 Central–Front/Rear 병렬 topology와 Rear Drive/BMS/power 책임을 유지한다.
정확한 첫 단위·합격 기준·이관 전후는 [수용 검토안](m4_host_acceptance_review.md)에 둔다.

## 승인 후 M5 gate 실제 판정 — 2026-10-21

[새 근거](test-plan/evidence/m5_dds_qualification/README.md):42회23 PASS/19 FAIL,
GDB1회와 의도한 timeout이 재현되지 않아 post-check가 실패한 추가1회는 별도 보존한다.
첫5회 build/setup 실패는 runtime NOT RUN이다. SDK pin/알고리즘·제품 source는 변경하지 않았다.
실제 bucket/WHC·Proxy/lease/mutex 객체 관측을 확장했지만 전체 수명 안전성은 승인하지 않는다.

| M5 정규 제어 연결 조건 | 현재 판정 |
| --- | --- |
| 통신·종료·재시작 계약 통과 | **미충족**. 원래20ms normal 전달 실패·full reliable RHC close timeout 보존. 명시적 quiesce/drain→새43·old42 거부는 기능 통과하지만 이보다 좁은 조건 |
| 경고별 수정 또는 개별 계측 한계/수명 근거 | **미충족**. scoped bucket/WHC 근거와 실제 Proxy 생성/관측/free 연결 확보. remote lease·TKMAP·다른 callback interleaving은 OPEN |
| 실제 경로에 설명되지 않은 메모리 경고 부재 | **FAIL**. TSan 원본98 warning occurrences 보존; 다른 결함98개라는 뜻 아님 |
| 실제 SDK 버전·빌드·기능 연결 | 진단11.0.1/e54e991 세 library SHA·compile/run/source 기록 확인. 숨겨진 lookup은 동일 vendor source의 진단 object이며 실제 정규 adapter 구성은 NOT BUILT/NOT RUN |

따라서 **DDS control gate CLOSED / Central↔Front 정규 제어 adapter 미착수**다.
OPEN-M5-DDS-CLOSE-01(full RHC/awake recv/GC close wait), OPEN-M5-DDS-DELIVERY-01
(원래20ms 전달 미충족)과 기존 OPEN-M4-MWTSAN-01을 추적한다. B의 Host 한정 수용은 유지한다.
SDK 경고·원래 OTHER/FIFO/native 실패, 학습자/Target/system 상태는 변경하지 않는다.
추가 조사는 사용자가 보고한 Daybreak 인증 요구로 보류했다. 이미 완료한 로컬 실행 결과는 유지하며
인증 우회·추가 SDK 실험은 하지 않았다. 인증 문제 해소 뒤 미확정 경로와 지원되는 close 해결책을
검증하고 위 조건을 모두 충족할 때만 추가 승인 없이 adapter를 진행한다.
