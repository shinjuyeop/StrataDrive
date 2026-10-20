# M4 기술 종료 검토 — Host component와 원격 경계

Date: 2026-10-20. Status: **IN PROGRESS / NOT CLOSED**. 현재 상태 기준은 [project_status](project_status.md)다.
학습자 직접 재현/설명은 **REVIEW PENDING**, system32요구/29TC·Target/전체 원격 배포는 **NOT RUN**이다.
이 검토는 위 상태를 PASS로 바꾸지 않는다.

| 종료 항목 | 구현/실제 시험 | 근거/판정 | 차단 여부 |
| --- | --- | --- | --- |
| 정상 request/arm/TX result/status/Actual/protection 소유권 | AsyncCoordinatorPort·AsyncZoneOwner·AsyncLeafOwner; M4AsyncRuntime·AsyncOwnerTest | 실제 BMS/HV/센서 준비·arm 뒤 정상 배분; 기존56+신규12 함수→시험 추적 | Host component PASS |
| owner stop/방향별 loss/delay/부분 송신/보호·재가입 | M4FaultRuntime/Wall·M4OwnerStop/M4Direction; Network::replace_joined_links | 원래 source/deadline, stopped ACK 부재, 별도 physical watchdog, failed link join/교체, 새 durable Epoch/full readiness/arm, 모델/SOC/energy 연속 | Host component PASS; 원격 격리 증거 아님 |
| 실행/메시지/복구 구조 정리 | ADR-0057, boundary compile, CTest disjoint labels | 912개 이름/assertion 보존;35/36개 logical physical trace byte 동일; 최신948개 normal/ASan·UBSan PASS | PASS |
| 원격 Leaf composite authority/INIT/arm/stop/protection | ICD owner-wire v1; RemoteWire/PeerFixture/RemoteIssuer/RemoteProtection/RemoteLeafTest | 36개 실제 codec/SessionCoordinator/Steering actor·physical sensor component 시험;30ms credit source/60ms max life·20ms result; same-Epoch 자동 복구 금지 | Host 계약/component PASS; 다른 ECU 원격 배포 미실행 |
| 원천 feedback/parent/epoch/sequence/expiry | owner_wire explicit catalogue; NoInnerCanCounterSourceOrCrcIsRegenerated·BMS unknown/zero·real Leaf Actual | CAN/DBC/P05 불변; byte/uint64/binary64 보존; 지연 도착이 원래 expiry로 거부 | PASS component; 전체 DDS Actual 왕복은 M5 |
| clock/source-age/skew/rejoin | RunLeaseGate·mapped_time; RemoteClock/PeerFixture | common kernel monotonic profile 고정; 불확실성 산술 경계 검사; 다른 clock runtime 거부 | Host 계약 PASS; Target sync 후속, Host M5 자체 차단 아님 |
| TBD-05/15 API/QoS/queue/프로세스 | optional DDS/Zenoh6조건×3회, netns/veth/실제 tc/실제 thread·load | v1 30 PASS/6 FAIL 보존, 관측 보완 v2 별도36/36 PASS. QoS만으로 로컬 SPSC/atomic 의미를 재현할 수 없음; 첫 adapter는 bounded lane/실패 latch·full handshake 필요 | 후보 실험과 실제 배포 구분; 세부 결과 공유 근거 참조 |
| 새 workload M3 감시/타이밍 수용 | release-grid replay·공통 absolute timer·독립2/4ms guard; 사전48회×2 | 원본41/7, 수정 후42/6, 분리 후42/6; FIFO각24/24지만 OTHER loaded각0/6. 원본 FIFO extra wake의 kernel 원인 미확정 | **BLOCK: OPEN-M4-TIM-01 partial mitigation**; 시한/분모 유지 |
| 변경 동시성 sanitizer | d7115ff TSan runtime.wall9 + remote36 | remote36/36, native8/9·경합 경고0. 정상 run에서 core CommandDelivery 보호 FAIL(약915.3ms); 추가 trace 진단1 PASS는 실패 대체 아님 | **BLOCK: OPEN-M4-TSAN-01**; 정확한 이전 failure path 미확정 |
| Middleware 동시성 검증 | application/C wrapper ASan·UBSan4회 및 TSan4회, 별도 완전 계측 DDS2회 | ASan4/4, 미계측 DSO와 함께 실행한 TSan4/4 FAIL; 완전 계측 DDS도2/2 FAIL(entity index/hopscotch/GC 경고). SDK 경고를 무시/suppress하지 않음 | **BLOCK: OPEN-M4-MWTSAN-01**; vendor 내부 경고 분석 필요 |
| 기존 M3 예외 | OPEN-M3-01/02·ADR-0042/43 | 원본 OTHER sanitizer2 FAIL과 kernel trace 권한 제약 유지 | 전체 M3 수용 PENDING; 새 성공으로 닫지 않음 |

실제 commit/환경/명령·원본·CSV/그래프는 [후속 evidence](test-plan/evidence/m4_followup/README.md)에 묶는다.
기능 PASS, 정상 timing FAIL, TSan race warning 부재, 학습자 이해 확인은 서로 다른 판정이다.

## 남은 차단과 필요한 결정

1. **실행 타이밍:** 기존 선택 IO/FIFO Host profile은 두 새48회에서 각각24/24 PASS다. 그러나 전체 사전 조건의 OTHER loaded6 FAIL과 원본 FIFO 추가 wake 원인을 해결한 것은 아니다. 전체 timing 수용/요구 범위를 바꾸지 않았으므로 M4 전체 종료는 보류한다. Tracefs/perf 권한이 필요한 관측은 timer expiry→wakeup→switch/TID/IRQ/preemption correlation이다. SYS-PERF/E2E·Target 검증도 별도다.
2. **TSan native 정상 기능 실패:** CommandDelivery 이후 gate 닫힘과 압력1MPa/토크0의 보호 선택을 확인했다. 경합 경고0만으로 PASS라 하지 않는다. 최초 run은 full event trace 환경변수가 없어 정확한20ms 결과/command expiry 경로를 복원할 수 없다. 추가1회 full trace 진단은 재현되지 않았고 원래 실패는 유지한다. 다음 고정 반복에는 처음부터 `STRATADRIVE_M4_RESULTS`를 켜고 결과 deadline·원래 source·RX/dispatch/start/end를 대조한다. 임의 timeout 완화는 하지 않는다.
3. **Middleware SDK 검증:** wrapper만 계측한 TSan4개와 실제 DDS11.0.1 전체를 계측한 진단2개 모두 경고/exit66을 보존했다. 완전 DDS stack은 `ddsrt_chh_lookup`/entity index bucket GC/free 경로이며, SDK의 progress-based reclamation과 sanitizer happens-before 해석 또는 실제 lifetime 문제를 구분해야 한다. 단순 미계측 한계만으로 설명할 수 없고 false positive나 제품 race로 확정하지 않는다. Zenoh Rust SDK 전체 계측은 cargo/Rust toolchain 부재로 미실행이다. DDS 기본 방향은 유지하되 특정 구현체의 배포 수용은 보류한다. 필요 결정은 vendor sanitizer 지원/경고 분석 또는 같은 계약/분모로 다른 DDS 구현체 재검증이며, 기본 추천은 먼저 현재 source/stack을 분석하는 것이다.
4. **수용 범위 판단:** 추천은 위 실패를 OPEN으로 두고 원인/관측을 보완한 뒤 **Host IO/FIFO에 한정한 M4 기술 수용 여부**를 검토하는 것이다. OTHER도 같은 정상 timing 지원 조건으로 유지하면 현 기준은 실패이며 종료할 수 없다. FIFO 한정 수용을 택해도 원본 FAIL/Target/system/학습자 상태는 유지하고, M5 workload에서 다시 측정해야 한다. 이는 기본 실행 policy를 자동 FIFO로 바꾸거나4ms 조건을 완화하는 결정이 아니다.

## M5 첫 구현 단위

이번에는 M4 원격 계약·candidate probe까지 진행했고 **M5 Central↔Zone 제어 adapter는 미착수**다. M4 전체 종료 선행 조건이 아직 충족되지 않았다.
다음 단위는 위 실행 예외/수용 범위 검토 뒤, Cyclone direct API의 독립 Central↔Front process에서 기존 request→arm→normal command→원천 Actual/result를 왕복시키는 것이다.
공통 clock/netns profile과 원래 source/parent/expiry를 유지하고 방향별 tc loss/delay·이전 message/late ACK 거부·새 durable Epoch/전체 INIT·readiness·arm 재가입을 검증한다.
Front 먼저여도 Central–Front/Rear 병렬 topology와 Rear Drive/BMS/power 책임은 유지하며 fixture/실제 원격 범위를 명시한다.
