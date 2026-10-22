# Project status

Updated: **2026-10-22**. **M3 — IN PROGRESS / M4 Host IO/FIFO COMPONENT LIMITED ACCEPTANCE / M5 SOME/IP HOST LIMITED ACCEPTANCE / M6 IN PROGRESS**다.

2026-10-22 최신 [M6 Simple Vehicle/MIL 첫 구현](test-plan/evidence/m6_simple_vehicle/README.md):
**actual 기반 차량 모델과 첫 종방향 MIL·선택형3-vECU 연결 검증 완료, M6 전체 종료 아님**.
기존 actuator 실제 torque/pressure/angle에서 vehicle speed/pose를 계산하고 wheel speed를
Rear Drive→CAN/P05→SOME/IP→Central validator로 반환한다. 물리 state는 ECU 재가입에도 유지한다.
실제 이동으로 드러난 NormalStop의 delayed pressure/terminal Hold 경계를 수정했다.
최종 C++13d1e87의 전체 Normal/ASan 각999/999,TSan 경계28/28,실제 SDK Normal3/3·
ASan1/1·TSan1/1,Python8+24를 확인했다. 개발 포함 SDK6/9 원본과 MIL 최초 FAIL은 보존한다.
실제 SDK는 low-speed acceleration fixture,30/20/0km/h 추종은 별도 Python MIL이다.
MIL plateau max0.049180/0.046337/0.005251km/h,overspeed1.2233%;M8 C++ speed controller는 미구현이다.
[ADR-0063](adr/ADR-0063-simple-vehicle-and-longitudinal-mil.md)/[모델 ICD](icd/simple_vehicle.md)를 따른다.
M6 부하·장시간·전체 EV scenario/M7 CARLA/M8 동등성·차량 SIL/Jetson은 NOT RUN이다.
기존 M5 Host 한정 수용·TSan OPEN/DDS CLOSED·M4 전체 NOT CLOSED는 유지한다.

아래 Rear 연결 기록은 M6 착수 전의 수용 범위와 당시 분모다.

2026-10-22 이전 [Rear 실제 통신 경계 후속](test-plan/evidence/m5_someip_rear_adapter/README.md):
**문서화한 Host Normal FIFO Central↔Front/Rear 기능 범위 한정 수용 — Rear 연결 완료**
([ADR-0062](adr/ADR-0062-someip-rear-host-adapter.md)). Central·Front·Rear 별도3프로세스,
Rear/Drive/BMS/Power 단일 소유권과 실제8참여자 ACK/RunLease/arm·Front 결과 뒤 Rear 배분을
SOME/IP에 연결했다. 원래 host10-v1·2ms/4ms·20ms envelope·source/expiry·큐8을 유지한다.
최종 소스a790032의 Normal FIFO 무부하2/2·기존 부하2/2·Rear 핵심 고장4/4·Front 대표2/2,
ASan/UBSan2/2, 전체 Normal/ASan각987/987이다. 정상4회의 세 Leaf 최소 여유는
Steering7.766637/Brake7.764243/Drive7.163085ms, 재가입 후 최소는 각각6.378692/6.376290/
5.576097ms다. 실제 NormalStop/HV-off 및 살아 있는 SDK stop/join을 확인했다.
**TSan은1/2: 재가입 PASS, normal32 batches 뒤 원래 허가 지원 부족/expiry로 보호하여
관측 구간 미완료 FAIL**. 메모리/UB/경합 경고0이며 wall-time은 승인된 Normal 성능 기준과
분리한다. 최종13/14·전체34/41 raw 결과와 OPEN-SOMEIP-REAR-01을 보존한다. TSan 전체
정상 구간 PASS나 무제한 Host 운용을 주장하지 않는다. CPU/부하/2540ms+실제 종료 tail의
Normal FIFO SIL 범위만 수용하며 M4 전체 NOT CLOSED, DDS CLOSED/기존 OPEN, Jetson·실제 IO·
M6·전체 시스템 미검증은 유지한다. M6 모델/센서 경계 설계는 다음 후보이며 구현하지 않았다.

이하 기존 Central↔Front 및 이전 검토는 당시 상태와 분모를 보존한다.

2026-10-22 이전 [실제 Leaf 갱신 수정](test-plan/evidence/m5_someip_refresh_delivery/README.md):
**host10-v1의 Host FIFO Central↔Front 제한 범위 수용 / Rear 연결 진행 가능**.
20ms 기본 profile은 보존하고 실제 Host allocation/VehicleRequest 갱신을10ms로 명시했다.
허가 source/expiry는 그대로이며 다음 release 뒤8ms 인계 여유도 검사한다.
동일 논리 재현은 수정 전 실제 Leaf expiry FAIL→새 profile 갱신 PASS(최소5.23ms 여유),
최종 Normal FIFO 무부하2/2·기존 부하2/2·핵심 보호/종료/재가입4/4,
ASan/UBSan·TSan 실제 SDK 각2/2, 전체 Normal/ASan 각983/983이다.
Normal 실제 Leaf 최소 갱신 여유13.56ms. 원래2ms/4ms guard·20ms envelope·입력 age·
8 ACK·RunLease·CAN/P05를 유지한다. OTHER 부하 timing은 진단 전용이며 sanitizer wall
성능과 메모리/경합 오류 판정은 분리한다. 과거 실패·분모·OPEN은 변경하지 않았다.
수용은 위 CPU/FIFO·기존 부하·2540ms 관측 Host functional SIL에 한하며,
Rear 구현·Jetson·전체 시스템은 NOT RUN, M4 전체 NOT CLOSED·DDS CLOSED는 유지한다.

이전 `b624243` 검토의 [Host FIFO 갱신/시작 순서 후속](test-plan/evidence/m5_someip_fifo_refresh/README.md)은
`45a3352`의 실제 만료/품질 검사와 `7fe4bbd`의 영속 Epoch 발급→native 감시 순서 수정을 검증했다.
최종 **Normal FIFO8/8**, ASan/UBSan·TSan 실제 SDK 경계 **각2/2**다. 공통 전체 회귀는
Normal **979/980**(기존 OTHER wall 주입 전 실패1), ASan **980/980**이며 원본을 유지한다.
새 SDK 전체25회23 PASS/2 FAIL과 최종12/12를 구분한다. 사용자 승인으로 **OTHER 부하 timing은
진단 전용**이고 이번 FIFO 한정 진행을 막지 않는다. 필수 조건은 실제8참여자 Host Central↔Front의
Normal FIFO 정상 운전·핵심 보호/종료/재가입, 실제 sanitizer 오류 없음이다.
다만 과거 정상 갱신 중단의 허가 expiry가 다음20ms release에69,603ns 부족한 분기는 확인했으나
수정하지 못했다. 준비 조건의 단순 삭제는 실제 원격 인계 전 expiry를 유발해 철회했다.
당시 **Host functional SIL 조건부 채택 / FIFO 수용 확대·Rear 연결 진행 보류**였다.
이 갱신 경로는 위 새 profile에서 별도 수정·검증했으며 당시 결과를 PASS로 고치지 않는다.
후속 PASS로 기존 OPEN을 닫지 않으며 M4 전체·Jetson·전체 시스템 수용으로 확대하지 않는다.

이전 [SOME/IP native 실행 감시 근거](test-plan/evidence/m5_someip_native_watch/README.md)는
기존2ms 실행 기회/4ms 감시를 실제 Central·Front owner와 지속 SIL 물리 프로세스에 연결했다.
원래 요청 회차의 완료를 기록하고, owner/monitor 정지에는 살아 있는 독립 감시·물리 override가
보호한다. 실제 RX8+추가1 거부·latch·FIFO 보존을 보강하고, 물리 보호 후 같은 Epoch의
nominal 출력 적용 오류와 감시 마지막 회차 오기록·runner 선행 실패 판정을 수정했다.
구현 `2dbc5e0`, 전체 Normal/ASan **978/978씩**, 관련 Python **48/48씩**(작업 트리·build 없는
fresh checkout), 기존 native 영향 **6/6**이다. 최종 동일 C++ 기능은 **Normal12/13·ASan13/13·
TSan10/13**, 새 통합 경로의 유한48회는 **31 PASS/17 FAIL**이며 sanitizer 경고는 없다.
Normal FIFO 정상 무부하·CPU1/2 부하7ms/10ms는 **각3/3** 통과했다. 이2540ms 관측 profile의
정상 운전 근거만 확보했으며 **전체 고장·복구 운용 수용 확대는 보류**한다. 일부 정상 운전에서
원래 명령 expiry에 따른 보호와 주입 전 실패가 남아 OPEN-SOMEIP-NATIVE-01/02로 관리한다.
SDK OTHER 스레드CPU4/5, ownerCPU1/2·physicalCPU3, monitorCPU0으로 분리했다. 실제 사용자
RT limit20/20·FIFO 우선순위11/18/19/20을 확인했으며 모든 스레드 FIFO 적용은 하지 않았다.
기존 동일 CPU TSan0/13·GDB 및 배치 비교 실패도 보존한다. 계측 결과는 Normal 성능과 별도다.
통제61ms 모델 지연은 energy.step 실패·원래 dt/input·보호·IO 상태 기록을 검증했지만
**OPEN-SOMEIP-HOST-01은 OPEN 유지**다. 당시 제안한 allocation/permission/Leaf 시간축
후속은 위 갱신 근거로 이행했다. 역사적 사건 전체의 원인을 확정한 것은 아니다.
기존 Host functional SIL 조건부 채택, M4 전체 NOT CLOSED·DDS historical OPEN/CLOSED,
Rear 네트워크·Jetson·실제 IO·전체 시스템 NOT RUN을 유지한다.

이전 `767d334`의 [SOME/IP Host Central↔Front adapter](test-plan/evidence/m5_someip_front_adapter/README.md)는
**Host functional SIL 경로에 한해 조건부 채택**했다([ADR-0061](adr/ADR-0061-someip-front-owner-adapter.md)).
실제 SessionCoordinator·RunLeaseIssuer·8개 참여자의 Release ACK·arm과 Central allocation→
Front owner→기존 CAN/P05·Leaf→실제 SIL Actual/health 반환을 IP 경계에 연결했다.
일반/권한 lane을 분리하고 포화8/8에서 독립 보호·SDK stop/join·새 Epoch 재시작,
살아있는 Central에서 Front 소실·8-role 재가입, Central 소실 시 Front 로컬 보호를 검사했다.
고정 최종 C++ cohort는 Normal15/15·ASan13/13·TSan12/13 raw이며 경합 경고0이다.
의도된 peer crash의 RunLease reset 분류를 보완한 동일 바이너리 재가입 회귀3/3 PASS;
원래 TSan exit1과 전체201 attempts의188 PASS/13 FAIL은 그대로 보존한다.
관련 계약 Normal/ASan 각각145/145, 새 checkout(build/ 없음) Python43/43 PASS.
기존 pilot은 별도 fixture 이력으로 유지하고 attempt-02 cohort 제외 메타데이터만 정합화했다.

남은 fixture는 trusted 시나리오 입력과 지속 SIL 물리·센서 IO다. Rear owner들은 Central에
로컬로 남는다. 당시 미완료였던 native2ms/4ms execution-watch 연결·Host 부하 시험은 위 후속에서 실행했으며,
전체 운용 수용은 보류다. 이전 physical-model 약61ms pause/실패 원인은 OPEN-SOMEIP-HOST-01이다.
따라서 일반 운용/실시간 채택, 실제 Host IO·Rear 네트워크·Jetson·전체 시스템 수용은 아니다.
기존 요청의 연결·qualification 결과와 현재 다음 단계는 위 최신 근거를 따른다. **DDS gate CLOSED·정규 DDS adapter 미착수와
기존 FAIL/OPEN은 유지**하며 SOME/IP 채택을 DDS 결함 해결로 기록하지 않는다.
[README](../README.md)는 프로젝트 소개와 실행 진입점이며, **이 문서가 현재 구현 상태·최신 시험 분모·다음 작업의 기준**이다. 과거 ADR/학습·품질 기록의 수치는 당시 범위로 유지한다.
단계별 일정은 [로드맵](roadmap.md), 날짜별 시험 이력·도구·로그 경로는 [품질 기록](quality_policy.md)에 둔다.

사용자는 `7bbafc7` 검토 뒤 [B안](m4_host_acceptance_review.md)을 명시적으로 승인했다.
검증된 Host native IO/FIFO component만 한정 수용하고 **M4 전체 NOT CLOSED**를 유지한다.
OTHER loaded 실패·과거 FIFO/native 실패·DDS 경고는 원본과 함께 OPEN 예외로 관리한다.
DDS 통신·종료·재시작 및 경고별 수명 검증은 **DDS 정규 제어 연결 전 필수 gate**다.
별도 SOME/IP 경로의 제한된 채택 범위는 ADR-0061을 따른다.
Ubuntu/CPU/FIFO 배치·2ms 실행 기회·4ms deadline·command expiry·20ms envelope는 불변이다.
학습자 REVIEW PENDING, Target/전체 시스템 NOT RUN은 그대로다.
`9136c1f`는 middleware result의 최상위/필수 필드/타입 검사를 추가했다.
추가14개 실제 runner-process 회귀를 포함해 runner 단계 Python **134/134 PASS**이며,
22개 focused 시험은 수정 전10 PASS/8 FAIL/4 ERROR→수정 후22 PASS다. 기존120개 이름/assertion을 유지했다.
원본 result JSON·구문 오류·process exit를 보존하고 예정36개를 모두 수집한다.

직전 [M5 DDS qualification 근거](test-plan/evidence/m5_dds_qualification/README.md)는
24+6+6+6회 **42 attempts /23 PASS·19 FAIL**다. 초기5회 build/setup 실패는 runtime NOT RUN으로
별도 보존했다. GDB 추가1회와 timeout-cleanup 경로를 재현하지 못한 추가1회도 별도 기록했다.
실제 bucket/WHC·Proxy/lease/mutex 생성·접근·quiescence·free 관측을 확장했고 Normal/ASan 수명
시험은 통과했지만 TSan 경고는 남는다. v6 raw restart는 세 빌드에서 close timeout,
v7의 명시적 송신 중지/drain→epoch43 재준비는 기능 통과·old42 거부, TSan은 FAIL이다.
계측을 줄인 ASan 정상 통신도20ms 전체 전달 조건을 놓친 실행이 있어 **DDS control gate CLOSED**다.
정규 adapter는 미착수다. bookkeeping3개 추가 후 최신 전체 Python **137/137 PASS**다.
사용자가 Daybreak 인증 요구를 확인한 뒤 추가 조사는 보류하고 완료한 코드·결과를 보존했다.
이는 M4 기술 조건 변경이나 이미 실행한 시험의 NOT RUN 재분류가 아니다.

`c10688d` 후속 [Host DDS 환경·운용 후보 점검](test-plan/evidence/m5_dds_operating_profile/README.md)은
설계 YAML과 실행 설정/실제 QoS·thread readback을 구분했다. CPU1/1·5ms/full 일반3회0 PASS,
minimal2/3, CPU1/2 minimal5ms와20ms 각각3/3이다. 첫 DATA/heartbeat 순서·100ms 재전송으로
초기17개가 만료된 경로를 확인했다. 실제 양방향 transport 준비 추가 뒤 같은 full/CPU1/5ms3/3
PASS지만 정규 session/arm이 아니다. Writer 삭제가 reader take까지 중단하던 진단 결함도
수정했고 삭제 뒤40개 추가 수신·reader rejection0을 확인했다. 원본42회23/19는 불변이다.
새45 attempts(수정 전1+비교/종료38+준비6)는 별도 보존한다. 후보의 종료/재시작·포화 close는
기능 통과했지만 과거 close timeout은 미재현/OPEN, TSan64 warning occurrences는 unresolved다.
준비 미송신의 실제 timeout/cleanup과 두 실제 child 강제 timeout 회귀를 확인했다.
관련 Python29/29, sanitizer expiry/actor 보호 component ASan·TSan 각각11/11 PASS;
전체973/native40/timing48 재실행 없음. **DDS control gate CLOSED / 정규 adapter 미착수** 유지.
이번 새 Daybreak 안내는 없었고 실패한 공식 API URL 조회는 중단했다. 접근 이력은 새 근거에 보존했다.

`658562e` 후속 [종료·TSan 검토](test-plan/evidence/m5_dds_shutdown_followup/README.md)는
build/ 없는 checkout에서 Python29개 중2개 시험의3 failure records를 재현했다.
두 runner의 잠금 부모 생성과 독립 fixture를 보완한 뒤 새 checkout·작업 트리 각각29/29 PASS다.
이는 mock SDK bookkeeping이며 새 DDS runtime0회다. 기존64회 경고를32개 stack 조합으로
연결했다.9회는 구체적 publication 계측 공백,55회는 실제 사용 SDK 경로 미확정이며
**64회 모두 FAIL 유지**다.1회는 Writer의 같은 bitfield 바이트에 대한 잠금 안 쓰기와
잠금 밖 읽기를 원본·소스·실제 binary로 좁혔다. full-RHC GDB 대기는 reader close→GC와
recv 재시도/awake 진행의 고리에 부합하지만 지원되는 수정은 미확정이다.
대응하는 승인 patch/release를 찾지 못해 새 SDK 비교는 NOT RUN, 문의는 초안만 작성했다.
제품 C++/SDK 변경·973/native40/timing48 재실행 없음. **DDS gate CLOSED / adapter 미착수**다.

앞선 `d3e7f6d` 사용자 고정 수집213425의
[OTHER1+FIFO10 OFF/ON11쌍](test-plan/evidence/m4_kernel_campaign/completed_213425/README.md)은
전부 **VALID**다. OTHER2 FAIL(OFF191/ON186 miss), FIFO20 PASS이며 수집·분석 exit1은
두 OTHER 실패를 반영한다. FIFO 주입 전 deadline 누락0건, 주입 뒤 의도된 Monitor 지연은
원래 deadline 후3.170–5.059µs 검출·이후1.008–3.484µs physical override로 대응했다.
사용자/capabilities0/RT20·FIFO priority/CPU·marker/cleanup·유실0을 실제 확인했다.
버퍼 보완은 이번11쌍에서 검증됐지만 과거 FIFO 원인은 미재현·미확정이다.
앞선212418의 CPU9 유실/INVALID·FIFO 미실행 기록은 보존한다. Python **112/112 PASS**,
이번 C++·sanitizer·48회 timing 재실행은 없다. 이전 native Normal20+TSan20 PASS도 유지한다.
[SDK 후속](test-plan/evidence/m4_sdk_followup/README.md)에서 DDS 공식 TSan4 FAIL을 재현했고,
Rust 도구 설치·nested build-std 보완 후 Zenoh matched partial4 FAIL/full4 PASS를 확인했다.
이 결과로 과거 native/FIFO 원인이나 M4 종료를 확정하지 않는다.

`c52445a` 후속 [DDS 실제 Writer 수명 검증](test-plan/evidence/m4_dds_lifetime/README.md)에서는
SDK11.0.1의 실제 생성→lookup→unlink→quiescence→mutex/free를 분리했다.
정상3·ASan/UBSan3 PASS, TSan3 FAIL(각2경고), 의도적 ASan UAF3 검출이다.
두 프로세스 wrapper도 ASan 정상/overflow2 PASS, TSan2 FAIL을 보존한다.
Writer 한 경로의 계측 공백 근거를 확보했지만 bucket/proxy/WHC 전체 안전성은 OPEN이다.
Middleware runner의 FAIL/경고 종료코드0 결함은 `1677f85`로 수정했다.
신규8개는 수정 전2 PASS/5 FAIL/1 ERROR→8 PASS, 당시 전체 Python **120/120 PASS**다.
초기 lifetime harness의12개 setup 실패도 별도 보존했다. 제품 코드·SDK 알고리즘·버전 변경은 없다.
기존6개 runtime/test 바이너리 SHA가 동일하여 C++973·TSan108+9·timing48 근거를 원래 identity로
재사용하고 새 실행으로 세지 않는다. [Host IO/FIFO 한정 수용안](m4_host_acceptance_review.md)은
당시 **PROPOSED**였고 이번 사용자 승인으로 위 한정 범위에 적용했다. 전체 종료는 NO-GO이며 **M4 NOT CLOSED**다.

## Milestone 현황

| 단계 | 상태 | 남은 항목 |
| --- | --- | --- |
| M0 — 계약·아키텍처 | BASELINED | [종료 검토](m0_baseline.md)는 문서 계약의 검토 결과 |
| M1 — DBC·vCAN | TECHNICAL CHECKS PASS / REVIEW PENDING | Wire baseline 채택, 학습자 설명·직접 재현 |
| M2 — Actuator·EV 모델 | TECHNICAL CHECKS PASS / REVIEW PENDING | 학습자 직접 재현·수용 검토 |
| M3 — Timing·실행 | IN PROGRESS / HOST REVIEW COMPLETE | [실행 기준 선택](m3_acceptance_review.md); 일반 sanitizer 타이밍 실패 2건·학습자 수용 및 Target/E2E 후속 |
| M4 — Central/Zone | HOST NATIVE IO/FIFO COMPONENT LIMITED ACCEPTANCE / WHOLE NOT CLOSED | Central·scoped admission·CAN gateway/보호·Rear power/permission/limits·양 Zone 초기 구동·정상 정지/HV 종료 연결; 실제 Zone health·독립 status/상실 연결; 단일 coordinator·8-role session INIT/rejoin 위에9개 정상 owner runtime 연결·정상/고장/종료/복구 검사; 공통 owner/방향별 고장·joined 재가입·M3 독립 guard 연결 검사;release 위상 보완/책임 분리·owner-wire/remote Leaf credit·실제 actor 보호 검사; timing·native/SDK TSan 예외 OPEN, [종료 검토](m4_exit_review.md) 진행 |
| M5 — 통신 | DDS CONTROL GATE CLOSED / SOME/IP HOST FIFO CENTRAL↔FRONT LIMITED ACCEPTANCE | host10-v1 실제8-role·native 감시·기존 부하 정상 갱신·핵심 보호/종료/재가입 수용; Rear 연결 진행 가능. DDS FAIL/OPEN·Rear/Jetson/system NOT RUN 유지 |
| M6 | IN PROGRESS | Simple Vehicle/첫 Python MIL·3-vECU quiet 검증; 전체 EV/부하·sensor 경계 후속 |
| M7–M13 | PLANNED | CARLA → control·diagnostics·AI·보드 비교 |

[MBD 방법](engineering_plan.md#model-based-design-path)은 계획에 채택했다. 첫 대상은 Central 종방향 제어이며
M6 모델/MIL→M8 C++ 동등성/차량 SIL 순서다. TBD-16의 첫 모델 도구는 Python으로 선택해 M6 MIL을 실행했다. 자동 생성과 M8 동등성은 NOT RUN이다.

## 구현·시험한 범위

현재 구현은 **Host functional SIL component**다. [실행 경계 정리](learning/m2_execution_boundaries.md)로 ECU 판단과 물리 실행 연결을 분리했다. 모델의 설정값은 첫 시험 fixture이며 실차 calibration은 아니다.

| 영역 | 구현한 내용 | 상세 안내 |
| --- | --- | --- |
| CAN FD 통신 | Actuator Command/Actual 6개 + EV/BMS 6개 frame, DBC·codec·AUTOSAR R25-11 E2E Profile 5·receiver·SocketCAN | [Actuator frame](learning/m1_steering_frame_codec.md), [EV/BMS](learning/m1_bms_codec.md) |
| 세션·수신 연속성 | 영속 Epoch 발급, bounded queue, overflow/restart, 이전 Epoch 거부와 P05 state 오염 방지 | [Session/queue](learning/m1_session_queue.md) |
| Steering | Delay/rate/angle 제한, source-loss hold, 별도 angle sensor와 정상 응답 범위·residual/dwell 고장 검출 | [응답 모델](learning/m2_steering_model.md), [고장 검출](learning/m2_steering_fault_monitor.md) |
| Brake | 압력 가압/감압·지연·포화, 별도 pressure sensor와 stuck/slow 응답 검출, 보호 floor 요청·관측 구분 | [압력 모델](learning/m2_brake_model.md), [고장 검출](learning/m2_brake_fault_monitor.md) |
| Drive | Signed torque/zero ramp, BMS·trusted permission·local HV/speed gate와 capability; 비동기 취득 시각 보존·Actual socket TX→독립 RX | [응답 모델](learning/m2_drive_model.md), [필수 gate](learning/m2_drive_gate.md), [Actual CAN](learning/m3_drive_feedback.md) |
| Battery·BMS | 실제 DC 기반 단일 energy/SOC owner, 전압·전류·온도·셀 극값 관측, 방향별 derating·보호 dwell/latch | [Battery](learning/m2_battery_model.md), [BMS](learning/m2_bms_controller.md) |
| Power lifecycle | 실제 접점·RC bus 기반 precharge/READY, 전류 확인·접점 open·잔류 전압 방전, shutdown blocked | [전원 상태 흐름](learning/m2_power_lifecycle.md) |
| Central 전원·허가 | 독립 입력 health/정상 준비, trusted lifecycle root·요청 ACK·expiry, actual OFF/READY와 FAIL_SAFE latch; 전원 요청·DrivePermission 산출 | [준비 조건](learning/m4_normal_drive_readiness.md), [상태 owner](learning/m4_vehicle_management.md) |
| 세션 실행 경계 | 영속 grant→8-role Prepare/INIT/Release·정확한 ACK/원래 deadline·global gate, bounded SPSC·부분 INIT 실패와 명시적 재가입; 물리 상태 보존 | [Session owner 연결](learning/m4_session_bootstrap.md) |
| 정상 비동기 실행 | Central·Front/Rear·다섯 Leaf·Physical 단독 소유, 방향별 SPSC·global epoch gate·원래 grant parent/expiry, 실제 BMS/HV/sensor→arm·TX result·status/Actual·보호 ACK·재가입 | [Owner 통합·재현](learning/m4_async_owners.md), [대표 근거](test-plan/evidence/m4_async/README.md) |
| Central 단일 실행 | VM·allocation·NormalStop을 private로 소유, 원래 root/issuer 인계·10/20 ms 실행 순서·부분 실패 양 Zone 보호·참여자 INIT preflight | [Coordinator 연결](learning/m4_vehicle_coordinator.md) |
| Central 배분 | Acceleration/curvature/braking→angle·signed torque·pressure, 권한/BMS/capability gate·actual 잔여 회생 보정·저속 hold/release·deficit/excess와 보호 요청 | [첫 배분 component](learning/m4_control_allocation.md) |
| Zone 명령 수용 | Front atomic Steering/Brake·Rear Drive, 독립 trusted root 대조·scope/range/mode/age/expiry·연속성 latch·명시적 arm/INIT | [명령 수용 component](learning/m4_zone_command_admission.md) |
| Zone 전달·로컬 보호 | Bounded FIFO·최신 명령 선택·각 CAN write 전후 expiry guard·partial/failure latch; 별도 trusted port로 실제 Leaf의 Hold/Protect/Zero 선택 | [Gateway·보호 연결](learning/m4_zone_gateway.md) |
| Rear 전원·시동 연결 | 독립 lifecycle root·실제 송신 Enable ACK·limits/permission/status 감시, Drive NonDriving→trusted arm·정차/derating envelope, Drive/Power 로컬 보호 | [전원·초기 구동](learning/m4_rear_power_startup.md) |
| Front 초기 구동 연결 | 센서/주기 감시를 유지하는 NonDriving, 두 Leaf·gateway의 동일 Epoch/fresh sensor preflight·arm, 실패 시 둘 다 보호 | [Front/양 Zone 시동](learning/m4_front_startup.md) |
| 정상 정지·HV 종료 | Stop intent/자식 issuer·새 actual dwell·terminal lease·Hold/Zero 인계→Inhibit/Shutdown→actual OFF ACK, 부분 실패/권한 상실 보호 | [정상 종료 연결](learning/m4_normal_stop.md) |
| Zone 입력·상태 감시 | 실제 gateway·담당 Leaf 원천 health→Ready/Active/Terminal/FailSafe, Central의 Zone별 status ingress·상실 latch·새 INIT 경계 | [상태 감시 연결](learning/m4_zone_feedback_health.md) |
| 에너지·회로 연결 | Actual torque/speed→motor DC·손실→Battery SOC, capacitor·경로 손실과 atomic commit; 정상/용착/센서 상실/지속 부하 | [이상적 HV 연결](learning/m2_drive_energy.md), [실제 회로 연결](learning/m2_ev_power_circuit.md) |
| 주기 실행·감시 | Steering 및 Brake/Drive/Power 10 ms·BMS 20 ms, 실제 RX·독립 감시, owner별 CPU 배치·전체 body/CPU/sleep·RX 시간 대조·4 ms 교차 guard와 수신 이중 감시 | [다중 주기](learning/m3_multirate_runtime.md), [CPU 부하](learning/m3_cpu_placement.md), [전체 cycle](learning/m3_owner_cycles.md) |

Receiver는 유효 0과 unknown, 원천 source/dependency age, 원래 요청에 묶인 expiry를 구분한다.
중계·재발행으로 오래된 측정이나 제한값을 fresh하게 만들지 않는다.
Isolated DriveActuator의 speed/capability는 unavailable이며, 필수 EV gate는 별도 DriveController가 담당한다.
Steering TrackingError와 Brake ResponseError는 정상 응답 계약 위반을 검출한다. 단일 센서로 기계 원인을 고유하게 진단하지 않는다.

## 검증 결과와 한계

| 검사 | 결과 / 범위 |
| --- | --- |
| 전체 C++ | `97afb35` Normal·ASan/UBSan **각각973/973 PASS**; unit800 / integration.logical164 / runtime.wall9. 검토 기준966개 이름 유지 + pending/expiry7개. 기존19.8ms 재현의 기대 결과만 [ADR-0059](adr/ADR-0059-pending-command-allocation-settlement.md)에 따라 변경하고 수정 전 결과 보존. Python 당시 **97/97 PASS**(기존95+marker 실패 보존/버퍼 제한2); C++ 실행 코드는97afb35 그대로 |
| M4 고장·복구 component | Central/두 Zone/다섯 Leaf 실행 정지·8방향 loss·delay/원래 context expiry·FIFO overflow/join·새 Epoch 복구·Prepare/INIT/Release/arm/stop ACK 경계. `97afb35` fault artifact33개씩 두 빌드 PASS, durable CLI 재가입 양 빌드 PASS. 과거37개 CSV byte 동일성 검사는 당시 source 이력이며 새 wall timing 동등성 주장이 아님 |
| M4 물리 반응 | 원본 CSV 사후 감사: 정상 운전 뒤 고장56개 표본에서 angle hold·pressure floor·torque zero·접점 open 확인; never-active8개는 해당 반응 N/A. 짧은 run의 잔류 bus 전압과 실제 OFF 확인을 구분. SOC/energy/model 연속성 PASS |
| M4 분리 vCAN | 이전 Normal·sanitizer 각각 **5/5 PASS 이력**. 실제 CAN command·metadata/원래 deadline·terminal 뒤 거부. 이번 계약 수정 후 vCAN 재실행은 NOT RUN; 실제 owner→codec→remote Leaf는 아래 논리 통합으로 검사 |
| 원본 M4→M3 cohort (`12fc4a5`) | 사전 고정48회 ×2.54s, CPU0/1·OTHER/FIFO·부하/고장·3회 반복, 실제 설정/부하 control48/48 PASS. **41 PASS / 7 FAIL / 0 BLOCKED**. OTHER loaded normal0/6, FIFO normal12/12, intentional fault23/24 PASS.7개 실패를 모두 유지하며 timing 수용 미완료 |
| 위상 수정/분리 후 native cohort | `603fe24`와`77d411c` **각각48회:42 PASS/6 FAIL/0 BLOCKED**, FIFO각24/24(Drive fault6/6 포함), OTHER loaded normal각0/6. 원본41/7과 별개이며 시한/분모 불변. 최초 FIFO extra wake kernel 원인 미확정, OPEN-M4-TIM-01 유지 |
| 원격 계약·실제 Leaf | 이전 Epoch 거절 응답의 원래 identity 보존, 최초 sent 기준20ms/원래 expiry 중 이른 envelope, issuer/Epoch/token ACK8개씩 불변 보관. 실제 Central·두 Zone→codec→다섯 private-gate Leaf의 INIT/arm/정상 적용/Actual·Power/permission·Stop/HV OFF·지연 거부 PASS. 전체 원격 process 배포 아님 |
| 최신 native TSan | `97afb35` 변경 경계 **108/108**, runtime.wall **9/9 PASS**, 경합 경고0. 전체973개 TSan은 NOT RUN. 최초부터 full trace 고정 normal20+TSan20회 **40/40 PASS**, 수정 runner exit0. 과거 `d7115ff`8/9의 CommandDelivery 실패는 원인 미확정·**OPEN-M4-TSAN-01 유지** |
| 명령 전달 계약·수정 | 한 batch가 pending이면 다음 due 배분을 보류하고 original deadline·allocator expiry/30ms gap·Zone/Leaf authority 감시는 계속한다. 제때 완료되면 fresh 입력으로 기존20ms release grid 재개. Rear19.8ms는1025.2ms의 조기 보호 대신1025.4ms exact envelope expiry에서 보호; 양 Zone12ms는 기존 Rear 적용 명령의1011.000001ms expiry가 먼저 보호. 일시 지연 정상 재개·지속 지연 만료·Stop handoff 검사. 실제 native 과거 원인으로 확정하지 않음 |
| 계약 수정 후 timing (`1989477`) | 같은48회 프로토콜 **41 PASS/7 FAIL/0 BLOCKED**; 설정/부하/grid control48/48. OTHER loaded normal6 FAIL + FIFO monitor-overrun 조건1 FAIL. **FIFO23/24**: 예정 주입1.2s 이전 Front/Rear slot281(662ms release/666ms deadline) 누락,666.004077ms 검출·666.009677ms 물리 override. kernel 원인 미확정, 이전 commit timing으로 대체하지 않음 |
| 최신 settlement 후 timing (`97afb35`) | 동일48회 **42 PASS/6 FAIL/0 BLOCKED**; 설정·부하·release grid·buffer control48/48. OTHER loaded normal6 FAIL, FIFO24/24·intentional fault24/24 PASS. 이전 FIFO 누락 원인은 여전히 미확정이며 이번 미재현으로 닫지 않음. 원래 deadline 불변·Host timing 수용 PENDING |
| M4 kernel 관측 | compact-v2 사용자 실행3쌍/6 workload 모두 FAIL로 보존. 두 쌍은 end marker EBADF,185513쌍은 OFF243/ON159 miss·729726 event·유실0·**VALID**. 최초 CPU1 조향 사례: timer hard-expiry 초과3.714µs, wake→CPU2.856ms, body1.125µs. CPU 대기 중 최신 slot9로 넘어가 slot8 미완료, 원래 deadline 후65.184µs 검출·이후4.895µs physical override. 이 OTHER 관측의 지연 위치 확인이며 FIFO 원인/전체 수용과 구분. `eecc1d7` 후속212418은 CPU9 유실로 INVALID였다. 보완 후213425의11쌍 모두 VALID·FIFO20 PASS·주입 전 miss0, user20/20·marker/정리·유실0을 확인했다. OTHER191/186 miss는 FAIL로 유지하며 과거 FIFO 원인은 미재현·OPEN. [최신 고정 수집](test-plan/evidence/m4_kernel_campaign/completed_213425/README.md). [근거·CSV·그림](test-plan/evidence/m4_kernel_valid/README.md) |
| 통신 후보 | 이전 v1 30/36·v2 36/36, wrapper ASan4/4·TSan4 FAIL·SDK 재계측 DDS2 FAIL 유지. 새 DDS 공식 `SANITIZER=thread`4 FAIL, helper vendor3 경고/C11 control3 clean/의도적 race3 검출. 후속 실제 Writer 수명 시험은 normal3/ASan3 PASS·TSan3 FAIL이며 한 경로의 GC 계측 공백 근거다. bucket/proxy/WHC 전체 안전성은 미확정. wrapper ASan2 PASS/TSan2 FAIL, runner 오류 종료 수정·Python120 PASS. [새 수명/판정 근거](test-plan/evidence/m4_dds_lifetime/README.md). Zenoh Rust1.97.1·nightly/std 확보, TCP baseline4/full TSan4 PASS; 동일 nightly·probe·runtime matched partial4 FAIL/full4 PASS. 계측 공백의 재현 근거이며 과거 배포 binary/전체 feature 수용은 별도. [원본/재현](test-plan/evidence/m4_sdk_followup/README.md), **OPEN-M4-MWTSAN-01** |
| M5 DDS qualification | [새42회·두 추가 진단·원본·packet/object CSV](test-plan/evidence/m5_dds_qualification/README.md):23 PASS/19 FAIL. 실제 bucket/WHC/proxy·lease 수명 관측과 staged restart를 추가했지만 full-RHC close·20ms 전달·미확정 TSan 경고가 남아 정규 제어 gate CLOSED. 제품 source/SDK pin·기존2ms/4ms/envelope 불변. 최신 Python137 PASS. 새 production timing/Target/system NOT RUN |
| 독립 감시·실제 적용 | 기존2ms 기회·4ms 완료 guard 불변. `97afb35`의 intentional fault24/24 PASS: 원래 deadline→검출0.003282–0.084379ms·검출→물리 override0.000936–0.986748ms. 정상6 FAIL에서 보호가 동작해도 timing PASS로 합치지 않음; 자기 body/논리 clock과 구분 |
| 추적성·공유 근거 | [함수→실제 GTest→판정·결과93개](test-plan/evidence/m4_settlement/final/component_results.csv), [수정 전후·source·환경·재현·정상/고장/복구 CSV/그래프·원본 로그](test-plan/evidence/m4_settlement/README.md). 이전966개와41/7은 [계약 검토](test-plan/evidence/m4_contract_review/README.md),948개·872개는 당시 이력으로 유지 |
| M3 수용 검토 | Host IO 동반/FIFO 기준 선택, 원본 96회 재분석·판정 동일. 전체 timing 수용은 PENDING |
| 최신 Build·정적 분석 | `97afb35` Debug normal/ASan·UBSan/TSan 빌드 PASS. 변경 production4개 clang-analyzer·cppcheck PASS. 이번 Release BUILD_TESTING=OFF는 NOT RUN; 이전 PASS와 enum registry 경고 기록 보존 |
| 이전 Build·정적 분석 (`12fc4a5`) | Debug 두 빌드·Release BUILD_TESTING=OFF PASS. Clang-tidy10개·production8개 cppcheck; 새 analyzer 오류 없음, variant/noexcept·인자 순서 경고를 근거와 함께 보존. TSan 기본 ASLR 매핑 실패; process-local `setarch -R`에서 native7/7 PASS·경합 경고0. 전체 TSan/RTOS/Target 실행 결과로 확대하지 않음 |
| Native 일반/FIFO 비교 | 같은 CPU map·workload·시한으로 4조건×2 trace×3회 **24/24 PASS**, 설정·부하 control 모두 PASS |
| Native 고장 회귀 | Normal OTHER/FIFO 각각 17/17, sanitizer OTHER 15/17·FIFO 17/17: **66/68 PASS**, 일반 sanitizer의 owner skip 두 실패 보존 |
| 이전 RTOS 파일럿 | 기존 12회 이력과 직전 4조건 **4/4 PASS**; 새 timer 비교와 별도 cohort |
| Hosted timer 비교 | 기능 **48/48 PASS**. 추가 Host timing은 absolute **24/24**, relative **0/24 PASS**; 대조군 실패 보존 |
| 후속 native FIFO 회귀 | 17조건×3회, normal/sanitizer 각각 **51/51 PASS**; 기존 OTHER 실패 2건 유지 |
| 후속 대기 진단 | Control **12/12 PASS**. Quiet 두 정책 각각 3/3, IO 부하 OTHER 0/3·FIFO 3/3 timing PASS; intrusive 진단 |
| Timer 정지·원본 호환 | ViPer 35.133 ms 정지의 누락 3개/정상 FAIL 확인; 나머지 3조건과 upstream 기능 4/4 확인, 48회 비교와 별도 |
| 이전 Linux 실행 회귀 | Multirate 17조건+Steering 4조건 normal/sanitizer **42/42 PASS 이력 유지** |
| 실행 대기 진단 | 무부하 3회·감시 CPU 부하 3회 수집; control **6/6 PASS**. 원래 정상 timing 계약은 각각 **2/3·0/3 PASS** |
| Wire·전체 시스템 | 기존 vCAN 97개 normal/sanitizer 각각 재통과 + gateway/startup 5개씩 PASS. DBC 12 frame/36 payload 이력 유지. 32개 requirement/29개 system TC **NOT RUN** |

[RTOS 파일럿](learning/m3_rtos_pilot.md)은 기존 Steering ECU와 CAN을 유지하고 실제 OS Task/Event/Alarm/Resource를 연결한다.
별도 Linux plant process가 물리·센서 취득·Actual 수신을 맡는다. OIL 2.5 OSEK 기능 시험이며 R25-11 Classic stack 적합성,
ARXML/RTE/BSW 생성·ARM64 Jetson 배포는 NOT RUN이다. 기존 Linux 배포 계획과 2 ms/4 ms guard·RX 3 ms 기준은 유지한다.

최초 Trampoline POSIX의 가상 tick은 relative sleep 기반이었다. 첫 파일럿 12 runs의 첫 release 기준 wall drift는
약 **23.8–30.6 ms / 1.6 s**였다. 기능 PASS를 정시 실행이나 차량 전체 timing 충족으로 확대하지 않는다.
다음 hosted OS 12 runs에서도 약 **24.3–28.8 ms / 1.6 s**의 drift를 관측했다. 이 당시 Linux scheduling은 SCHED_OTHER였다.
[ARM64 빌드·RT 사전 점검](adr/ADR-0041-arm64-rtos-build-and-host-preflight.md)을 추가했다.
ARM64는 세 ELF의 CPU·loader/library ABI를 기록한 교차 빌드 결과이며 Jetson 실행 결과가 아니다.
Host는 PREEMPT_DYNAMIC이다. 관리자 설정 후 새 PAM 실행 세션의 RT priority limit **20/20**과
FIFO priority **1·20 AVAILABLE / 21 EPERM**을 확인했다. 기존 IDE 세션의 limit 0은 유지되지만 같은 사용자로
새 실행 세션을 만들면 시험할 수 있다. [실행 방법](learning/m3_rtos_pilot.md#권한-설정-후-기존-ide-세션에서-실행하기)을 참고한다.
현재 agent의 비대화형 sudo는 제한되지만 사용자 터미널의 고정 sudo kernel 수집은 실제 완료했다. [Native FIFO 실행](learning/m3_native_fifo.md)에서 owner별 실제 priority와
startup gate·실패 취소·호출 thread 복원을 연결했다. 추가 부하의 Drive release→완료 p99는 full trace에서
일반 **1.947 ms → FIFO 0.065 ms**, minimal에서 **2.450 ms → 0.073 ms**였다. 모든 작업의 지연 개선이나 WCET 보장은 아니다.
Sanitizer 일반 실행 2회는 예상하지 않은 owner skip을 동반해 실패했다. 같은 cohort에서 FIFO 고장 회귀는 모두 PASS다.
직전 실행은 총 **94/96 PASS**이며 실패를 제거하거나 기존 시한을 완화하지 않았다. PREEMPT_RT kernel·Target timing은 후속이다.

별도 observer가 기존 native multirate thread의 `/proc` 누적 카운터를 읽었다. 6회에서 monitor skip **486개**가 있었고,
이를 덮는 모든 관측 구간에서 runqueue 대기 증가를 확인했다. 무부하의 한 구간에서는 요청 wake 지연 약 3.565 ms와
대기 누적 증가 약 3.510 ms가 기록됐다. 앞뒤 sample 여유 약 2.494 ms가 포함되므로 개별 wakeup의 정확한 분해는 아니다.
경쟁 process/IRQ/VM 원인은 아직 특정하지 않았다. Perf(paranoid=4)·tracefs 권한이 막힌 상태를 그대로 기록했다.
이 observer는 추가 부하를 주는 진단 도구이며 기존 배치 성능 표본과 합치지 않는다.

앞선 schema 5 배치 시리즈 124 runs의 119 PASS/5 FAIL은 [품질 이력](quality_policy.md)에 보존했다.
IO 동반 map(ECU CPU B, RX/monitor/plant CPU A)과 owner별 FIFO를 다음 Host 통합의 기준으로 선택했다.
별도 observer 진단은 monitor를 CPU 2로 옮긴 실험 map이며 이전 5개 실패의 원인을 소급 확정하는 자료가 아니다.
M1/M2 학습자 수용·전체 M3 수용은 PENDING이다.

[M3 수용 검토](m3_acceptance_review.md)에서 계약·분모·실패·물리 적용을 대조했다.
Pooled guarded 주기 통계에 run 사이 대기 시간이 섞인 오류를 수정했고 Python 60개가 통과했다.
원본 96회를 재분석해 해당 16개 분포만 교정했고 개별 run 판정·Drive/RX 지연·miss/skip은 동일했다.
원본 로그를 보존했으며 새 workload 실행은 0회다. 기본 실행 정책은 기존 상속 방식이며 FIFO는 CLI로 명시한다.

후속 [ADR-0043](adr/ADR-0043-hosted-monotonic-timer-and-placement.md)에서 opt-in RTOS build의 timer 기본을
절대 monotonic timerfd로 바꿨다. 선택한 Host RTOS/FIFO profile의 normal drift는 3회 모두 절댓값 0.001 ms 미만,
원래 timer phase→Control 완료 max는 0.277 ms였다. 상대 타이머 대조군은 FIFO에서도 15–17 ms drift가 남았다.
OS Task/CAN·native 시한은 유지하고, 새 추가 Host timing 5 ms 판정과 source/실제 CPU·policy를 대조했다.
개발 probe의 12-tick 정지가 120 ms보다 짧아지는 문제는 13 ticks로 수정했고 최소 wall 120 ms 검사는 유지했다.
원래 native sanitizer 두 실패의 정확한 커널 원인과 전체 M3 수용은 계속 PENDING이다.

## 다음 작업

1. **Rear 연결 후속:** [host10-v1 근거](test-plan/evidence/m5_someip_refresh_delivery/README.md)로 Host FIFO Central↔Front를 한정 수용했다. 다음은 현재 Central 내부의 Rear/Drive/BMS/Power 경계를 분리하되 실제8 ACK·단일 소유권·원래 허가/명령 시한·독립 보호를 유지하는 구현이다. 이번 작업에는 포함하지 않았다. DDS는 사용하지 않는 별도 경로이며 full-RHC 종료·20ms 전달·TSan FAIL/OPEN과 CLOSED gate를 유지한다. 과거 Daybreak 제한 작업을 재시도하지 않는다. DDS 자체를 정규 연결할 경우에만 해당 통신/종료/경고 gate를 충족해야 한다. M4 전체 종료와 Jetson/system 수용은 별도다.
2. **M3 타이밍 예외 해소:** OPEN-M3-01/02의 원본 실패를 유지하고 수집한 VALID kernel trace의 timer→wakeup→switch 근거를 재사용한다. 과거 FIFO 실패 당시 chain은 없어 인과관계가 미확정이다. 재발 시 원래 identity/deadline과 kernel chain을 함께 확보하며 가설 없는 반복은 하지 않는다. PREEMPT_RT 비교는 Target 후속 실험이며 M4 준비가 M3 전체 수용을 뜻하지 않는다. 학습자 직접 재현·설명도 남아 있다.
3. **ARM64 배포 준비:** Host PC + Jetson 한 대 내부 여러 vECU 배치를 유지한다. Jetson 일반 커널/PREEMPT_RT 동일 workload 비교는 Target 성능 검증 PLANNED / NOT RUN이다. 이번 커널 교체·MCU 이식은 없다.  보드 OS/BSP·ABI/stack/IPC·SocketCAN과 실제 실행을 확인한 뒤 다른 Leaf OS 확장을 검토한다. Target 검증은 배포 단계, RTE/BSW는 별도 pilot과 연결한다.
4. **MBD 준비·후속 pilot:** 현재 M4 통합을 진행하고 M5 통신 경계를 준비하면서 제어 interface·도구/모델 검토를 병행한다. M6 Simple Vehicle에서 종방향 모델/MIL을 만들고 M8에서 C++ 동등성과 차량 SIL을 검증한다. [채택 범위](adr/ADR-0052-model-based-design-development-path.md)는 방법/계획이며 구현·Simulink/자동 생성 도입 완료가 아니다.

## 후속 통합 범위

Central의 단일 vehicle management/allocation/session/feedback bridge와 Front/Rear 독립 연결은
[채택한 아키텍처](adr/ADR-0021-central-coordination-and-parallel-zones.md)다.
Front는 Steering/Brake, Rear는 Drive/BMS를 담당하며 feedback도 담당 Zone→Central→Host를 거친다.
준비 조건·전원/허가·첫 배분 library를 구현하고 PowerController·RC/접점·torque/pressure 응답 모델과 component 시험했다.
Rear 전원/허가/limits·Front/Rear NonDriving→arm과 NormalStop/terminal handoff→HV 종료도 실제 controller·RC/angle/pressure/torque component와 독립 Actual receiver에 연결했다. 실제 Zone health/독립 status receiver도 연결했다. 단일 coordinator와8-role 세션 준비/INIT/rejoin 뒤 정상9-owner 비동기 경로를 구현했다. 새 M4 경로는 실제 BMS/전원·명령·Actual을 사용한다. Remote INIT/lease wire와 Leaf component는 검사했고, 실제 controller process partition·DDS/Host bridge는 M5 후속이며 이전 EV demo/runtime의 request/grant·relay는 개별 모델 fixture로 유지한다.

기존 통합 EV 예제/배분 응답의 speed는 고정20 rad/s, 첫 시동은0 rad/s, 정상 종료는 외부20→0 script다. 차량 관성·타이어·차량 제동/배분 통합·CARLA closed-loop는 M4/M6/M7,
Owner별 배치와 native FIFO 우선순위는 Host에서 비교했다. Target timing과 DTC 통합(M9), Classical control·AI·Target 배포는 후속 단계다.
Leaf는 [Classic 개발 체계](adr/ADR-0022-leaf-classic-development-methodology.md)를 따르는 방향을 채택했고,
실제 OS/RTE/BSW stack·toolchain은 pilot에서 검토한다.

설계 범위의 기준은 [RG-01 회생·마찰 배분](icd/regenerative_braking_design.md),
[EV-01 Battery/BMS·전원](icd/ev_power_bms_design.md), [개발·학습 계획](engineering_plan.md)이다.
