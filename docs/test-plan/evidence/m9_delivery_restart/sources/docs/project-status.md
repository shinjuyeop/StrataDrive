# 프로젝트 상태

정리 기준·최신 검증: **2026-11-03**.
이 문서가 현재 구현·수용 범위와 다음 작업의 기준이다. 실행 중인 미기록 변경은 완료로 세지 않는다.

## 단계별 현재 판정

| 단계 | 판정 | 근거 |
| --- | --- | --- |
| M0 | 요구·구조 baseline 확정 | [M0 검토](archive/milestone-reviews.md#m0) |
| M1–M2 | 통신·actuator/EV component 기술 검사 완료; 학습자 review 별도 | [M2 검토](archive/milestone-reviews.md#m2) |
| M3 | Host FIFO 기준 사용; 과거 timing 예외·전체 종료 OPEN | [M3 검토](archive/milestone-reviews.md#m3) |
| M4 | Host IO/FIFO component 한정 수용; 전체 NOT CLOSED | [Host 수용](archive/milestone-reviews.md#m4-host) · [종료 검토](archive/milestone-reviews.md#m4) |
| M5 | Central↔Front/Rear 3-process SOME/IP Host FIFO 기능 한정 수용 | [실행 근거](test-plan/evidence/m5_someip_rear_adapter/README.md) |
| M6 | **Host quiet SIL/Python MIL 범위 CLOSED** | [종료 검토](archive/milestone-reviews.md#m6) · [최종 물리 응답](test-plan/evidence/m6_physical_response/README.md) |
| M7 | **시뮬레이션 시간 기능 통합 CLOSED / 실제 wall 실시간 수용 별도 OPEN** | [7개 실제 실행·독립 감사](test-plan/evidence/m7_carla_integrated/simulation-time/README.md) · [ADR-0065](archive/design-decisions.md#adr-0065) |
| M8 | **제어기·고정 fixture 기능 SIL 범위 CLOSED / 전체 Reference·wall·Target 별도 OPEN** | [종료 검토](archive/milestone-reviews.md#m8) · [마감 무결성](test-plan/evidence/m8_closeout/README.md) |
| M9 | native3-ECU 진단 전달 객체 재개·durable prefix 복구; 전체 ECU producer adoption·fault matrix 후속 | [진단 계약](interfaces/diagnostics.md) · [전달 이력 복구](test-plan/evidence/m9_delivery_restart/README.md) |
| M10–M13 | PLANNED / NOT RUN | [로드맵](roadmap.md) |

기술 검사와 학습자 설명·수용은 별도다. Component PASS를 전체 system/Target PASS로 올리지 않는다.

## M9 진단 집계·저장과 Central 검출 경로 연결

TBD-08의 [event/DTC 계약 v0.1](interfaces/diagnostics.md)에 따라 유한 SPSC 큐·중복/재발
집계·원본 clock/인과 보존·Unknown 재평가·trusted clear와 Linux journal을 구현했다.
Clear는 durable tombstone이며 제어 latch를 변경하지 않는다. 미완료 tail·오류·capacity는
기록 불완전으로 남기며 자동 복구하지 않는다. 집계/store 자체의
[이전 component 실행](test-plan/evidence/m9_diagnostics_component/README.md)을 보존한다.
후속으로 SpeedRequest/NormalStop/Coordinator의 원본 판정·phase·보호 ACK snapshot을 연결했다.
기존 SimpleVehicle 정상4350회 제어·정지/HV-off의 DTC0과 주행 중 현재 speed 입력만 누락한
case의 SD-1001 한 건을 실제 검출→Leaf 선택→Central ACK→fresh Actual→journal로 확인했다.
입력 누락 후 검출2ms, 검출부터 Leaf 선택0.2ms·Central ACK3ms·Actual acquisition209ms다.
제어·원본 권한·물리·에너지는 hook on/off에서 동일했다. 일반/논리1104개,
영향 ASan/UBSan147개와 기존 wall owner 회귀2개가 통과했다.
[명령·source·원본·독립 감사와 실패 이력](test-plan/evidence/m9_control_hooks/README.md)을 따른다.
이 숫자는 논리 fixture 반응이며 DTC의 wall 실시간 기록 지연 보장이 아니다.
SD-1001은 입력 복원만으로 보호를 해제하지 않고 INIT2의 실제 정상 요청 수용 뒤 Passed로
판정한다. 이력은 정상 정지/HV-off와 명시적 durable clear까지 남으며 writer 재시작 후에도
tombstone을 유지한다. 같은 물리 모델에서 INIT3 뒤 재고장은 generation2로 기록했다.
[복구·clear·재고장 근거](test-plan/evidence/m9_speed_recovery/README.md)를 따른다.
이번 일반/논리1109개, 영향 ASan/UBSan152개, 기존 wall owner2개가 통과했다.
ZoneFeedbackMonitor의 최초 fault/current·last-healthy input과 Leaf의 원래 accepted context
expiry를 소유자별 queue에 연결했다. SD-2002·SD-4002·SD-2001의 실제 복구 predicate를
추가하고 보호 전달 Observation과 구분했다. Central·두 Zone 정지→Leaf 자체 만료→재개 후
Zone 주기 초과→실패 링크 교체/INIT2→qualified Passed·미삭제 이력을 연속 검증했다.
[소유자별 범위와 실패 이력](test-plan/evidence/m9_owner_sources/README.md)을 따른다.
이번 일반/논리1118개·영향 ASan/UBSan124개·기존 wall owner2개가 통과했다.
Gateway·BMS·Power의 최초 native 원인/보호 전달·실제 정상 재시험을 별도 source publisher로
연결했다. 새 SD-2101/3101/3201은 명시적 registry2이며 기존 store를 자동 migration하지 않는다.
Central pause의 실제 두 Gateway 만료/ACK·물리 응답과 INIT2 뒤 완전 dispatch/Passed를
차량 논리 SIL로 확인했다. BMS 자체 trip/외부 보호와 Power sensor 누락/실제 RC HV Ready
재도달은 component 범위다. [native 원인·범위와 실패 이력](test-plan/evidence/m9_native_causes/README.md)을 따른다.
이번 일반/논리1129개·영향 ASan/UBSan206개·기존 wall owner2개가 통과했다.
후속으로 BMS electrical/Power current 누락을 실제 차량 SIL의 detector·local 보호·Zone ACK·
물리 응답·DTC·INIT2 복구까지 연결했다. 각각 SD-3101/3201 한 건이며 복원만으로 보호가
풀리지 않는다. 영구 Power current 누락은 차량 정지 후에도 HV-off를 선언하지 않는다.
[두 입력 손실 차량 검증](test-plan/evidence/m9_native_vehicle/README.md)을 따른다.
일반/논리1137개·영향 ASan/UBSan59개·기존 wall owner2개가 통과했다.
Release 전에는 실제 제어 Session과 별개인 trusted Attempt로 최초 기동 고장을 수집한다.
명시적 registry3·SD-4101로 Prepare/INIT/Release ACK 누락을 원래 detector/deadline/ACK mask와
연결했다. 실패한 epoch의 Session/Passed는 없으며 새 실제8-role Release 뒤에만 기동 복구를
인정한다. 기동 handshake 성공은 물리 HV/차량 readiness와 다르다.
[기동 시도·독립 감사·실패 이력](test-plan/evidence/m9_startup_sources/README.md)을 따른다.
최종 일반/논리1154개·영향 ASan/UBSan218개·기존 wall owner2개가 통과했다.
Event-only wire v1과 기존 journal 기반 유한 spool을 추가했다. 별도 송신/수신 process에서
commit 후 ACK 유실·양쪽 재시작·원본19개 event replay를 검증했다. Ordinal/bytes 중복은
이력을 늘리지 않고, receiver 재시작 뒤 중복 replay는 Unknown을 유지한다. 원격 clear는 없다.
[wire·spool 범위/실패/감사](test-plan/evidence/m9_delivery_spool/README.md)를 따른다.
최종 일반/논리1170개·영향 ASan/UBSan234개·별도 process 전송 Normal1/ASan1·기존 wall2개가 통과했다.
실제 SOME/IP 진단 channel에 새 logical owner의 SPSC→별도 writer→TCP→replica 경로를 연결했다.
Normal4350 controls/DTC0과10s 입력 손실·ACK 유실·replica kill/restart를 원본 detector/selection/
ACK/Actual·PCAP·journal로 대조했다. 재시작 Unknown과 이력은 유지하며 archived source를
새 실행으로 세지 않는다. [SOME/IP 실행·실패·한계](test-plan/evidence/m9_someip_live/README.md)를 따른다.
일반/논리1172개·영향 ASan/UBSan239개·SDK Normal4/ASan4·TSan live loss1·기존 wall2개가 통과했다.
원격 endpoint의 실제 accepted RunLease snapshot과 Central 원본 Session을 대조하는
ContextualOutbox를 추가했다. Local Ready/7개 ACK는 근거가 아니며 두 source의 원본 context
중복 제거·독립 durable ACK·지연된 context·재시작 Unknown을 component 범위에서 검증했다.
[범위·원본·검사](test-plan/evidence/m9_remote_context/README.md)를 따른다.
이 경계를 실제 Central/Front/Rear graph에 연결했다. Central 원본 Session과 실제 endpoint의
accepted credit를 사용하며9개 owner/native stream을 별도 writer·TCP·replica·merged journal로
모은다. 정상 DTC0과 Front/Rear 명령 손실·진단 ACK 유실·context 지연을 검증했다.
[native 배선·원본·실패·한계](test-plan/evidence/m9_native_routing/README.md)를 따른다.
최종 SDK 기능은 Normal5/ASan5/TSan2, 일반1188·영향 ASan279가 통과했다. Native guarded4ms는
별도6개 시도 모두 미통과이며 기존 M4AsyncWall2개 통과와 구분한다.
진단 전달 객체 재개를 추가했다. Remote source는 저장한 원본 Session을 실제 accepted endpoint
credit에 재대조하고 ordinal1부터 재전송한다. Collector는 replica-only commit의 merged 누락을
대조·복구한 뒤 기존 고장 상태를 Unknown으로 둔다. Actual native owner/SDK를 유지한 전달 객체
재개와 별도 process의 source/replica/merged SIGKILL3개 경계를 구분한다.
[전달 재개·원본·분모·실패](test-plan/evidence/m9_delivery_restart/README.md)를 따른다.
기본1206·영향 ASan296·native Normal9/ASan9가 통과했다. 단독 SDK TSan은5/6이며1개는
고장 주입 전 정상 선행 조건/cleanup 실패로 남겼다. 동시 실행 TSan2/6과 초기 감사 실패도 보존한다.
다음은 전체 native ECU 재기동의 producer identity/sequence adoption·commit 전 메모리 손실 조정과
다른 native 고장 조합·원인 연결/복구다. Native4ms와 M9 전체 수용은 계속 OPEN이다.
정규 DDS gate와 native wall/Target·부하/보존 용량 수용은 아직 후속이다.
다른 BMS trip/Power 고장 조합·Clock 복구·proposal 이전 bootstrap 실패는 후속이다.
실제 ACK/통신 손실의 주입 recipe·기대 결과는 사전 고정 후 검증한다.
30km/h ACK/통신 손실의 실제 주입 recipe와 기대 code·물리 기준은 실행 전에 고정한다.
TBD-08은 실제 모니터 경계의 code별 복구 predicate·전달/부하 검증·학습자 수용 전 CLOSED로 올리지 않는다.

## 구현·검증한 범위

Central은 조정·배분·영속 Epoch·8-role 세션과 RunLease를 소유한다.
Front는 Steering/Brake, Rear는 Drive/BMS/Power를 별도 process에서 단독 소유한다.
실제 SOME/IP·IP·owner-wire·CAN/P05 경계로 INIT/Release ACK/credit/arm,
명령·Actual·health·로컬 보호와 새 Epoch 재가입을 연결했다.

M6에서는 persistent physical process가 actuator·SimpleVehicle·EV/Battery를 소유하고
같은 구간 motor work로 차량과 전기 에너지를 결합한다. 실제 wheel feedback이 Central로 돌아온다.
최종 C++ Normal/ASan 각1018/1018, 계측 TSan 경계35/35, Python/무build export 각54/54는
[해당 quiet fixture의 근거](test-plan/evidence/m6_physical_response/README.md)다.
100ms loss 검출과 230ms 물리 응답의 기점·범위는 [물리 계약](interfaces/vehicle-energy.md#physical-response-contract)을 따른다.
Python 종방향 PI/MIL과 C++ SpeedPI는 독립 구현이다. C++ 속도 폐루프는 기존 Central→Zone→Leaf→Actual 경로와 SimpleVehicle의 논리 시간 범위에서 검증했다.

## M7 CARLA 통합 결과

사용자 승인 [ADR-0065](archive/design-decisions.md#adr-0065)에 따라 M7 기능 종료와 wall 실시간 수용을
분리한다. `m7-simulation-time-v1`의 실제7개 case가 통과했다. 비영상·영상 각각 한 세션60s/
6000 physics·6000 EV 정산, INIT 이후 정상5919구간, 가속·회생·제동·재출발6주기다.
영상은 RGB/GT 각1200개이며 원본 frame/timestamp 일치·누락0이다.
보호 시험은400구간 중 index278부터 자연 sleep122구간, 마지막100구간 동일 pose를 확인했다.
RGB 누락·stale snapshot·불완전 work·native SIGSTOP/실제10s 응답 감시 모두 다음 tick을 차단했다.
마지막 세 고장에는 완료 physics1구간의 EV 미정산을 남겼으며 완전한 에너지 정산이나 실제 정지로 세지 않는다.

Normal/ASan 각114/114, 연속성·session·숨은 reset·timestamp·정상 권한 손상6/6 거부.
비영상/영상60s의 실제 loop는 약213.88/244.37s였다. 원본320 substep 기록·검증과 의도적 pause를
포함한 관측값이며 CARLA 단독 성능 benchmark나 실시간 보장이 아니다.
[전체 원본·분모·재현](test-plan/evidence/m7_carla_integrated/simulation-time/README.md)을 따른다.

아래는 이전 통합과 별도 실시간 경로의 근거다. 새 기능 수용으로 과거 실패를 바꾸지 않는다.

| 범위 | 확인한 결과 | 실행 근거 |
| --- | --- | --- |
| 기능 주행·에너지·영상 | 고정 VehicleRequest → 실제8-role Actual → NoDrive → solver work → 단일 EV. 가속·회생·마찰 제동·휠 정지·재출발과 RGB/GT 검증 | [통합 실행](test-plan/evidence/m7_carla_integrated/README.md) |
| 보호 Actual·로딩 중 종료 | 기능 clock의 보호 Actual 연속 적용, 로딩 중 sync RPC 종료 교착 수정·검증 | [수정·실행](test-plan/evidence/m7_carla_recovery/README.md) · [요청 인과 검증](test-plan/evidence/m7_carla_recovery/causal-followup/README.md) |
| 보호 정지·client-loss 종료 | opt-in 보호 hold에서 body/wheel exact0·pose 유지; client 단절 시 동기 tick 종료 교착 수정. 고정 Town03/V1 범위 FIXED_LIMITED | [일괄 검증](test-plan/evidence/m7_carla_recovery/batch-closeout/README.md) |
| 독립 wall 감시 | 2ms/4ms 감시 → 로컬 보호 선택 → 다음 tick 차단. Terminal native owner는 입력 단절 뒤에도 보호 Actual 생성 | [wall guard](test-plan/evidence/m7_carla_wall_guard/README.md) · [terminal 응답](test-plan/evidence/m7_carla_wall_guard/terminal-response/README.md) |
| 증거 전달 최적화 | Raw solver journal 회수와 compact 전달을 분리하고 기존 physics/work/Actual 동등성 검증. 정상 wall timing 수용은 아님 | [전달 경로](test-plan/evidence/m7_carla_wall_guard/pipeline/README.md) |
| Wall owner component | 실제 monotonic timer·분리된 IO·유한 mailbox, 원래8-role service와 보호·완료 work 정산 검증. 합성 stationary 입력 범위 | [component 실행](test-plan/evidence/m7_carla_wall_guard/wall-owner/README.md) |
| 실제 CARLA wall 연결 | `wall5-hv50-v1`에서 파생 HV 예산을 분리한 뒤 정상2회·보호2회, 각900구간과 서버 종료 **4/4 통과**. 단기 비영상 한정이며 전체 실시간 수용은 OPEN | [HV 재조정·실행](test-plan/evidence/m7_carla_wall_guard/carla-runtime/hv-budget-v1/README.md) · [이전 실패 보존](test-plan/evidence/m7_carla_wall_guard/carla-runtime/nonvideo-wall5/README.md) |

이전 기능 시험의 정상5실행은 각각900구간, 약4.77215m 이동·최대 전방 속도 약1.259m/s다.
영상2실행은 각각 RGB180/GT180이다. Reference 30km/h 추종이나 전체 ODD 검증은 아니다.
마지막 wall 연결의 Normal/ASan 각113/113·TSan 경계26/26과 정상901/보호401개 replay 일치는
component/회귀 근거이며 실제 wall 주행 성공을 뜻하지 않는다.

## 남은 문제와 제한

| 항목 | 현재 처리 |
| --- | --- |
| 엔진 프레임 공백 | 최소 state 경로의10ms 요청1000구간은 source/공식 패키지 모두 최대 약10.83ms. RGB+GT에서는30ms 초과가 source200/1000·패키지17/1000으로 재현됨. 영상 경로의 지연 기여를 확인했으며 세부 blocking 원인은 미확정. 패키지 종료−11 실패 별도 보존. [대조 시험](test-plan/evidence/m7_carla_wall_guard/carla-runtime/frame-diagnostic/README.md) |
| Clock·실시간 실행 | simulation elapsed와 CLOCK_MONOTONIC을 분리. 고정 offset·heartbeat·timeout 증가로 2ms/4ms·30ms 수용을 대신할 수 없음 |
| 비영상 wall 반복 안정성 | ADR-0066의 HV source30ms/dependency50ms 분리 후 정상2회 모두900구간 완료. 실제 취득 age 최대13.595ms, dependency 최대31.661ms로 원인에 맞는 여유를 확인. M6·wheel/Actual·명령30ms·owner2ms/4ms 유지. 장시간·고속·영상으로 확대하지 않음 |
| Wall fault 후 실제 제동 | 정상 세션 이후 새 LocalProtection Actual의 실제 제동·자연 정지를 짧은 비영상 시험에서 확인.100ms physics 보류는 game thread 자체 정지가 아니며 장시간·전체 wall fault 수용은 OPEN |
| Source 서버 종료 | 과거 UE 종료SIGSEGV와 해당 FAIL 유지. HV 예산 시험4회는 정상 종료했지만 M8 전 정리 회귀의 정상 주행 뒤 UE GC 경로에서 종료−11을 다시 관측. 엔진 바이너리는 동일하며 원인 해결로 세지 않음 |
| Renderer | 카메라 없이 rendering만 켠 기본 source 경로는 최대16.66ms, RGB+GT의10ms 요청에서는 최대65.08ms/5frame 반복 지연. 영상 capture/render/readback과 물리 진행의 결합을 우선 조사. 과거 Distance Field SIGSEGV·전체 content/장시간 안정성은 미해결 |
| 과거 M3/M4·SDK | timing/FIFO·native·SDK sanitizer 기능 미완료 OPEN은 각 당시 분모·실패와 함께 보존 |
| DDS | 정규 제어 gate CLOSED, adapter 미착수. 기존 종료·20ms·TSan FAIL 및 접근 제한 이력 유지 |
| 전체 시스템·Target | 32개 요구/29개 system TC, Jetson·실제 IO·Host–Target 검증은 NOT RUN. C++ 제어는 M8 고정 fixture 범위 검증; AI는 후속 |

## M7 종료 조건

**m7-simulation-time-v1의 고정 Town03/V1 기능 범위는 CLOSED**다. 연속 정상·영상·원본 work/EV·
보호 Actual 자연 정지·센서/work 누락·Host 정지 차단·Actual-only/single writer·pause/reset/새 INIT를
실행·독립 검사했다. 고정 VehicleRequest 시험이며 M8 경로 추종·Reference30km/h·AI 수용은 아니다.

실제 wall 전체 수용은 **별도 OPEN**이다. 비영상 `wall5-hv50-v1`의 짧은 정상 반복·보호 정지는
4/4 통과했다. Normal/ASan·UBSan 각123/123, HV 예산/시각 손상6/6 거부를 확인했다.
실행 범위의 HV 예산 충돌은 해소했으며 서버 종료 원인·영상·장시간/고속 적합성은 남는다.
M6 wall 계약·수치·수용은 그대로이며 기존 wall 실패도 보존한다. source30ms·expiry는
기능 profile의 동일 simulation domain에서 유지하고 timestamp를 고쳐 쓰지 않는다.
상세 계약은 [시뮬레이션 시간 연속 실행](interfaces/carla-plant-adapter.md#시뮬레이션-시간-연속-실행)에 있다.

M8 전 공통 controller/owner·CMake·감사 reader 정리를 완료했다. Normal/ASan 각1170/1170,
지정 TSan 경계36/36, Python201/201, 기존 감사 결과19개 일치와 정상901/보호401개
native replay를 확인했다. 실제 CARLA 회귀는4개 중3개 전체 통과, 정상 wall 주행1개는
900구간 검사 통과 후 UE 종료−11로 실패다. [변경·원본·한계](test-plan/evidence/pre-m8-refactor/README.md)를
보존하며 M6/M7 수용 범위를 확대하지 않는다.

## M8 종료 조건

**M8 제어기·고정 fixture 기능 SIL 범위는 CLOSED**다. 원래 M8의 종방향 모델/C++
동등성, 실제 owner 경로의 속도 폐루프, Pure Pursuit와 고정 S01/S02/S03의30km/h
추종을 완료했다. 추가로 추진 포화 feedback·저속 고장 응답·30km/h NormalStop/HV-off를
검증했다. [종료 검토표](archive/milestone-reviews.md#m8)가 각 조건과 원본 근거를 연결한다.

현재 code/test는 마지막 검증 source와 일치한다. C++1217개·Python237개·영향 범위
ASan/UBSan33개는 보존된 최종 실행 결과다. 이번 마감은 새 물리 시험 없이 근거·추적성·
source/hash를 검토했다. [마감 기록](test-plan/evidence/m8_closeout/README.md)을 따른다.

다음은 **M9 고장 event→검출→보호→Actual→DTC 통합**이다.30km/h 입력 손실·제동
시간 초과·ACK/통신 손실의 추가 물리 시험은 이 묶음에서 고정 사건/기점/기대 상태와 함께
진행한다. 기존 fault latch·timeout·local protection은 계속 유지한다.

Planner/localization을 포함한 정식 S01–S03·32개 system 요구/29개 TC는 NOT RUN을
유지한다. wall·Target·전체 ODD·동적 가용력 참조·제동 포화와 과거 UE 원인도 별도 OPEN이다.
기술 마감과 학습자의 제어식·권한 전달 설명 review는 별도다.

## M8 종방향 제어기와 SimpleVehicle 폐루프

`m6-pi-v1`을 `central/longitudinal/`의 C++17 SpeedPI로 이식했다. 사전 고정한
입력·수치 오차·고장/INIT 기준으로 Python과 C++의 매 event 출력·관련 state를 비교했다.
Debug/Release/ASan·UBSan의 공통 vector 동등성이 통과했다.
[사전 protocol](test-plan/longitudinal-equivalence-protocol.md)과
[실행 원본·분모·한계](test-plan/evidence/m8_speed_pi/README.md)를 따른다.
`SpeedRequest`는 검증된 Drive Actual wheel source로 VehicleRequest를 만들고 기존
세션·permission·배분·보호·NormalStop 경로에 연결된다. 논리 시간 87초의
0→30→20→0km/h, 4,350회 제어가 통과했다. 실제 차량 plateau 최대 오차는
0.0497/0.0480/0km/h, 양수 목표 최대 overspeed는 1.291%다.
주행 중 Actual 손실·명령 중단도 기존 보호 경로와 실제 torque/brake 응답을 통과했다.
[프로토콜](test-plan/speed-loop-protocol.md)과 [실행 근거·한계](test-plan/evidence/m8_speed_loop/README.md)를 따른다.
이번 기존 wall 회귀는8/9였고 physical guard 실패의 단독 재확인은1/1이다.
초기 기동 보호의 정확한 timing 원인은 미확정이며 최초 FAIL을 보존한다.

SimpleVehicle 시험은 in-process owner/mailbox SIL이며 SOME/IP·실시간 scheduling 수용을 대신하지 않는다.
wall 실시간 gate는 기능 개발과 별도로 추적하며 개인 이해 review는 별도다.

## M8 CARLA 저속 속도 폐루프

V1 mass1696kg/radius0.355m를 명시적으로 연결하고 기존 eight-role INIT/RunLease,
Central→Zone→Leaf→native/server admission→solver work→single EV 경로를 실행했다.
40초/4,000개10ms physics interval, 1,960회20ms 제어에서0→10→0km/h를 추종했다.
차체 plateau 최대 오차0.02473km/h·양수 목표 overspeed1.42557%·정지 구간0,
제어 wheel은0.01882km/h·1.07297%·0이다. 4,000개 work 정산과 독립 wire/energy 감사가 통과했다.
Snapshot/work 누락은 각각200구간 뒤 다음 tick을 차단했고 정상·결함3개 서버 모두 정상 종료했다.

계산된 request의 생성 시각과 원래 wheel acquisition을 분리한다. 현재 feedback/request
age30ms와 기존 permission/command 제한을 유지하고, 별도 input dependency는 기존 PI의
60ms 기준으로 제한해 CommandContext oldest/expiry에 전달한다. SimpleVehicle sensor-root
매핑은 그대로다. 최초 합성 시험의 interval 실패와 설계 수정은
[사전 protocol](test-plan/carla-speed-protocol.md), [ADR-0069](archive/design-decisions.md#adr-0069),
[원본·재현·한계](test-plan/evidence/m8_carla_speed/README.md)에 기록했다.

## M8 고정 곡선 30km/h 추종

C++ Pure Pursuit를 기존 SpeedPI/VehicleRequest/Steering owner 경로에 연결했다.
Town04 고정 경로의 rear-axle pose는 원본 ActorSnapshot에서 변환하는 SIL fixture다.
최종 단일 세션6000 physics interval·2960 controls·6000 work settlement에서
300m marker를48.708s에 통과하고0→30→0km/h 주행과 정지·hold를 완료했다.

974개20Hz active-route sample의 cross-track P95는0.02783m, heading P95는0.2185deg다.
곡선 plateau10s의 차체 최대오차0.05503km/h(100Hz), 양수 목표 overspeed1.42135%이며
기준을 통과했다. 원본 command/Actual·solver work·single EV 독립 감사와20개 route
증거 변조 검사도 통과했다. Pose 시각 불일치는200구간 뒤 다음 tick을 차단했다.
최종 정상/결함 서버는 각각exit130으로 정리됐다.

회귀는 C++ unit/논리1203개, ASan/UBSan 대상63개, Python223개 통과다.
초기 Town04 로딩 시간 초과−9, 첫 완료 주행의 renderer 설정 복원 SIGSEGV−11,
누적 에너지 차분 audit 정밀도 실패를 보존했다. 구간 work 기록 정밀도는 재현 후
수정했으며 기존 감사 허용오차와 EV state 계산은 유지했다. UE renderer 근본 원인은 OPEN이다.

[계약](interfaces/lateral-route-controller.md), [사전 protocol/실패 이력](test-plan/carla-route-protocol.md),
[원본·판정·재현](test-plan/evidence/m8_route/README.md)을 따른다.
S01 직선과 S03 복합 경로·30→20km/h 전환의 후속 결과는 아래 절을 따른다.
단일 S02 후보의 기능 검증이며 전체 Reference, Planner/localization, wall 실시간,
CARLA NormalStop HV-off 수용으로 표시하지 않는다.
과거 UE 종료 실패와 wall 기동 실패도 OPEN으로 유지한다.


## M8 S01 직선·S03 복합 경로와 위치 기반 감속

Town06의 고정 Driving lane fixture에서 S01은6000 physics/2960 controls,
S03 v2는8000 physics/3960 controls와 모든 work 정산을 완료했다. S01의30km/h
차체 최대오차0.07484km/h, 횡오차 P95 0.001586m다. S03의30/20km/h 오차는
각0.07487/0.02810km/h, 횡오차 P95 0.03418m, heading P95 0.52851deg다.
20Hz 원본 active-route 표본은 각각974/1333개, 누락0이다.

S03 v2는 rear-axle230m에서20km/h 요청을 latch하고6s에 걸쳐 감속한다.
실제 요청 시각은37.8s, 곡선 진입45.368s의 body 속도는19.87454km/h다.
380m에서63.3s에 정지를 요청하고8s 감속,395m 완료 marker를66.668s에 통과했다.
양수 목표 최대 overspeed는 body3.48382%, wheel2.48238%로10% 기준 이내다.
최종 wheel0·hold·원래 설정 복원·actor 제거·서버exit130을 확인했다.

첫 S03 v1의10s startup은 기존300Nm 구동 상한에 비해 관성 토크501.733Nm를
요구했다. 첫 plateau 최대오차5.32610km/h로 FAIL이며 원본·판정은 유지한다.
v2는 S01에서 검증한20s startup과50m 더 긴 시작 직선을 별도 경로/hash로
고정했다. PI·구동 상한·감속6s·오차 기준은 바꾸지 않았다. 하위 구동 포화의
feedback/anti-windup과 reference 필요조건 검사는 아래 후속 절에서 별도로 검증했다.

같은 v2 binary의 pose source 불일치는200 physics·199 EV 정산 후 다음 tick을
차단했다. 미정산1구간을 완전 정산이나 실제 차량 제동 완료로 세지 않는다.
최종 C++ unit/논리1207개, ASan/UBSan 대상67개, Python230개, CLI scope12개가
통과했다. 독립 native/work/EV 감사와 S01/S03 증거 변조 검사를 완료했다.
이전 M8 증거683개 hash도 보존했다.

[사전 protocol와 v1 실패·v2 개정](test-plan/carla-reference-protocol.md),
[원본·수치·재현](test-plan/evidence/m8_reference/README.md),
[ADR-0071](archive/design-decisions.md#adr-0071)을 따른다.
후속 추진 포화와 저속 CARLA NormalStop·입력 누락의 실제 응답은 아래 절을 따른다. 고정 fixture S01/S02/S03의 기능 성능을 확인한 것이며
Planner/localization·전체 Reference·wall/Target 수용은 별도다.


## M8 추진 배분 포화 feedback과 참조 필요조건

2026-11-01. 선택형 v2는 하위 배분에서 양수 추진 요청이 제한되면 다음20ms PI의
양수 적분을 보류한다. 성공한 선택의 정확히 직전 parent/epoch/시각을 검사하며 기존
wheel/pose·request/input 권한은 유지한다. flag=false는 원본 v1과 같다.
실행 전 관성 토크 필요조건으로 S03 v1의10초 가속을 서버 기동 전에 거절한다.
20초 가속·경로·평가 window·300Nm 상한은 그대로다.

독립 Python/C++ v2의7224 events와 두 합성 plant 각2500 steps가 Release와
ASan/UBSan에서 일치했다. 분리된 포화/복귀 실험의 최대 속도는 v1 1.69332에서
v2 0.999992m/s로 줄었다(target1m/s). 실제 CARLA S03 v2는8000 physics/EV 정산,
3960 controls,1333 active20Hz 표본을 통과했다.30/20km/h plateau body 최대오차는
0.07718/0.02783km/h, 횡오차 P95 0.03410m, heading P95 0.53494deg다.
원본 배분7920개와 PI 식을 독립 확인했고 양수 적분을39회 보류했다.
이 고정 경로에서 모든 성능이 기존 v1보다 향상됐다는 의미는 아니다.

pose-stale는200 physics/199 settlements 후 다음 tick 차단을 확인했다. 실제 제동/HV-off
정지는 이번 판정이 아니다. C++ 회귀1212개와 새 CTest 동등성1개, ASan/UBSan 대상75개,
Python233개, CLI15개가 통과했다. 기존 증거866개와 원본 v1 hash를 보존했다.
[Protocol](test-plan/propulsion-saturation-protocol.md),
[원본·감사·재현](test-plan/evidence/m8_saturation/README.md),
[ADR-0072](archive/design-decisions.md#adr-0072)를 따른다.

저속 주행 중 입력 누락과 CARLA NormalStop의 실제 응답은 아래 절을 따른다.
동적 BMS/경사/도로 저항을 포함한 일반 참조 타당성, 제동 측 anti-windup,
Planner/localization·전체 Reference·wall/Target 수용은 OPEN이다.


## M8 저속 NormalStop·속도 입력 누락의 실제 CARLA 응답

2026-11-01. Town03 V1 simulation-time에서 약9.9823km/h 주행 중 두 사건을 각각
실행했다. 각4000 physics/4000 단일 EV 정산, 사건 전750 PI release와 독립 원본
CAN/owner-wire·solver/EV 감사를 통과했다. 다음 tick 차단만으로 정지를 판정하지 않는다.

NormalStop은 요청 후2.988s에 body·네 wheel 정지,3.178s에 원본 StopLease/선택 ACK
인계,3.778s에 Complete·HV-off를 확인했다. 원본 PowerStatus는 세 접촉기 open,
bus27V다. 기존1m/s²·제동5s·shutdown2s 설정을 유지했다. 정지 hold의2102 물리
구간에서도 원본 Actual freshness·8-role RunLease와20ms StopLease 갱신을 검사했다.

Central의 현재 Drive Actual 입력만 누락한 경우 해당20ms job에서 Feedback fault와
local protection을 선택했다. 원본 acquisition 기준 torque0은16ms, brake≥1MPa는
206ms(관측 약18/208ms), 물리 정지는2.108s였다. 전체 통신 단절이나 command-expiry
timeout 시험으로 세지 않으며 이 경우 HV-off 완료도 주장하지 않는다.
두 실행 모두 마지막1초 pose drift0, 정지 유지와 서버 정상 종료130을 확인했다.

최종 C++ unit/logical1214개, Python233개, ASan/UBSan 영향 범위22개와 최종 정지
재검사1개를 통과했다. 원본 StopLease/ACK 손상8종과 raw evidence 변조28종을 거절했다.
첫 NormalStop binary 이후 설정 검증 순서를 수정했으며 최종 binary에4001 원본 관측을
재생해 native JSON 전체 일치를 확인했다. 입력 누락 실행은 최종 binary를 사용했다.
이전 M8 증거1008개와 원본 v1 model hash를 보존했다.

[Protocol](test-plan/carla-stop-protocol.md), [원본·판정·재현](test-plan/evidence/m8_stop/README.md),
[ADR-0073](archive/design-decisions.md#adr-0073)를 따른다. 인계 후 명시적 보호 요청과30km/h 감속/deadline 검토는 아래 후속 절을 따른다.
ACK/전체 통신 손실의 물리 응답은 후속이다.
전체 Reference·Planner/localization·wall/Target와 기존 UE renderer/GC 원인은 OPEN이다.


## M8 정지 인계 후 보호 전환과30km/h 계약 검토

2026-11-02. 동일 Town03 약10km/h에서 NormalStop의 원본 handoff ACK 이후100ms에
8-role local protection을 선택했다. 실제 hold10구간을 거친 뒤 보호2092구간으로
전환했으며 전체4000 physics/4000 EV 정산을 통과했다. 보호 상태 torque0의 원본
acquisition은 주입 후5.6ms, brake≥1MPa는185.6ms(관측7.6/187.6ms)였다.
보호 전후 body/네 wheel 정지와 마지막1초 pose drift0을 확인했다. 이 시험은 명시적
SIL safety request이며 ACK-loss나 통신 단절 검출 시험·NormalStop HV-off 완료가 아니다.

서버는 동일 release/8-role 보호 mask·credit0·마지막 hold보다 뒤인 선택 시각·새 원본
LocalProtection Actual을 확인해야 보호로 전환한다. 기존 source/whole-interval/expiry는
유지하며 normal/hold 재개를 거절한다. 첫 실제 실행은 새 mode의 JSON StopLease/ACK
누락으로1898 physics/EV 뒤 차단됐다. 원본 FAIL을 보존하고 직렬화 회귀를 추가했다.
수정 후4000구간과 독립 native/work/EV 감사·terminal 변조22종을 통과했다.

C++ unit/logical1215개, Python233개, ASan/UBSan41개와 CLI4001관측 검사를 통과했다.
기존 NormalStop·입력 누락의8002 원본 관측은 최종 binary에서 JSON 전체가 일치했다.
이전 M8 증거1135개와 원본 v1 model hash를 보존했다.

30km/h는 기존1m/s²로 이상적 감속만8.333s가 필요해5s 제동 예산과 충돌한다.
낙관적 무지연 입력의 C++ 시험에서도 정확히5s에 BrakingTimeout을 확인했다.
기본 설정은 유지하며 다음 후보를 별도30km/h profile의1m/s²·제동10s·shutdown2s로
정리했다. 이 계약 검토 이후 별도30km/h 실제 정지 결과는 아래 절을 따른다.

[Protocol](test-plan/carla-stop-fault-protocol.md), [실행 근거](test-plan/evidence/m8_stop_fault/README.md),
[30km/h 계약 검토](test-plan/normal-stop-30-contract-review.md),
[ADR-0074](archive/design-decisions.md#adr-0074)를 따른다. 별도30km/h fixture의
정지 계약 연결·실제 응답은 아래 후속 절에서 검증했다. ACK/전체 통신 손실의 물리 응답,전체 Reference,
Planner/localization·wall/Target·UE renderer/GC 원인은 OPEN이다.


## M8 별도30km/h NormalStop·HV-off

2026-11-02. Town06 고정 직선에서20s 가속 후 첫 PI release+35s에 NormalStop을
요청했다. 별도 `normal-stop30-a1-t10-v1`은 감속1m/s²·제동10s·shutdown2s를
coordinator 생성 시 전달하며 기존5s 기본값은 유지한다. 사건 시 body29.952690km/h에서
요청 후8.477999s에 body·네 wheel 연속 정지를 시작했고,8.678s에 물리 hold 인계,
9.277999s에 Complete·HV-off를 확인했다. ACK 이후 shutdown은 약.608s로2s 이내다.
원본 PowerStatus는 세 접촉기 open·bus27V, 마지막1초 pose drift는0m다.

전체6000 physics/6000 단일 EV 정산과1750 PI/Pure Pursuit release를 독립 감사했다.
PI 식 차이는0, plateau body/wheel 최대오차는.074842/.030900km/h다.900개의20Hz
경로 표본에서 횡오차 P95 .001690m, heading P95 .007805deg, 최종 progress242.205m다.
정지 hold는1552 물리 구간이다. 마지막 settlement 행을 포함한1553관측과 구분한다.

C++ unit/logical1217개, Python237개, ASan/UBSan 영향 범위33개를 통과했다.
기존 저속 두 실행의8002개 native 관측은 새 binary로 전체 JSON이 일치했다.
첫 독립 감사는 마지막 PI 이후의 원본 wheel 표본을 놓친 집계 오류로 실패했다.
원본1000개 Drive acquisition에서 고정 구간의50Hz500개를 추출하도록 수정했으며
구간·분모·허용 오차와 물리 producer는 바꾸지 않았다. 실패와 교정 근거를 보존했다.
이전 M8 evidence1305파일과 원본 v1 hash도 유지했다.

[사전 protocol](test-plan/carla-stop30-protocol.md), [원본·감사·재현](test-plan/evidence/m8_stop30/README.md),
[ADR-0075](archive/design-decisions.md#adr-0075)를 따른다. 같은30km/h 참조의
timeout·입력 손실 및 ACK/통신 손실 고장별 실제 응답은 M9 후속이다. 고정 nominal 직선 수용이며
전체 Reference·Planner/localization·wall/Target와 UE renderer/GC 원인은 OPEN이다.
