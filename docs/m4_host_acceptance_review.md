# M4 Host IO/FIFO 한정 수용 검토안

2026-10-22 승인 범위 반영: [Host FIFO 후속](test-plan/evidence/m5_someip_fifo_refresh/README.md)의
필수 조건은 실제8참여자 Central↔Front Normal FIFO 정상 운전·핵심 보호/종료/재가입이다.
OTHER 부하 timing은 지원 한계 진단으로 분리하며, sanitizer wall time은 Normal 성능과 별도다.
실제 메모리/UB/경합 오류는 계속 FAIL이다. 최종 FIFO8/8·ASan/TSan SDK 각2/2이나,
과거69,603ns short-support 정상 갱신 경로는 아직 수정하지 못해 **FIFO 통합 수용 확대와
Rear 진행은 보류**한다. 영속 Epoch 발급을 감시 전에 완료하고 만료 허가 ready 판정을 수정했다.
기존 Host IO/FIFO component 수용·M4 NOT CLOSED·DDS FAIL/OPEN·Jetson/system NOT RUN은 유지한다.


2026-10-21 후속: [SOME/IP 실제 Host Central↔Front adapter](test-plan/evidence/m5_someip_front_adapter/README.md)를
functional SIL 범위에 조건부 채택했다. 실제8-role 세션·독립 보호·새 Epoch 복구 근거이며,
이 문서의 M4 전체 NOT CLOSED·Host native IO/FIFO 한정 수용·기존 DDS FAIL/OPEN을 변경하지 않는다.
[후속 native 연결·실제48회](test-plan/evidence/m5_someip_native_watch/README.md)는31 PASS/17 FAIL이다.
Normal FIFO 정상 무부하/부하는각3/3이지만 전체 고장/복구 수용은 보류하며 이 M4 판정은 유지한다.

Updated:2026-10-21. **B APPROVED — Host native IO/FIFO component 한정 수용**.
승인 근거: `7bbafc7` 검토 뒤 사용자의 명시적 B안 승인.
**M4 전체 NOT CLOSED / DDS 제어 gate CLOSED**다. M5 transport qualification은 착수한다.
승인은 아래 Host component 범위에만 적용한다. 기본 OTHER policy·Ubuntu/CPU/FIFO 배치·
2ms 기회/4ms deadline·명령 expiry/20ms envelope와 보호 조건은 변경하지 않는다.
[현재 상태](project_status.md), [기존 종료 기준](m4_exit_review.md),
[새 DDS 수명 검증](test-plan/evidence/m4_dds_lifetime/README.md)을 함께 본다.

`658562e` 후속 [종료·TSan 경로별 검토](test-plan/evidence/m5_dds_shutdown_followup/README.md)에서도
full-RHC 종료 OPEN·64회 경고 FAIL이 남아 DDS 정규 adapter 연결은 불가다.
관련 Python29/29는 fresh-checkout 준비/실패 수집 검증이며 SDK 수용 근거가 아니다.

별도 [SOME/IP 파일럿](test-plan/evidence/m5_someip_pilot/README.md)은 Host 두 프로세스
component 경로의 조건부 후보 검증이다. 지정 기능과 실제 SDK 계측 결과를 확보했지만
전체 session/보호/Target 배포는 미검증이며, 이 문서의 한정 수용이나 DDS gate를 변경하지 않는다.

## 판단과 선택지

**기존 조건을 모두 유지한 M4 전체 종료는 NO-GO**다. DDS 전체 동시성 검증과 과거
두 실행 실패의 원인이 미확정이다. 다만 **검증된 Host native component를 IO/FIFO
조건으로 한정 수용하는 안은 권고할 수 있다.** 수용은 원인 해결 선언과 다르며 아래
명시적 예외 이관과 M5 진입 순서를 사용자가 승인했다. DDS 안전성 승인·전체 M4 종료는 아니다.

| 결정 | 기존 조건에 대한 변경 | 영향과 권고 |
| --- | --- | --- |
| A. 기존 M4 종료 조건 유지 | 변경 없음. timing/native/SDK 세 OPEN의 기존 차단 유지 | 비선택 대안으로 보존. 원래 전체 종료 조건은 여전히 미충족 |
| B. Host IO/FIFO component 한정 수용 | Host component 범위를 아래 profile로 명시. OTHER loaded 정상 운전 수용 제외를 공식 승인하고 TIM/native 미확정 사건은 OPEN 예외로 이관. SDK 검증은 M5의 transport 단계 진입 gate로 이관 | **승인·적용**. Host 한정 기술 단위 수용과 M5 transport qualification 착수. DDS 정규 제어 adapter의 정상 명령 enable은 SDK gate 이후. 전체 M3/Target/system/학습자 종료를 뜻하지 않음 |

B를 선택해도 기존 실패를 PASS나 RESOLVED로 바꾸지 않는다. 과거 사건과 DDS 경고는
추적·재발 판정·후속 차단이 유지된다. B는 이 범위로 승인됐고 OTHER 부하 실패·과거 FIFO/native 사건·DDS 경고는
원본과 함께 OPEN 예외로 유지한다. M4 전체 무조건 종료나 M5 정규 제어 허용을 권고하는 근거는 없다.

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

## 승인한 Host 실행 조건

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
이 부하 조건의 OTHER 정상 제어는 **미충족**이다. B 승인으로 이 부하 조건의 OTHER 정상 운전은 한정 수용 범위에서
명시적으로 제외했다. 실패 판정 자체는 변경하지 않는다. 이 관측으로 과거 FIFO 사건의 OS 원인을 확정하지 않는다.

## 미확정 사건의 처리안

| OPEN | 복원 가능한 사실 / 없는 정보 | 영향·이미 확인한 보호 | 재발 시 필수 기록 / 처리 제안 |
| --- | --- | --- | --- |
| OPEN-M4-TIM-01: 과거 FIFO | `1989477` Front/Rear slot281 release662ms/deadline666ms 미실행. 직전 Rear body1.117555ms/CPU1.107494ms, 다음 요청 wake662ms→실제 slot282 start664.151891ms. timer 만료/wakeup/switch/IRQ chain 없음 | 실제666.004077ms 검출·666.009677ms physical override. 정상 가용성 실패. 현재97afb35 FIFO24/24와 추가20/20에서 해당 주입 전 사건은 미재현 | 동일 source/binary, 실제 TID·timer/스케줄/IRQ, 요청 wake·job 시작/완료·deadline·보호 이벤트. Rear CPU burst만으로 다음2.15ms 지연의 원인을 확정할 수 없음. A에서는 차단, B에서는 원인 미확정 예외로 OPEN 유지·같은 profile 재발 시 수용 재검토 |
| OPEN-M4-TSAN-01: native CommandDelivery | `d7115ff` 정상 arm810.816152ms 뒤 fault915.290114ms, protection selection915.819030ms. token/source/deadline·구간별 transaction trace 없음. 별도 저장 trace는 후속 PASS | 원본 실패의 최종 모델 pressure1MPa·torque0는 보호 출력으로 바뀐 결과. 정확한 실제 override 시각은 없음. 현재 boundary108+wall9와 두 native40 묶음 PASS; pending 계약 수정은 별도 논리 재현으로 검증 | 최초 요청의 epoch/token/source/expiry, Central enqueue→Zone RX/dispatch→Leaf 적용→result, 실제 gate/모델/ACK. 기존 settlement 수정이나 TSan 부담이 옛 원인이라는 인과 증명 불가. A에서는 차단, B에서는 원래 OTHER/unpinned/guard-OFF 진단 사건을 OPEN 예외로 이관하고 재발 즉시 분석 |
| OPEN-M4-MWTSAN-01: DDS | 29개 경고를4개 수명/게시 계열로 구분. 실제 Writer scope/GC·mutex 수명은 정상6회 및 ASan UAF 대조3회로 좁힘. TSan Writer3회와 wrapper2회는 여전히 FAIL. bucket/remote/WHC 전체 안전성 미확정 | 현재 실제 DDS control adapter가 없으므로 Host component의 명령 경로에는 이 SDK가 참여하지 않음. 향후 원격 adapter에서는 SDK 경쟁/오류가 누락·만료·재시작으로 나타날 수 있음. 기존 in-process gate가 원격 안전성을 보장하지 않음 | 생성/게시/unlink/vtime/마지막 접근/free·callback 종료·mutex destroy를 객체 identity로 연결. A에서는 차단, B에서는 **M5 transport qualification gate**로 이관. 원인/수명 근거 또는 지원되는 수정이 준비되기 전 정규 제어 enable 금지 |

후속 반복은 같은 PASS를 더 모으는 목적이 아니라 새 가설·계측을 검증할 때만 한다.
과거 FIFO/native 실패 로그의 빠진 사건은 새 실행으로 복원할 수 없다.
기존2ms/4ms/expiry/envelope를 완화하거나 기록을 RESOLVED로 바꾸지 않는다.

## 승인 후 M5 첫 단위와 제어 gate 판정

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

SDK의 기존 미완료 조건을 승인에 따라 M5 정규 제어 연결 전 필수 gate로 관리한다.
통신·종료·재시작 계약 통과, 실제 경로의 경고별 수정 또는 구체적 계측 한계/수명 근거,
설명되지 않은 메모리·수명 경고 부재, 정확한 SDK build/config 연결을 모두 충족해야 한다.
충족 시 추가 승인 없이 Central↔Front 제어 adapter를 진행한다. 미충족 시 gate를 닫고 진단을 계속한다.

Host component 수용과 별개로 **학습자 REVIEW PENDING**, Jetson·전체 원격 배포·
32 requirement/29 system TC는 **NOT RUN**이다. 배치는 Host PC + Jetson 한 대 안의 여러
vECU를 유지한다. Jetson 일반 kernel/PREEMPT_RT 비교, NIC/IPC/SocketCAN·clock·CPU/RT
priority 실제 적용과 새 workload의 성능은 Target에서 검증한다. MBD/AUTOSAR 순서는
기존 ADR·로드맵을 유지한다.

## 승인 이후 실제 진행

[2026-10-21 qualification 결과](test-plan/evidence/m5_dds_qualification/README.md)는
42회23 PASS/19 FAIL이다. 실제 bucket/WHC/Proxy·lease 관측과 명시적 staged restart를
추가했지만 raw close timeout·20ms 전달 실패·미확정 TSan 경고가 남는다.
**B 한정 수용 유지 / M4 전체 NOT CLOSED / DDS control gate CLOSED**다.
정규 adapter는 미착수이며 Daybreak 인증 요구 확인 뒤 추가 조사는 보류했다.
학습자·Target·system 상태와 과거 OPEN은 승인 전후 모두 유지한다.

`c10688d` 이후 [환경·운용 후보 후속](test-plan/evidence/m5_dds_operating_profile/README.md)에서
실제 QoS/thread/status 관측, partial writer 삭제 뒤 reader 정지 결함 수정,
첫 heartbeat 전 DATA/100ms 재전송에 대한 양방향 transport 준비를 검사했다.
새 성공은 기존42회 실패나 full-RHC close/TSan OPEN을 닫지 않는다.
Host 한정 수용·M4 NOT CLOSED·DDS control gate CLOSED는 동일하다.
