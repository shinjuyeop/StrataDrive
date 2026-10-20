# M4 Host IO/FIFO 한정 수용 검토안

Date:2026-10-20. **PROPOSED / 사용자 결정 대기**.
현재 승인 상태는 **M4 NOT CLOSED / M5 adapter 미착수**다.
이 문서는 종료 기준·기본 policy·지원 범위를 변경하지 않는다.
[현재 상태](project_status.md), [기존 종료 기준](m4_exit_review.md),
[새 DDS 수명 검증](test-plan/evidence/m4_dds_lifetime/README.md)을 함께 본다.

## 판단과 선택지

**기존 조건을 모두 유지한 M4 전체 종료는 NO-GO**다. DDS 전체 동시성 검증과 과거
두 실행 실패의 원인이 미확정이다. 다만 **검증된 Host native component를 IO/FIFO
조건으로 한정 수용하는 안은 권고할 수 있다.** 수용은 원인 해결 선언과 다르며 아래
명시적 예외 이관과 M5 진입 순서에 대한 사용자 승인이 필요하다.

| 결정 | 기존 조건에 대한 변경 | 영향과 권고 |
| --- | --- | --- |
| A. 기존 M4 종료 조건 유지 | 변경 없음. timing/native/SDK 세 OPEN의 기존 차단 유지 | 현재 적용 상태. 원인/SDK 수명 검증을 계속하며 M5 adapter 보류 |
| B. Host IO/FIFO component 한정 수용 | Host component 범위를 아래 profile로 명시. OTHER loaded 정상 운전 수용 제외를 공식 승인하고 TIM/native 미확정 사건은 OPEN 예외로 이관. SDK 검증은 M5의 transport 단계 진입 gate로 이관 | **조건부 권고안**. Host 기술 단위 종료와 M5 transport qualification 착수가 가능. DDS 정규 제어 adapter의 정상 명령 enable은 SDK gate 이후. 전체 M3/Target/system/학습자 종료를 뜻하지 않음 |

B를 선택해도 기존 실패를 PASS나 RESOLVED로 바꾸지 않는다. 과거 사건과 DDS 경고는
추적·재발 판정·후속 차단이 유지된다. 현재 문서에는 B가 **승인되지 않은 제안**으로만
반영된다. M4 전체 무조건 종료나 M5 정규 제어 허용을 권고하는 근거는 없다.

## 재사용 가능한 소스·시험 근거

[소스/바이너리 대조](test-plan/evidence/m4_dds_lifetime/source-reuse.json): `97afb35`부터
검토 HEAD까지 `central/zone/vecu/interfaces/simulation/cmake/CMakeLists.txt`의 production
변경은 없다. Normal/ASan/TSan의 `actuator_demo`와 runtime test, **6개 SHA256가 모두
기존 근거와 동일**하다. 그 뒤 변경한 runner·수집기·진단 시험을 C++ 제어 경로의 변경으로
취급하거나 예전 결과를 새 실행이라고 부르지 않는다.

기존 [48회](test-plan/evidence/m4_settlement/README.md)는 normal/ASan, OTHER/FIFO,
동일 CPUs0/1, 무부하 또는 CPU1에7ms/10ms OTHER 부하, normal/Drive pause/Monitor overrun을
3회씩 수행했다. 설정·부하·grid·성장 control은48/48 통과했고 결과는42 PASS/6 FAIL이다.
정상 운전 비교만 추리면 다음과 같다. 숫자는 **실제 실행 횟수**, 새 측정값이 아니다.

| Build/정상 조건 | OTHER | FIFO | 입증한 범위 |
| --- | --- | --- | --- |
| Normal, 추가 부하 없음 | 3/3 PASS | 3/3 PASS | 같은 map/주기/시한에서 정상 운전 |
| Normal, CPU1 부하7/10ms | **0/3 PASS** | **3/3 PASS** | 같은 부하에서 FIFO 정상 운전; OTHER 기회/완료 계약 실패 |
| ASan/UBSan, 추가 부하 없음 | 3/3 PASS | 3/3 PASS | 계측된 동일 조건의 기능·기회 관측 |
| ASan/UBSan, CPU1 부하7/10ms | **0/3 PASS** | **3/3 PASS** | 같은 부하에서 FIFO 통과; OTHER 실패 보존 |

나머지 고장24회는 두 policy/build의 Drive pause와 Monitor6ms 지연이다. FIFO12회는
모두 고장 oracle PASS이며 정상 FIFO12회와 합쳐 **FIFO24/24**다. 고장 중 발생하는
미실행 기회를 정상 timing PASS로 바꾸지 않는다. [전체 비교 CSV](test-plan/evidence/m4_dds_lifetime/host-comparison.csv).

[213425 고정 수집](test-plan/evidence/m4_kernel_campaign/completed_213425/README.md)의 FIFO20회는
**Normal build·추가 부하 없는 Monitor overrun**이다. 48회의 loaded 정상 조건을 대체하지
않는다. 추적11쌍 유효, FIFO 주입 전 miss0, 원래 deadline 뒤3.170–5.059µs 검출·
이후1.008–3.484µs Physical override는 독립 감시 경로의 추가 근거다.
OTHER2회는191/186 miss·FAIL이며 정상 arm 전에 보호했다.

이 재사용 범위에서 새 수용용48회나 같은 FIFO 수집을 반복할 누락 조건은 없다.
새 DDS adapter로 실행 부하/스레드/프로세스가 달라지면 그때 별도 원래 프로토콜을
적용한다. 이번 DDS ASan/TSan·수명 시험은 기능/동시성 진단이며 timing 수용 결과가 아니다.

## 제안하는 Host 실행 조건

| 항목 | 한정 수용 profile과 실제 근거 |
| --- | --- |
| Host | 현재 Ubuntu22.04/x86_64, kernel6.8.0-138-generic/PREEMPT_DYNAMIC. Jetson에 이 수치를 이식하지 않음 |
| 기본 정책 | 현재 상속 OTHER 기본은 그대로. 제어 실행 profile은 CLI로 명시한 SCHED_FIFO. profile을 요청했는데 적용 실패하면 SETUP 실패, timing 실패나 PASS로 합치지 않음 |
| 권한 | 검증된 원래 사용자 RTPRIO20/20; vECU/부하 UID1000·effective capabilities0. sudo는 추적 수집만 수행 |
| CPU A=0 | Front18, Rear18, Physical19, Monitor20; 각 thread의 affinity=[0] |
| CPU B=1 | Central11, Steering/Brake/Drive/Power10, BMS9; 각 affinity=[1] |
| 부하 | 무부하 및 CPU1의 OTHER0 7ms busy/10ms period가 검증됨. 임의 고우선순위 RT 경쟁·다른 CPU map·SDK 추가 worker까지 보장하지 않음 |
| 시간 계약 | CLOCK_MONOTONIC grid,2ms 실행 기회/4ms 완료 deadline, 원래 command expiry와 최초 sent 기준20ms envelope. 늦은 회차를 앞선 회차 완료로 채우지 않음 |
| 보호·복구 | 독립 Monitor/Physical 감시와 실제 output override·gate latch. 통신/부분 송신 실패·epoch/parent/lease·준비/arm·durable epoch 재가입은 기존 component 회귀 근거로 유지 |
| IO 범위 | M3 IO 배치 계열과 현재 same-process typed port/mailbox·vCAN component 근거. 아직 없는 실제 DDS control adapter/NIC·원격 process timing을 포함하지 않음 |

현재 관측된 OTHER loaded 실패는 주로 CPU 배정 대기다. 대표 구간에서 timer hard-expiry
초과2.268µs, runnable 대기3.559ms(부하 process3.536ms), body1.102µs였다. 기존 최신-slot
선택 때문에 기회를 놓친 것이며 짧은 body만으로2ms/4ms 계약을 만족한다고 판단할 수 없다.
이 부하 조건의 OTHER 정상 제어는 **미충족**이다. 이를 제외하려면 B의 범위 변경을
명시적으로 승인해야 한다. 이 관측으로 과거 FIFO 사건의 OS 원인을 확정하지 않는다.

## 미확정 사건의 처리안

| OPEN | 복원 가능한 사실 / 없는 정보 | 영향·이미 확인한 보호 | 재발 시 필수 기록 / 처리 제안 |
| --- | --- | --- | --- |
| OPEN-M4-TIM-01: 과거 FIFO | `1989477` Front/Rear slot281 release662ms/deadline666ms 미실행. 직전 Rear body1.117555ms/CPU1.107494ms, 다음 요청 wake662ms→실제 slot282 start664.151891ms. timer 만료/wakeup/switch/IRQ chain 없음 | 실제666.004077ms 검출·666.009677ms physical override. 정상 가용성 실패. 현재97afb35 FIFO24/24와 추가20/20에서 해당 주입 전 사건은 미재현 | 동일 source/binary, 실제 TID·timer/스케줄/IRQ, 요청 wake·job 시작/완료·deadline·보호 이벤트. Rear CPU burst만으로 다음2.15ms 지연의 원인을 확정할 수 없음. A에서는 차단, B에서는 원인 미확정 예외로 OPEN 유지·같은 profile 재발 시 수용 재검토 |
| OPEN-M4-TSAN-01: native CommandDelivery | `d7115ff` 정상 arm810.816152ms 뒤 fault915.290114ms, protection selection915.819030ms. token/source/deadline·구간별 transaction trace 없음. 별도 저장 trace는 후속 PASS | 원본 실패의 최종 모델 pressure1MPa·torque0는 보호 출력으로 바뀐 결과. 정확한 실제 override 시각은 없음. 현재 boundary108+wall9와 두 native40 묶음 PASS; pending 계약 수정은 별도 논리 재현으로 검증 | 최초 요청의 epoch/token/source/expiry, Central enqueue→Zone RX/dispatch→Leaf 적용→result, 실제 gate/모델/ACK. 기존 settlement 수정이나 TSan 부담이 옛 원인이라는 인과 증명 불가. A에서는 차단, B에서는 원래 OTHER/unpinned/guard-OFF 진단 사건을 OPEN 예외로 이관하고 재발 즉시 분석 |
| OPEN-M4-MWTSAN-01: DDS | 29개 경고를4개 수명/게시 계열로 구분. 실제 Writer scope/GC·mutex 수명은 정상6회 및 ASan UAF 대조3회로 좁힘. TSan Writer3회와 wrapper2회는 여전히 FAIL. bucket/remote/WHC 전체 안전성 미확정 | 현재 실제 DDS control adapter가 없으므로 Host component의 명령 경로에는 이 SDK가 참여하지 않음. 향후 원격 adapter에서는 SDK 경쟁/오류가 누락·만료·재시작으로 나타날 수 있음. 기존 in-process gate가 원격 안전성을 보장하지 않음 | 생성/게시/unlink/vtime/마지막 접근/free·callback 종료·mutex destroy를 객체 identity로 연결. A에서는 차단, B에서는 **M5 transport qualification gate**로 이관. 원인/수명 근거 또는 지원되는 수정이 준비되기 전 정규 제어 enable 금지 |

후속 반복은 같은 PASS를 더 모으는 목적이 아니라 새 가설·계측을 검증할 때만 한다.
과거 FIFO/native 실패 로그의 빠진 사건은 새 실행으로 복원할 수 없다.
기존2ms/4ms/expiry/envelope를 완화하거나 기록을 RESOLVED로 바꾸지 않는다.

## B 승인 이후의 M5 첫 단위와 판정

1. **첫 착수: pinned DDS의 두 process transport/lifetime qualification.** Central↔Front의
   bounded ingress/result lane, session/epoch identity, 정상 종료·중간 peer 종료·재시작을
   실제 process로 구분한다. 이 단계에서는 control run gate를 닫아 둔다. DDS의 남은
   bucket/proxy/WHC 경로를 실제 생성·접근·종료·해제로 재현하고, ASan/TSan 결과 및 source
   수명 논증으로 분류하거나 검증된 지원 수정을 비교한다. 기존 증명 없는 경고는 PASS가
   아니며 suppress/seq_cst 일괄 교체로 종결하지 않는다.
2. **기존 계획의 첫 제어 adapter는 그 gate 뒤에 시작.** 실제 Central↔Front의
   Prepare→INIT/ACK→readiness→arm→normal request/result→원천 Actual을 연결한다.
   Front/Rear 병렬 topology와 Rear Drive/BMS/power 책임은 유지한다.
3. **제어 단위 합격:** 정상 경로의 원래 source/epoch/token/parent/lease·CAN/P05·expiry가
   wire 왕복에 보존되고, down/up loss·delay·부분 송신/큐 포화·old epoch/late ACK를 거부한다.
   같은 epoch 자동 복구 금지·durable epoch/full handshake 재가입·모델/에너지 연속을 검사한다.
   독립 원격 감시의 보호와 stopped owner ACK 부재를 확인하고 새 workload의 기존 타이밍
   프로토콜을 별도로 실행한다. 기간/횟수/조건은 구현 전 프로토콜에 고정한다.

이는 SDK의 기존 미완료 조건을 명시적 후속 gate로 옮기는 제안이며 새로운 M4 차단을
추가하지 않는다. B가 승인되기 전에는 M5 구현을 시작하지 않는다.

Host component 수용과 별개로 **학습자 REVIEW PENDING**, Jetson·전체 원격 배포·
32 requirement/29 system TC는 **NOT RUN**이다. 배치는 Host PC + Jetson 한 대 안의 여러
vECU를 유지한다. Jetson 일반 kernel/PREEMPT_RT 비교, NIC/IPC/SocketCAN·clock·CPU/RT
priority 실제 적용과 새 workload의 성능은 Target에서 검증한다. MBD/AUTOSAR 순서는
기존 ADR·로드맵을 유지한다.
