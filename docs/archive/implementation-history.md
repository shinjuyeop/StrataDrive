# 구현·검증 이력

2026-11-06 정리한 M7–M9 경과와 2026-11-12에 통합한 M10 상세 기록을 보존한다.
현재 판정은 [프로젝트 상태](../project-status.md), 최신 근거는 [검증 안내](../test-plan/README.md)를 따른다.
아래의 당시 OPEN·다음 작업·중간 분모는 현재 판정으로 해석하지 않는다. Raw evidence는 이동하거나 수정하지 않았다.

## M9 마감 시점

위치 이동 전 최종 판정은 `3d685f6`의 [유한 Host·simulation10ms 마감 근거](../test-plan/evidence/m9_followup/README.md)다.
아래의 “위 최종 근거”는 이 실행을 가리키며, 최신 구현 상태는 현재 프로젝트 상태 문서를 따른다.

## M9 이번 후속 구현

[M9 후속 근거](../test-plan/evidence/m9_completion/README.md)에 실제 CARLA30 정상·입력 손실·
Stop ACK 손실·명시적 전륜 link failure·제동10s timeout의 원본 trace와 독립 감사를 묶었다.
최초 native allocator/async transport의 원인·시각·token/expiry를 보호 상태 전환 전에 보존한다.
NormalStop은 새 동일 설정의 실제 전체 cycle/Complete 후에만 Passed를 발행하고 별도 현재
stationary/HV-off 증거와 명시적 요청으로 clear한다. Clock은 이 predicate에서 제외한다.
BMS9개 trip mask와 Power8개 물리 고장 조합은 electrical component 수준으로 확장했다.

이번에는 두 차례의 bounded ingress가 같은 lane별8건 budget을 공유하도록 하고,
StopRequest 발행을 VM의+4ms grid에 맞췄다. 놓친 job은 재생하지 않고 원래 source/expiry를
보존한다. 지연된 allocation이 이전 회차로 grant를 심사한 뒤 현재 회차를 완료로 기록해
다음 release보다405611ns 앞서 command가 만료되던 결함도 수정했다.
[입력/회차 후보](../test-plan/evidence/m9_allocation_release/README.md)의 원본과 실패를 보존한다.

NormalStop의 원래 만료를 관리 주기 사이에서도 poll해 SD-1105를 누락하지 않게 했다.
동시에 실제 transport 원인도 존재할 때 두 원본 DTC의 시간·token·공통 만료·관련 event를
검증하도록 감사기를 보완했다. [정지 만료 후보](../test-plan/evidence/m9_stop_deadline/README.md)는
기능12/12·서비스 최초25/30, 사후 원본 재감사27/30이다. 이전4개 후보의 fault80건도
대조했으며 예상한 최초 detector 보완 외의 판정 변경은 없다.

[선행 권한 후보](../test-plan/evidence/m9_deferred_grant/README.md)는 원래 기다리는 due 이후의
새 grant인지와 현재 실행 회차부터 기존18ms support가 남았는지를 따로 확인한다.
이미 처리한 권한 재사용·기한 연장은 거절한다. 전체 Debug1273·ASan/UBSan1273,
관련 TSan112·Python42·CARLA adapter 논리162·변경 구현 정적 검사가 통과했다.
실제 CARLA 서버 재실행이나 native4ms·Target 검사로 해석하지 않는다.

[물리 전달 후보](../test-plan/evidence/m9_plant_field_io/README.md)는 센서·각 Leaf 출력·Release의
파일 잠금을 분리하고 Leaf 실행 직후 출력을 전달한다. 선행 Brake Actual은 누락이 아니라
유효 Degraded952000Pa였다. 원래 detector/tolerance를 유지했으며 기능12/12·서비스28/30이다.
전체 Debug/ASan·UBSan 각1277개는 통과했다. 관련 TSan은115/116이며, 새 IO를 사용하지
않는 기존 메모리 M4 wall 정상 시험1건의 기한 초과는 원래 실패 기록으로 남긴다.
현재 수용에서의 계측/비계측 구분은 아래를 따른다.

**현재 Host quiet 서비스는 사용자 승인 `split-v1` 분리 판정을 통과했다.**
[이번 원본·재현](../test-plan/evidence/m9_validation_split/README.md)은 비계측 RelWithDebInfo
6조건×3회 **18/18**, 서비스·ordering·placement·response 독립 감사와 변조 검사 전부 통과다.
ASan/UBSan와 TSan은 각각21 targets **309/309**, 비계측 M4 wall2/2,
Python 판정/SDK/배치49/49다. Sanitizer의 두 M4 wall 시험만 비계측 검사로 옮겼으며
논리 SIL의 만료·보호 경계와 실제 동시성 검사는 유지한다. SDK 전체 sanitizer 수용은 별도다.

이 분리 판정에 사용한 C++/header/CMake1020개와 native normal binary는 선행 egress 후보와 같다.
20ms envelope·10ms 갱신/18ms support·원래 source/expiry·물리 보호 기준은 늘리지 않았다.
이번 native18건의 SDK 오류는0이다. 계측 지연 자체를 제거했다고 주장하지 않는다.
[사전 protocol](../test-plan/service-validation-protocol.md)과
[ADR-0102](design-decisions.md#adr-0102-m9-서비스-수용에서-sanitizer와-wall-성능을-분리)를 따른다.

선행 [egress 후보](../test-plan/evidence/m9_egress/README.md)는 기능12/12·혼합 서비스27/30의
원본 판정을 보존한다. 사용자가 승인한 이전 연결 오류 분류로 원본을 메모리에서 재감사하면
28/30이며 ASan stop-ack-loss의 SIGKILL 직후 reset1건만 달라진다. 실제 두 surviving owner의
보호/물리 반응·새 Epoch 재가입을 요구한다. TSan 갱신 만료2건과 기존 M4 TSan wall 실패는
원래 실패로 남으며 이번18건과 합치지 않는다. 큐 포화·새 세션 오류·sanitizer 경고는 면제하지 않는다.

[SDK owner 코어 공유23/30](../test-plan/evidence/m9_sdk_owner_core/README.md)과 이전 SMT 후보는
미채택이다. SDK I/O2·단일 CPU4/5/6을 유지한다. 후보별 분모·실패·source/binary를 보존한다.

**BMS/Power8-role 센서 고장 조합을 추가 검증했다.**
[센서 matrix](../test-plan/evidence/m9_sensor_matrix/README.md)는 BMS9·Power3·동시3조건을
입력 복원만 하는14s와 새 세션 복구24s로 각각 실행한다. 기존 검출·보호·실제 torque/brake·
정지/HV-off·durable DTC·Passed를 연결하며 자동 clear하지 않는다. 선행 BMS inhibition 뒤
Power contactor timeout과 자체 bus-low 미확정의 차이도 확인했다. 센서 소비 사본의 고장
시험이며 electrical plant 자체 고장·실제 CARLA·native wall matrix로 확대하지 않는다.

**Proposal 이전 기동 기록을 연결했다.** [Bootstrap incident](../test-plan/evidence/m9_bootstrap/README.md)는
EpochStore/journal 실패를 별도 영구 spool에 기록하며 가짜 application Epoch를 만들지 않는다.
초기 journal 검증 실패는 해당 process의 owner/proposal 전에 반환한다. 중단·실패 이력은 새 기동 성공 뒤에도
유지하며 자동 Passed/Clear하지 않는다. Spool 자체 장애는 기동을 막고, 전체 디스크/전원 장애와
장기 운영 보존은 별도 범위로 남긴다.

**Clock 복구·Power lifecycle·비활성 기록 보존을 연결했다.**
[이번 근거](../test-plan/evidence/m9_remaining/README.md)는 명시적 trusted Clock 재검증과
새8-role Release 뒤100ms의 정상 source 진행을 요구한다. 실제 rollback 후 INIT만 한
대조군은 Unknown을 유지한다. Power precharge/request-loss/shutdown-current/startup-energized/
discharge5조건은 복원만 한 경우와 새 세션 복구를 모두 검증했다. RequestLost는 상위
CommandLoss가 먼저 보호한 원본 순서를 보존하며 도달하지 않은 Power DTC를 만들지 않는다.
Debug/ASan·UBSan/TSan 각각 영향88개·차량12조건·변조94개, 전체 Debug1336개가 통과했다.
비활성 store의 독점 잠금 아래 원형 archive/새 directory 복원을 구현하고 실제 journal36개를
byte 동일하게 복원·독립 재감사했다. 자동 clear나 용량 회수는 하지 않는다.

선행 긴 native 서비스는 기준500ms1회와 Epoch2/3 각각60s의 quiet3회가 독립 감사까지 통과했다.
Owner CPU1/2/7의70% busy demand 부하에서는 첫 실행이 Drive command expiry로 보호 전환했다.
Front 응답 대기7.138ms 뒤 Rear에 전달했고 다음 Rear command가 기존 만료보다1.572ms 늦게
enqueue됐다. 최초 검출과 실제 정지·영속 SD-2001은 보존했으나 정상 서비스 완료로 세지 않는다.
당시 최종 cohort는6/7(기준+quiet4/4, loaded2/3)이며 통과6건은 네 독립 감사도 통과했다.
초기 후보의 실패·중단과 부하 실패의 원본은 위 후속 근거에 함께 보존한다.

이 당시 남았던 부하 갱신과 silent loss 연결은 위 최종 근거에서 다룬다. CARLA 수용은
명시한10ms sample/hold 해상도다. 기본512-event 경계와 비활성 archive/restore는
유한 운용 범위이며 자동 장기 상태 이관·용량 회수는 별도다. 아래 과거 근거의 당시
범위/실패는 그대로 유지한다.

## M9 진단 집계·저장과 Central 검출 경로 연결

TBD-08의 [event/DTC 계약 v0.1](../interfaces/diagnostics.md)에 따라 유한 SPSC 큐·중복/재발
집계·원본 clock/인과 보존·Unknown 재평가·trusted clear와 Linux journal을 구현했다.
Clear는 durable tombstone이며 제어 latch를 변경하지 않는다. 미완료 tail·오류·capacity는
기록 불완전으로 남기며 자동 복구하지 않는다. 집계/store 자체의
[이전 component 실행](../test-plan/evidence/m9_diagnostics_component/README.md)을 보존한다.
후속으로 SpeedRequest/NormalStop/Coordinator의 원본 판정·phase·보호 ACK snapshot을 연결했다.
기존 SimpleVehicle 정상4350회 제어·정지/HV-off의 DTC0과 주행 중 현재 speed 입력만 누락한
case의 SD-1001 한 건을 실제 검출→Leaf 선택→Central ACK→fresh Actual→journal로 확인했다.
입력 누락 후 검출2ms, 검출부터 Leaf 선택0.2ms·Central ACK3ms·Actual acquisition209ms다.
제어·원본 권한·물리·에너지는 hook on/off에서 동일했다. 일반/논리1104개,
영향 ASan/UBSan147개와 기존 wall owner 회귀2개가 통과했다.
[명령·source·원본·독립 감사와 실패 이력](../test-plan/evidence/m9_control_hooks/README.md)을 따른다.
이 숫자는 논리 fixture 반응이며 DTC의 wall 실시간 기록 지연 보장이 아니다.
SD-1001은 입력 복원만으로 보호를 해제하지 않고 INIT2의 실제 정상 요청 수용 뒤 Passed로
판정한다. 이력은 정상 정지/HV-off와 명시적 durable clear까지 남으며 writer 재시작 후에도
tombstone을 유지한다. 같은 물리 모델에서 INIT3 뒤 재고장은 generation2로 기록했다.
[복구·clear·재고장 근거](../test-plan/evidence/m9_speed_recovery/README.md)를 따른다.
이번 일반/논리1109개, 영향 ASan/UBSan152개, 기존 wall owner2개가 통과했다.
ZoneFeedbackMonitor의 최초 fault/current·last-healthy input과 Leaf의 원래 accepted context
expiry를 소유자별 queue에 연결했다. SD-2002·SD-4002·SD-2001의 실제 복구 predicate를
추가하고 보호 전달 Observation과 구분했다. Central·두 Zone 정지→Leaf 자체 만료→재개 후
Zone 주기 초과→실패 링크 교체/INIT2→qualified Passed·미삭제 이력을 연속 검증했다.
[소유자별 범위와 실패 이력](../test-plan/evidence/m9_owner_sources/README.md)을 따른다.
이번 일반/논리1118개·영향 ASan/UBSan124개·기존 wall owner2개가 통과했다.
Gateway·BMS·Power의 최초 native 원인/보호 전달·실제 정상 재시험을 별도 source publisher로
연결했다. 새 SD-2101/3101/3201은 명시적 registry2이며 기존 store를 자동 migration하지 않는다.
Central pause의 실제 두 Gateway 만료/ACK·물리 응답과 INIT2 뒤 완전 dispatch/Passed를
차량 논리 SIL로 확인했다. BMS 자체 trip/외부 보호와 Power sensor 누락/실제 RC HV Ready
재도달은 component 범위다. [native 원인·범위와 실패 이력](../test-plan/evidence/m9_native_causes/README.md)을 따른다.
이번 일반/논리1129개·영향 ASan/UBSan206개·기존 wall owner2개가 통과했다.
후속으로 BMS electrical/Power current 누락을 실제 차량 SIL의 detector·local 보호·Zone ACK·
물리 응답·DTC·INIT2 복구까지 연결했다. 각각 SD-3101/3201 한 건이며 복원만으로 보호가
풀리지 않는다. 영구 Power current 누락은 차량 정지 후에도 HV-off를 선언하지 않는다.
[두 입력 손실 차량 검증](../test-plan/evidence/m9_native_vehicle/README.md)을 따른다.
일반/논리1137개·영향 ASan/UBSan59개·기존 wall owner2개가 통과했다.
Release 전에는 실제 제어 Session과 별개인 trusted Attempt로 최초 기동 고장을 수집한다.
명시적 registry3·SD-4101로 Prepare/INIT/Release ACK 누락을 원래 detector/deadline/ACK mask와
연결했다. 실패한 epoch의 Session/Passed는 없으며 새 실제8-role Release 뒤에만 기동 복구를
인정한다. 기동 handshake 성공은 물리 HV/차량 readiness와 다르다.
[기동 시도·독립 감사·실패 이력](../test-plan/evidence/m9_startup_sources/README.md)을 따른다.
최종 일반/논리1154개·영향 ASan/UBSan218개·기존 wall owner2개가 통과했다.
Event-only wire v1과 기존 journal 기반 유한 spool을 추가했다. 별도 송신/수신 process에서
commit 후 ACK 유실·양쪽 재시작·원본19개 event replay를 검증했다. Ordinal/bytes 중복은
이력을 늘리지 않고, receiver 재시작 뒤 중복 replay는 Unknown을 유지한다. 원격 clear는 없다.
[wire·spool 범위/실패/감사](../test-plan/evidence/m9_delivery_spool/README.md)를 따른다.
최종 일반/논리1170개·영향 ASan/UBSan234개·별도 process 전송 Normal1/ASan1·기존 wall2개가 통과했다.
실제 SOME/IP 진단 channel에 새 logical owner의 SPSC→별도 writer→TCP→replica 경로를 연결했다.
Normal4350 controls/DTC0과10s 입력 손실·ACK 유실·replica kill/restart를 원본 detector/selection/
ACK/Actual·PCAP·journal로 대조했다. 재시작 Unknown과 이력은 유지하며 archived source를
새 실행으로 세지 않는다. [SOME/IP 실행·실패·한계](../test-plan/evidence/m9_someip_live/README.md)를 따른다.
일반/논리1172개·영향 ASan/UBSan239개·SDK Normal4/ASan4·TSan live loss1·기존 wall2개가 통과했다.
원격 endpoint의 실제 accepted RunLease snapshot과 Central 원본 Session을 대조하는
ContextualOutbox를 추가했다. Local Ready/7개 ACK는 근거가 아니며 두 source의 원본 context
중복 제거·독립 durable ACK·지연된 context·재시작 Unknown을 component 범위에서 검증했다.
[범위·원본·검사](../test-plan/evidence/m9_remote_context/README.md)를 따른다.
이 경계를 실제 Central/Front/Rear graph에 연결했다. Central 원본 Session과 실제 endpoint의
accepted credit를 사용하며9개 owner/native stream을 별도 writer·TCP·replica·merged journal로
모은다. 정상 DTC0과 Front/Rear 명령 손실·진단 ACK 유실·context 지연을 검증했다.
[native 배선·원본·실패·한계](../test-plan/evidence/m9_native_routing/README.md)를 따른다.
최종 SDK 기능은 Normal5/ASan5/TSan2, 일반1188·영향 ASan279가 통과했다. Native guarded4ms는
별도6개 시도 모두 미통과이며 기존 M4AsyncWall2개 통과와 구분한다.
진단 전달 객체 재개를 추가했다. Remote source는 저장한 원본 Session을 실제 accepted endpoint
credit에 재대조하고 ordinal1부터 재전송한다. Collector는 replica-only commit의 merged 누락을
대조·복구한 뒤 기존 고장 상태를 Unknown으로 둔다. Actual native owner/SDK를 유지한 전달 객체
재개와 별도 process의 source/replica/merged SIGKILL3개 경계를 구분한다.
[전달 재개·원본·분모·실패](../test-plan/evidence/m9_delivery_restart/README.md)를 따른다.
기본1206·영향 ASan296·native Normal9/ASan9가 통과했다. 단독 SDK TSan은5/6이며1개는
고장 주입 전 정상 선행 조건/cleanup 실패로 남겼다. 동시 실행 TSan2/6과 초기 감사 실패도 보존한다.
Front/Rear의 실제 ECU/SDK process를 SIGKILL하고 생존2 ECU·plant를 유지한 새 Epoch2 재합류를
연결했다. Private lifecycle journal이 새 발행자 세대를 영속 발급하고 별도 stream에서 순번1을
시작한다. 이전 committed prefix는 새 SDK client로 원형 재전송한다. Commit 전 메모리는 복구한
것으로 세지 않고 SD-5001의 cause_unknown/unmapped incident로 표시해 clear를 막는다.
[발행자 세대·손실 미확인·독립 감사·실패](../test-plan/evidence/m9_producer_adoption/README.md)를 따른다.
최종 native Normal11/ASan11·unit/logical/transport1202·영향 ASan301이 통과했다. SDK TSan은3/4이며
Rear rejoin의 새 정상 제어 구간 보호 선택을 미통과로 남겼다. 기존 wall은 최초8/9 후 실패 항목의
동일 기준 단독1/1을 구분하며 기존 native4ms/Target 수용을 닫지 않는다.
Central process 재기동도 명시적 issuer 구간과 fresh collector에 연결했다. 생존 Front/Rear의
원본 producer/sequence는 유지하며 실제 Epoch2/credit 뒤 원형 prefix를 재전송한다. 이전 저장소와
suffix를 보존하고 새 Central의 SD-5001은 정상 복귀/replay 뒤에도 clear를 막는다.
[Central 재기동·원본·분모·실패](../test-plan/evidence/m9_central_restart/README.md)를 따른다.
최종 native Normal12/ASan12/SDK TSan3·일반1206·기존 wall9·영향 ASan305가 통과했다.
초기 ingress overflow와 compile/runner 실패는 보존하며 기존 native4ms/Target 수용과 구분한다.
로컬 서비스 심사는 미확인 과거 이력의 명시적 수용과 현재 recording Passed를 분리한다.
전체 frozen source/replica/ACK·새 실제 Epoch/credit·최신 정지 입력을 확인하고 영속 Review 뒤
별도 Passed/clear를 요구한다. 재시작 후 과거 proof로 현재 상태를 재활성화하지 않는다.
[로컬 심사·원본·분모·실패](../test-plan/evidence/m9_continuity_review/README.md)를 따른다.
일반1215·기존 wall9·영향 ASan314·service writer4컷씩의 Normal/ASan이 통과했다.
SDK 회귀 Normal11/12·ASan12/12·TSan3/3이며 Normal Central의88.6ms owner 간격/overflow 실패는 유지한다.
Linux 로컬 서비스는 SO_PEERCRED UID/PID·boot capability·정확한 Session/incident/revision을
인가한 뒤 frozen guard와 원본 Actual 취득을 연결한다. Review→Passed와 별도 clear 요청을 구분하고,
재심사 중단/스트림 변경/재요청 충돌·capture 예외/저장 실패 시 clear를 막는다.
[로컬 서비스 연결·원본·검증 범위](../test-plan/evidence/m9_continuity_service/README.md)를 따른다.
최종 일반1223·기존 wall9·서비스 ASan8/TSan8·독립 변조48개가 통과했다. 앞선 넓은 ASan336개와
최종 수정 후 서비스8개를 구분한다. 초기 compile/거부 응답 전달/Release 경고·TSan 시작 실패를 보존했다.
실제3-ECU terminal 서비스도 연결했다. Central 재기동의 Epoch2 정상 정지 후 별도 명시적 요청으로
Epoch3를 발급하고 실제8-role Release·운전/정지·보호 뒤9개 source/collector를 순서대로 드레인한다.
새 physical Actual은 전 writer의 freeze보다 뒤에서 취득됐음을 PCAP/CAN/원본 물리 기록으로 대조한다.
로컬 인가와 Review→Passed→별도 clear만 별도 service journal에 기록하며 원형 unknown 이력은 유지한다.
[Native 서비스 조합·분모·실패](../test-plan/evidence/m9_native_service/README.md)를 따른다.
해당 당시 서비스 Normal/ASan은 통과했고, TSan은 Epoch2 정지 중 Allocation 보호로 서비스 진입 전 실패했다.
이전 두 TSan 서비스 통과·기존 SDK 회귀12/12·12/12·3/3과 구분하며 최종 TSan 수용은 OPEN이다.
일반1223·wall9·로컬 ASan17·Python24·변경3 TU 정적/Release 검사를 확인했다.
EpochStore fsync 동안 owner가 멈춘 초기 ASan 실패는 보호 ACK 후 비실시간 IO/계속 수신과
old owner의 지연 폐기로 수정했다. 초기 소켓 정리·독립 감사/취득 기록·compile 실패도 보존했다.
TSan Allocation 원인 분석과 실제 서비스 고장 거절의 이번 결과는 위 M9 후속 근거에 기록한다.
당시 Native4ms와 M9 전체 수용은 OPEN이었다. 현재 기능 범위 마감은 위 최종 근거를 따른다.
DDS 제어 gate는 CLOSED인 별도 대안이며 M9 SOME/IP 완료 조건이 아니다. Native wall/Target과 실제 부하/장기 보존 수용은 별도다.
BMS/Power 차량 조합·명시적 Clock 복구·proposal 이전 bootstrap의 최신 검증은 위 후속 근거를 따른다.
실제 ACK/통신 손실의 주입 recipe·기대 결과는 사전 고정 후 검증한다.
이번30km/h recipe와 기대 code·물리 기준은 [사전 protocol](../test-plan/carla-diagnostics-protocol.md)에 고정했다.
TBD-08의 실제 모니터 경계·code별 복구 predicate·전달/유한 부하의 기술 검증은 위 근거를 따른다.
학습자 최종 수용은 기술 기능 마감과 별도이며 자동으로 CLOSED 처리하지 않는다.

## 구현·검증한 범위

Central은 조정·배분·영속 Epoch·8-role 세션과 RunLease를 소유한다.
Front는 Steering/Brake, Rear는 Drive/BMS/Power를 별도 process에서 단독 소유한다.
실제 SOME/IP·IP·owner-wire·CAN/P05 경계로 INIT/Release ACK/credit/arm,
명령·Actual·health·로컬 보호와 새 Epoch 재가입을 연결했다.

M6에서는 persistent physical process가 actuator·SimpleVehicle·EV/Battery를 소유하고
같은 구간 motor work로 차량과 전기 에너지를 결합한다. 실제 wheel feedback이 Central로 돌아온다.
최종 C++ Normal/ASan 각1018/1018, 계측 TSan 경계35/35, Python/무build export 각54/54는
[해당 quiet fixture의 근거](../test-plan/evidence/m6_physical_response/README.md)다.
100ms loss 검출과 230ms 물리 응답의 기점·범위는 [물리 계약](../interfaces/vehicle-energy.md#physical-response-contract)을 따른다.
Python 종방향 PI/MIL과 C++ SpeedPI는 독립 구현이다. C++ 속도 폐루프는 기존 Central→Zone→Leaf→Actual 경로와 SimpleVehicle의 논리 시간 범위에서 검증했다.

## M7 CARLA 통합 결과

사용자 승인 [ADR-0065](design-decisions.md#adr-0065)에 따라 M7 기능 종료와 wall 실시간 수용을
분리한다. `m7-simulation-time-v1`의 실제7개 case가 통과했다. 비영상·영상 각각 한 세션60s/
6000 physics·6000 EV 정산, INIT 이후 정상5919구간, 가속·회생·제동·재출발6주기다.
영상은 RGB/GT 각1200개이며 원본 frame/timestamp 일치·누락0이다.
보호 시험은400구간 중 index278부터 자연 sleep122구간, 마지막100구간 동일 pose를 확인했다.
RGB 누락·stale snapshot·불완전 work·native SIGSTOP/실제10s 응답 감시 모두 다음 tick을 차단했다.
마지막 세 고장에는 완료 physics1구간의 EV 미정산을 남겼으며 완전한 에너지 정산이나 실제 정지로 세지 않는다.

Normal/ASan 각114/114, 연속성·session·숨은 reset·timestamp·정상 권한 손상6/6 거부.
비영상/영상60s의 실제 loop는 약213.88/244.37s였다. 원본320 substep 기록·검증과 의도적 pause를
포함한 관측값이며 CARLA 단독 성능 benchmark나 실시간 보장이 아니다.
[전체 원본·분모·재현](../test-plan/evidence/m7_carla_integrated/simulation-time/README.md)을 따른다.

아래는 이전 통합과 별도 실시간 경로의 근거다. 새 기능 수용으로 과거 실패를 바꾸지 않는다.

| 범위 | 확인한 결과 | 실행 근거 |
| --- | --- | --- |
| 기능 주행·에너지·영상 | 고정 VehicleRequest → 실제8-role Actual → NoDrive → solver work → 단일 EV. 가속·회생·마찰 제동·휠 정지·재출발과 RGB/GT 검증 | [통합 실행](../test-plan/evidence/m7_carla_integrated/README.md) |
| 보호 Actual·로딩 중 종료 | 기능 clock의 보호 Actual 연속 적용, 로딩 중 sync RPC 종료 교착 수정·검증 | [수정·실행](../test-plan/evidence/m7_carla_recovery/README.md) · [요청 인과 검증](../test-plan/evidence/m7_carla_recovery/causal-followup/README.md) |
| 보호 정지·client-loss 종료 | opt-in 보호 hold에서 body/wheel exact0·pose 유지; client 단절 시 동기 tick 종료 교착 수정. 고정 Town03/V1 범위 FIXED_LIMITED | [일괄 검증](../test-plan/evidence/m7_carla_recovery/batch-closeout/README.md) |
| 독립 wall 감시 | 2ms/4ms 감시 → 로컬 보호 선택 → 다음 tick 차단. Terminal native owner는 입력 단절 뒤에도 보호 Actual 생성 | [wall guard](../test-plan/evidence/m7_carla_wall_guard/README.md) · [terminal 응답](../test-plan/evidence/m7_carla_wall_guard/terminal-response/README.md) |
| 증거 전달 최적화 | Raw solver journal 회수와 compact 전달을 분리하고 기존 physics/work/Actual 동등성 검증. 정상 wall timing 수용은 아님 | [전달 경로](../test-plan/evidence/m7_carla_wall_guard/pipeline/README.md) |
| Wall owner component | 실제 monotonic timer·분리된 IO·유한 mailbox, 원래8-role service와 보호·완료 work 정산 검증. 합성 stationary 입력 범위 | [component 실행](../test-plan/evidence/m7_carla_wall_guard/wall-owner/README.md) |
| 실제 CARLA wall 연결 | `wall5-hv50-v1`에서 파생 HV 예산을 분리한 뒤 정상2회·보호2회, 각900구간과 서버 종료 **4/4 통과**. 단기 비영상 한정이며 전체 실시간 수용은 OPEN | [HV 재조정·실행](../test-plan/evidence/m7_carla_wall_guard/carla-runtime/hv-budget-v1/README.md) · [이전 실패 보존](../test-plan/evidence/m7_carla_wall_guard/carla-runtime/nonvideo-wall5/README.md) |

이전 기능 시험의 정상5실행은 각각900구간, 약4.77215m 이동·최대 전방 속도 약1.259m/s다.
영상2실행은 각각 RGB180/GT180이다. Reference 30km/h 추종이나 전체 ODD 검증은 아니다.
마지막 wall 연결의 Normal/ASan 각113/113·TSan 경계26/26과 정상901/보호401개 replay 일치는
component/회귀 근거이며 실제 wall 주행 성공을 뜻하지 않는다.

## 남은 문제와 제한

| 항목 | 현재 처리 |
| --- | --- |
| 엔진 프레임 공백 | 최소 state 경로의10ms 요청1000구간은 source/공식 패키지 모두 최대 약10.83ms. RGB+GT에서는30ms 초과가 source200/1000·패키지17/1000으로 재현됨. 영상 경로의 지연 기여를 확인했으며 세부 blocking 원인은 미확정. 패키지 종료−11 실패 별도 보존. [대조 시험](../test-plan/evidence/m7_carla_wall_guard/carla-runtime/frame-diagnostic/README.md) |
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
상세 계약은 [시뮬레이션 시간 연속 실행](../interfaces/carla-plant-adapter.md#시뮬레이션-시간-연속-실행)에 있다.

M8 전 공통 controller/owner·CMake·감사 reader 정리를 완료했다. Normal/ASan 각1170/1170,
지정 TSan 경계36/36, Python201/201, 기존 감사 결과19개 일치와 정상901/보호401개
native replay를 확인했다. 실제 CARLA 회귀는4개 중3개 전체 통과, 정상 wall 주행1개는
900구간 검사 통과 후 UE 종료−11로 실패다. [변경·원본·한계](../test-plan/evidence/pre-m8-refactor/README.md)를
보존하며 M6/M7 수용 범위를 확대하지 않는다.

## M8 종료 조건

**M8 제어기·고정 fixture 기능 SIL 범위는 CLOSED**다. 원래 M8의 종방향 모델/C++
동등성, 실제 owner 경로의 속도 폐루프, Pure Pursuit와 고정 S01/S02/S03의30km/h
추종을 완료했다. 추가로 추진 포화 feedback·저속 고장 응답·30km/h NormalStop/HV-off를
검증했다. [종료 검토표](milestone-reviews.md#m8)가 각 조건과 원본 근거를 연결한다.

현재 code/test는 마지막 검증 source와 일치한다. C++1217개·Python237개·영향 범위
ASan/UBSan33개는 보존된 최종 실행 결과다. 이번 마감은 새 물리 시험 없이 근거·추적성·
source/hash를 검토했다. [마감 기록](../test-plan/evidence/m8_closeout/README.md)을 따른다.

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
[사전 protocol](../test-plan/longitudinal-equivalence-protocol.md)과
[실행 원본·분모·한계](../test-plan/evidence/m8_speed_pi/README.md)를 따른다.
`SpeedRequest`는 검증된 Drive Actual wheel source로 VehicleRequest를 만들고 기존
세션·permission·배분·보호·NormalStop 경로에 연결된다. 논리 시간 87초의
0→30→20→0km/h, 4,350회 제어가 통과했다. 실제 차량 plateau 최대 오차는
0.0497/0.0480/0km/h, 양수 목표 최대 overspeed는 1.291%다.
주행 중 Actual 손실·명령 중단도 기존 보호 경로와 실제 torque/brake 응답을 통과했다.
[프로토콜](../test-plan/speed-loop-protocol.md)과 [실행 근거·한계](../test-plan/evidence/m8_speed_loop/README.md)를 따른다.
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
[사전 protocol](../test-plan/carla-speed-protocol.md), [ADR-0069](design-decisions.md#adr-0069),
[원본·재현·한계](../test-plan/evidence/m8_carla_speed/README.md)에 기록했다.

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

[계약](../interfaces/lateral-route-controller.md), [사전 protocol/실패 이력](../test-plan/carla-route-protocol.md),
[원본·판정·재현](../test-plan/evidence/m8_route/README.md)을 따른다.
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

[사전 protocol와 v1 실패·v2 개정](../test-plan/carla-reference-protocol.md),
[원본·수치·재현](../test-plan/evidence/m8_reference/README.md),
[ADR-0071](design-decisions.md#adr-0071)을 따른다.
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
[Protocol](../test-plan/propulsion-saturation-protocol.md),
[원본·감사·재현](../test-plan/evidence/m8_saturation/README.md),
[ADR-0072](design-decisions.md#adr-0072)를 따른다.

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

[Protocol](../test-plan/carla-stop-protocol.md), [원본·판정·재현](../test-plan/evidence/m8_stop/README.md),
[ADR-0073](design-decisions.md#adr-0073)를 따른다. 인계 후 명시적 보호 요청과30km/h 감속/deadline 검토는 아래 후속 절을 따른다.
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

[Protocol](../test-plan/carla-stop-fault-protocol.md), [실행 근거](../test-plan/evidence/m8_stop_fault/README.md),
[30km/h 계약 검토](../test-plan/normal-stop-30-contract-review.md),
[ADR-0074](design-decisions.md#adr-0074)를 따른다. 별도30km/h fixture의
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

[사전 protocol](../test-plan/carla-stop30-protocol.md), [원본·감사·재현](../test-plan/evidence/m8_stop30/README.md),
[ADR-0075](design-decisions.md#adr-0075)를 따른다. 같은30km/h 참조의
timeout·입력 손실 및 ACK/통신 손실 고장별 실제 응답은 M9 후속이다. 고정 nominal 직선 수용이며
전체 Reference·Planner/localization·wall/Target와 UE renderer/GC 원인은 OPEN이다.


## 과거 실행 근거 찾기

## 대표 실행 결과

| 찾는 내용 | 실행 원본·재현 |
| --- | --- |
| M9 유한 event/DTC 집계·Linux journal·clear·queue TSan | [component 검증](../test-plan/evidence/m9_diagnostics_component/README.md) |
| M9 SpeedRequest/NormalStop 검출 hook·SimpleVehicle 입력 누락·원본 보호/Actual·DTC | [연결 검증](../test-plan/evidence/m9_control_hooks/README.md) |
| M9 SD-1001 입력 복원·INIT·Passed·명시적 clear·writer 재시작·재고장 | [연속 복구 검증](../test-plan/evidence/m9_speed_recovery/README.md) |
| M9 Zone/Leaf 소유자별 원본 검출·전달 구분·SD-2001/2002/4002 복구 | [소유자 경계 검증](../test-plan/evidence/m9_owner_sources/README.md) |
| M9 Gateway native/ACK/차량 응답·BMS/Power component 복구·registry2 | [native 원인 검증](../test-plan/evidence/m9_native_causes/README.md) |
| M9 BMS electrical/Power current 누락·차량 보호/정지/HV·새 INIT 복구 | [차량 입력 손실 검증](../test-plan/evidence/m9_native_vehicle/README.md) |
| M9 BMS9·Power3·동시3 센서 고장·8-role 보호/물리/DTC·복구 | [센서 matrix](../test-plan/evidence/m9_sensor_matrix/README.md) · [protocol](../test-plan/native-sensor-matrix-protocol.md) |
| M9 Release 전 Attempt·기동 ACK 누락·최초 deadline·실제 새 Release 복구 | [기동 진단 검증](../test-plan/evidence/m9_startup_sources/README.md) |
| M9 Event-only wire·유한 spool·commit 후 ACK 유실·송수신 process 재시작 | [전송·spool 검증](../test-plan/evidence/m9_delivery_spool/README.md) |
| M9 고정 source의 epoch 장벽·family·늦은 tail과 실제 SOME/IP 수집기 재시작 | [고정 집합 병합 검증](../test-plan/evidence/epoch-merge/README.md) |
| M9 실제 SOME/IP/TCP·새 logical source·live writer·ACK 유실/replica 재시작 | [SOME/IP 진단 검증](../test-plan/evidence/m9_someip_live/README.md) |
| M9 원격 accepted credit·Central 원본 context 대조·유한 대기·두 stream 독립 ACK | [원격 context component](../test-plan/evidence/m9_remote_context/README.md) |
| M9 실제 native3-ECU·context2/source9·원본 검출/ACK·TCP·merged journal | [native 진단 배선](../test-plan/evidence/m9_native_routing/README.md) |
| M9 진단 전달 객체 재개·원본 재전송·source/replica/merged SIGKILL 경계 | [전달 이력 복구](../test-plan/evidence/m9_delivery_restart/README.md) |
| M9 Front/Rear ECU process 재기동·새 발행자 세대·commit 전 손실 미확인 표시 | [발행자 adoption](../test-plan/evidence/m9_producer_adoption/README.md) |
| M9 Central process 재기동·trusted issuer 계승·fresh collector·연속성 clear 차단 | [Central 재기동 검증](../test-plan/evidence/m9_central_restart/README.md) |
| M9 미확인 과거 이력 수용·현재 recording proof·영속 서비스 심사/clear·writer SIGKILL4경계 | [로컬 서비스 심사](../test-plan/evidence/m9_continuity_review/README.md) |
| M9 서비스 명령 부모 순서·marker IO 분리·고정18개씩4회·TSan timing 미통과 | [원본·수정·남은 실패](../test-plan/evidence/m9_service_timing/README.md) · [사전 protocol](../test-plan/service-timing-protocol.md) |
| M9 응답 enqueue/RX 알림·monotonic 대기·SDK 시각·host 주파수와 전체 실패 보존 | [지연 후속](../test-plan/evidence/m9_response_latency/README.md) · [사전 protocol](../test-plan/service-response-protocol.md) |
| M9 보조 IO 물리 코어 분리·역할별 marker 조회·갱신 기한/종료 오류 보존 | [배치·관측 후속](../test-plan/evidence/m9_auxiliary_io/README.md) · [사전 protocol](../test-plan/auxiliary-io-protocol.md) |
| M9 입력 phase·현재 allocation release 검증·회차 불일치 수정 | [고정 후보별 원본·검증](../test-plan/evidence/m9_allocation_release/README.md) · [protocol](../test-plan/allocation-release-protocol.md) |
| M9 SDK SMT 배치 비교·미채택·실패 보존 | [고정30건](../test-plan/evidence/m9_sdk_smt/README.md) · [protocol](../test-plan/sdk-smt-protocol.md) |
| M9 관리 주기 사이 StopRequest 만료·SD-1105 원본·복수 원인 감사 | [poll·80건 재감사](../test-plan/evidence/m9_stop_deadline/README.md) · [protocol](../test-plan/stop-deadline-poll-protocol.md) |
| M9 지연 수신 grant의 due freshness와 현재 회차 support 분리 | [수정·고정 cohort](../test-plan/evidence/m9_deferred_grant/README.md) · [protocol](../test-plan/deferred-grant-protocol.md) |
| M9 물리 센서/출력 필드별 IO·동일 turn 출력 전달 | [고정42건·실패 보존](../test-plan/evidence/m9_plant_field_io/README.md) · [protocol](../test-plan/plant-field-io-protocol.md) |
| M9 연결 불가 egress·TxResult 우선 연결 | [선행 후보·원본27/30](../test-plan/evidence/m9_egress/README.md) · [protocol](../test-plan/egress-availability-protocol.md) |
| M9 SDK owner 코어 공유 비교·미채택·복원 | [고정30건23/30](../test-plan/evidence/m9_sdk_owner_core/README.md) · [protocol](../test-plan/sdk-owner-core-protocol.md) |
| M9 사용자 승인 서비스/성능·sanitizer 분리 판정 | [비계측18/18·ASan/TSan 각309](../test-plan/evidence/m9_validation_split/README.md) · [protocol](../test-plan/service-validation-protocol.md) |
| M9 proposal 이전 EpochStore/journal incident·기동 차단 | [실행·중단/재시도](../test-plan/evidence/m9_bootstrap/README.md) · [protocol](../test-plan/bootstrap-incidents-protocol.md) |
| M9 trusted Clock 복구·Power lifecycle5조건·유한 native 부하/보존 | [차량36건·원본/실패·고정 native cohort](../test-plan/evidence/m9_remaining/README.md) · [Clock](../test-plan/clock-recovery-protocol.md) · [Power](../test-plan/power-lifecycle-vehicle-protocol.md) · [soak](../test-plan/service-soak-protocol.md) · [보존](../test-plan/diagnostic-retention-protocol.md) |
| 실제3-process SOME/IP·8-role·부하/고장/재가입 | [M5 Rear adapter](../test-plan/evidence/m5_someip_rear_adapter/README.md) |
| M6 모델·Python MIL | [SimpleVehicle](../test-plan/evidence/m6_simple_vehicle/README.md) |
| M6 에너지·회로·물리 응답 최종 판정 | [물리 응답](../test-plan/evidence/m6_physical_response/README.md) · [이전 energy 실패 포함](../test-plan/evidence/m6_vehicle_energy/README.md) |
| M7 기능 주행·회생·제동·영상 | [통합 실행](../test-plan/evidence/m7_carla_integrated/README.md) |
| M7 시뮬레이션 시간 연속 주행·영상·보호·고장 7개 시험 | [연속 실행](../test-plan/evidence/m7_carla_integrated/simulation-time/README.md) |
| M7 보호 Actual·로딩 중 종료 | [Recovery](../test-plan/evidence/m7_carla_recovery/README.md) · [요청 인과 보완](../test-plan/evidence/m7_carla_recovery/causal-followup/README.md) |
| M7 보호 hold 정지·client-loss 종료 | [일괄 검증](../test-plan/evidence/m7_carla_recovery/batch-closeout/README.md) |
| Wall 감시·입력 단절 뒤 native 보호 | [wall guard](../test-plan/evidence/m7_carla_wall_guard/README.md) · [terminal 응답](../test-plan/evidence/m7_carla_wall_guard/terminal-response/README.md) |
| Solver 전달 분리·physics/work 동등성 | [Pipeline](../test-plan/evidence/m7_carla_wall_guard/pipeline/README.md) |
| Wall owner timer·IO component | [Wall owner](../test-plan/evidence/m7_carla_wall_guard/wall-owner/README.md) |
| 실제 CARLA wall10ms 연결 실패 | [CARLA runtime](../test-plan/evidence/m7_carla_wall_guard/carla-runtime/README.md) |
| 비영상 wall5ms 정상·보호 정지와 반복/종료 실패 | [비영상 wall 개선](../test-plan/evidence/m7_carla_wall_guard/carla-runtime/nonvideo-wall5/README.md) |
| CARLA HV source/dependency 예산 분리·정상2/보호2 실행 | [wall5-hv50-v1 결과](../test-plan/evidence/m7_carla_wall_guard/carla-runtime/hv-budget-v1/README.md) |
| CARLA 기본 state·영상·확장 경로 지연 대조 | [Frame 진단](../test-plan/evidence/m7_carla_wall_guard/carla-runtime/frame-diagnostic/README.md) |
| M8 전 공통 구현·빌드·감사 reader 정리와 회귀 | [리팩터링 검증](../test-plan/evidence/pre-m8-refactor/README.md) |
| M8 별도30km/h NormalStop·10s 제동 계약 | [실행 근거](../test-plan/evidence/m8_stop30/README.md) · [protocol](../test-plan/carla-stop30-protocol.md) |
| M8 정지 hold 이후 보호 전환·30km/h 예산 계약 검토 | [실행 근거](../test-plan/evidence/m8_stop_fault/README.md) · [protocol](../test-plan/carla-stop-fault-protocol.md) · [30km/h 검토](../test-plan/normal-stop-30-contract-review.md) |
| M8 저속 NormalStop/HV-off·현재 속도 입력 누락의 물리 정지 | [실행 근거](../test-plan/evidence/m8_stop/README.md) · [protocol](../test-plan/carla-stop-protocol.md) |
| M8 추진 배분 포화·참조 필요조건 | [실행 근거](../test-plan/evidence/m8_saturation/README.md) · [protocol](../test-plan/propulsion-saturation-protocol.md) |
| M8 S01 직선·S03 위치 기반30→20km/h·구동 포화 실패와 v2 | [실행 근거](../test-plan/evidence/m8_reference/README.md) · [protocol](../test-plan/carla-reference-protocol.md) |
| M8 고정 곡선30km/h·Pure Pursuit·pose 시각 불일치 | [실행 근거](../test-plan/evidence/m8_route/README.md) · [protocol](../test-plan/carla-route-protocol.md) |
| M8 CARLA V1 저속 속도 폐루프·원천/계산 시각·snapshot/work 누락 | [실제 CARLA 실행](../test-plan/evidence/m8_carla_speed/README.md) · [protocol](../test-plan/carla-speed-protocol.md) |
| M8 SimpleVehicle 속도 폐루프·Actual/명령 손실·NormalStop | [논리 시간 폐루프](../test-plan/evidence/m8_speed_loop/README.md) · [protocol](../test-plan/speed-loop-protocol.md) |
| M8 종방향 PI의 Python/C++ 출력·상태·고장/INIT 동등성 | [SpeedPI component](../test-plan/evidence/m8_speed_pi/README.md) · [사전 protocol](../test-plan/longitudinal-equivalence-protocol.md) |
| DDS 제어 gate CLOSED의 근거 | [DDS shutdown 후속](../test-plan/evidence/m5_dds_shutdown_followup/README.md) |

Linux 로컬 서비스 요청/심사/별도 clear는 [연결 근거](../test-plan/evidence/m9_continuity_service/README.md)와
[고정 recipe](../test-plan/diagnostics-protocol.md#linux-로컬-연속성-서비스-요청-fixture)를 따른다. [실제3-ECU terminal 서비스 조합](../test-plan/evidence/m9_native_service/README.md) 뒤 서비스 고장 거절을 후속 검증했으며, 최신 수용 범위는 [분리 판정](../test-plan/evidence/m9_validation_split/README.md), 전체 미완료 항목은 프로젝트 상태를 따른다.


## M10 정리 전 상세 기록

2026-11-12 문서 정리 시 `project-status.md`의 상세 경과를 이곳으로 통합했다.
아래 “현재/다음/미실행”은 각 실험 당시의 설명이다. 최신 판정과 작업 순서는
[현재 상태](../project-status.md)를 따른다. 원본 실행·실패·hash는 기존 evidence에 보존한다.

2026-11-10 사용자 지시에 따라 **현재는 Jetson 배포 가능성을 고려한 사전학습 모델 비교를
우선하고 보드별 최적화는 후속**으로 둔다. S는 초기 연동 기준이며 최적 모델로 확정하지 않았다.
5종의 같은 개발324장 비교에서는 L이 P94.23%/R88.57%로 가장 높은 F1을 보였으나,
개발 탐색·S 대비 P+2.85%p·기존 V6 보류 실패를 유지하므로 runtime을 교체하지 않는다.
새 학습·보류 재사용·보드 engine/양자화는 하지 않았다. [현재 판단과 다음 순서](../perception-model-selection.md)를 따른다.

후속 [V8 Town04 평가](../test-plan/evidence/m10_quality_v8/README.md)는 새 지도372곳의 첫 적격
7/25번을 사용했다. 공식 L의 새 개발 P93.55%/R89.92%는 절대·상대 PASS지만 새 보류
P79.65%/R69.77%·near person2/3과 보행자/이륜차 조건이 FAIL이다. 최초 준비198장(보류 가림 FAIL),
별도 종료 FAIL99장과 동일 조건 복구를 보존했다. 전체657개 raw pair·미래 제외4990개,
source237개·원본/점수·새 경로 재감사를 남겼다. 추가 학습이나 보드 최적화로 전환하지 않았고,
후속으로 개발 자료에서 사전학습 후보 비교를 확대했다.

[비교 V2](../test-plan/evidence/m10_model_screen_v2/README.md)는 S/L·RT-DETRv2-R18에
D-FINE-M·RT-DETRv4-S·공식 DAMO legacy를 추가했다. 개발324장에서8점 confidence를
비교하고 설정 봉인 뒤 Town04 개발81장을 확인했다. L만 앞선 도로와 Town04의 절대 기준을
모두 통과했고 과거 보류 실패는 유지한다. D-FINE은 Town04 P88.15%/R92.25%이나 앞선
도로 P78.28%가 FAIL이다. RT-DETRv4는 P94.10%/R83.53%이나 작은 person/bicycle
기준이 남았다. 전체 raw2430개·threshold19440세트·48개 calibration/12개 check 점수를
재생했다. 신규 RGB·새 보류·학습·보드 최적화 없이 미래 제외4990개와 기본 S를 유지한다.
후속 오류 분석과 후보 설정 고정을 완료했다.

[오류 분석](../test-plan/evidence/m10_model_diagnostics_v1/README.md)은 신뢰도0.50 미만의
맞는 박스가 대부분의 누락을 설명하며 D-FINE FP가 V4 반복 배경에 집중됨을 확인했다.
가중치·640 입력·native top300을 유지한 [클래스별 설정](../test-plan/evidence/m10_class_calibration_v1/README.md)은
모델당15,625개 조합을 개발324장에서 비교하고 설정 봉인 뒤 이미 소비한 Town04 개발81장을
regression했다. D-FINE은 FP129→40·calibration P92%/R89.15%, Town04 P89.84%/R89.15%로
두 절대 기준 PASS다. 상대 기준은 bus recall 감소·precision 향상2.93%p<3%p로 FAIL을 유지한다.
RT-DETRv4는 Town04 bicycle60%가 남아, 다음 새 품질 평가의 단일 개발 후보를 D-FINE의
클래스별 설정으로 고정했다. 최종 Reference/runtime 교체가 아니다. 이어서 새 protocol·준비와 V9 개발/보류 평가를 완료했다.


[V9 새 도로 평가](../test-plan/evidence/m10_quality_v9/README.md)는 지도만으로 미사용38/85번을
선정하고 기존 recipe·confidence와 모든 gate를 유지했다. D-FINE-M은 새 개발 P95.20%/
R92.25%로 절대·상대 PASS, 새 보류 P86.09%/R76.74%로 상대 PASS·절대 FAIL이다.
보류 person/motorcycle 각50%도 기준 미달이다. 최종 모델은 채택하지 않았고 S/M10 OPEN을
유지한다. 준비198장·평가162장과 종료 실패99장을 포함해459개 raw를 보존했고, 미래 RGB
제외는5449개다. 독립 수치6건·full model raw324개·원본/압축 새 source 감사를 연결했다.
다음은 개발 자료에서 작은 VRU/Rider 누락과 입력 해상도/사전학습 후보 효과를 검증하고
새 설정을 고정한 뒤 새 보류를 취득하는 일이다. 이번 보류를 설계/재선정에 사용하지 않는다.
신규 학습·보드 최적화는 실행하지 않았다.


[입력 해상도 비교와 car 후속](../test-plan/evidence/m10_resolution_v2/README.md)을 완료했다.
원래3종 수치 FAIL·cache reference 오류/복구·1280 탈락을 보존했다. 검증된640/960만 비교한
960 원래 vector는 V9 개발 car32/33→31/33 회귀로 거절했다. 별도 car confidence.70→.60
후속은486개 개발/설계에서 P95.15%/R91.34%·기존 품질/무회귀 기준을 통과했다.
V9 개발도 설계에 사용했으며 독립 보류가 아니다. 후보 `dfine-m-960-car-v1`을 고정했고 다음은
새 준비·개발·보류 평가다. Native6+후속3probe·원본/파생 raw 재감사·Python216개를 연결한다.
새 RGB·학습·보드 최적화·runtime 교체는 없으며 미래 제외5449개와 S/M10 OPEN을 유지한다.


[CARLA 원본 해상도 비교](../test-plan/evidence/m10_camera_resolution_v1/README.md)는 모델960과
confidence를 유지하고 source640×384부터3840×2304까지 실제 촬영했다.4K를 품질 평가 전에
기술 기준으로 고정했고, 같은 개발 배치 각81장에서640은P98.37%/R93.80%,4K는129TP/0FP/0FN이다.
수치15건 중14PASS/1FAIL과 종료 실패3쌍·사전 복구를 보존했다. 전체180쌍·미래 제외5629개다.
[4K source profile](../../profiles/perception-camera-source-candidates-v1.json)은 다음 새 평가용이며
기존 S/runtime640은 유지한다.4K 순차 health/resize/추론 P95 약93.64ms로 live20Hz는 미수용이다.
이후 native ingress/전처리 검증은 아래 후속 기록으로 이어진다. 새 준비·개발/보류와 전체 wall 수용은 남아 있다.
새 학습·보드 최적화·실제 Jetson 배포는 수행하지 않았다.

### M10 비동기 실행 후속

최신 [실제 비동기 월드 비교](../test-plan/evidence/m10_world_async_v1/README.md)는4K 인식용
서버 비동기·물리10ms 경로를 추가했다. 상태는 실제 `on_tick` snapshot으로만 갱신하고,
누락을 보간하지 않으며 상태100ms 침묵 시 오래된 결과를 무효화한다. 새 상태로 복귀해도
원래 acquisition/receipt100ms와 active1/pending1/current1을 유지한다.

동기1회/비동기2회는 각100장·다섯 구간 fresh 소비·정상 종료를 통과했다. 실제 카메라는
**12.35 / 11.30 / 12.13Hz**, primary 유효 조회는 **44.72 / 38.39 / 45.89%**다.
비동기 두 실행의 명시적 client tick은0회이며 실제 상태/관측은 추론과 독립 진행했다.
비동기가 빨라지거나 더 매끄러워졌다는 근거는 없다. 첫 비동기에는100ms 상태 침묵1회와
receipt late5회를 보존했고 결과를 연장하지 않았다. 물리10ms는 wall100Hz 보장이 아니다.

Python335개·C++/boundary12개씩 Debug/Release/ASan·report 변조36건 거절을 확인했다.
고정 source565개·실제 raw300장·exact native/Pillow 입력을 재감사하고 미래 제외는7013개다.
후속 작업은 async 상태/보호 경로의 unavailable 연결과 renderer/SDK 지연 분리 계측이다.
새 독립 품질·전체 wall20Hz·장기 운용·각 Jetson 전체 stack 배포는 남아 있으며, 보드 최적화는
후속으로 둔다. 기본 S/runtime640과 M10 OPEN을 유지한다.

앞선 [명시적 준비·주파수별 가용성·실제 반복 검증](../test-plan/evidence/m10_native_startup_v1/README.md)의 기준을 유지한다.
Native4K 추론 owner에 독립 합성3회 준비를 추가하고 같은 스레드로 센서 처리를 이어간다.
준비의 cold 비용/전체10s·2/3회100ms gate와 모든 결과를 별도 보존하며 synthetic 결과는 발행하지
않는다. READY는 초기화 완료이고 실제 perception availability/주행 permission이 아니다.

녹화 개발3장/6초에서10/13/20Hz 입력의50Hz 유효 조회 비율은 **42.33%/61.67%/99.00%**다.
258개 추론이 모두 기한 내 발행돼도 입력 간격 때문에 빈 구간이 남는다. 각1회·렌더링 제외이며
실측 지연도 다르므로 보편적10Hz 안전 판정으로 확대하지 않는다. SYS-PERF-002 Reference20Hz와
원래 source+100ms AND receipt+100ms를 유지한다. 실제 CARLA의 source/wall clock은 별개다.

실제 NVMe 기록 조건은240장/238발행/237소비, 유효 조회43.82%다. 원래 서버 시작180s 실패와
별도 복구 중8-slot 저장 overflow232장 FAIL은 그대로 보존한다. 후속 유한 Host 메모리 기록은
240장/최대8.49GB reference를 보관하고 측정 종료 후 압축한다. 이 진단 버퍼를 Jetson production
요구로 옮기지 않으며 inference latest1은 그대로다. 같은 조건의 두240장 실행은 저장 손실0으로
완료됐고 카메라 wall **11.71/11.32Hz**, primary 유효 조회 **44.42/43.41%**다.
각6개200-tick 구간의 fresh 소비와 source 정지 후 wall 만료를 확인했지만 공급 공백은 남았다.

Python318개·기존 C++/boundary12개씩 Debug/Release/ASan·source533→547→554와952개 전체
원본을 재감사했다. 모든 실제 입력 tensor/health는 기존 Pillow와 exact이며 미래 제외는6713개다.
실패한 V1에는 per-decision trace가 없어 해당 원인 재생을 주장하지 않고 원본/최종 counter를 보존한다.
후속 client는 실패 시에도 최종 decision trace를 저장한다. 이전 [CPU kernel·27개 fresh 근거](../test-plan/evidence/m10_native_kernel_v1/README.md)와
기존 live FAIL/품질 FAIL은 유지한다. 다음은 renderer/SDK source age·callback·관측 scheduling
분리 계측과 기존 상태/보호 경로의 unavailable 연결이다. 새 독립 품질·전체wall20Hz·장기 운용·
각 Jetson 전체 stack 배포가 남으며 기본 S/runtime640·M10 OPEN·보드 최적화 후속 원칙을 유지한다.

### M9 기능 범위 마감

[최종 근거](../test-plan/evidence/m9_followup/README.md)는 남아 있던 부하 시 명령 갱신과
silent Front packet loss의 실제 CARLA 응답을 검증했다. 명시적 SDK FIFO1은 기존 전용
CPU4/5/6에만 적용한다. 고정 기준1·quiet3·loaded3은 **7/7**, 뒤이은 서비스6조건×3회는
**18/18**이다. 서비스 고장12건은 실제 거절/무승인 commit0을 검증한 것이며 원래 runtime
FAIL을 성공한 서비스로 바꾸지 않는다. Owner 우선순위·20ms envelope·10ms 갱신/18ms
support·Front-before-Rear 의존과 원래 만료는 유지했다. 감사 대상404821개 요청의 관측 최대
왕복2.295638ms·최소 만료 여유17.704362ms는 이 유한 실행의 값이다.

CARLA는 기본 정상1·새 판정 정상1·silent loss2의 새 서버 실행 **4/4**를 통과했다.
각6000개 실제 physics/에너지 정산·6001개 native JSON 관측 재현·원본 DTC byte journal·
실제 body/4-wheel 정지·서버 종료130을 확인했다. Silent loss는 실제 gateway/Leaf 감시기의
SD-2001과 fresh torque/pressure/wheel을 연결한다. 서로 다른 producer의 event는 전체
run/producer/sequence와 occurrence로 연결하며 가짜 Central DTC를 만들지 않는다.

사용자가 허용한 수용 기준 조정은 명시적 `sampled-actual-v1`의 **10ms 물리 sample/hold**다.
Normal Command의 원래 권한은 현재 barrier에서 검사하고 Actual·wheel·permission·RunLease는
전체 다음10ms를 덮어야 한다. 구간 안의 원래 command 만료를 그대로 기록하고 native 감시기
기한도 유지한다. 다음 barrier에는 실제 native 결과가 필요하다. 기본 whole-interval·wall
판정과 보호 선택/새 LocalProtection Actual 조건은 유지한다. Subinterval 연속 물리 응답으로
해석하지 않는다. [사전 계약](../test-plan/carla-sampled-actual-protocol.md)을 따른다.

변경 CARLA component는 Release·Debug·ASan/UBSan·TSan 각각52개, 총208개를 통과했다.
Python54개와 잘못된 profile/실행 환경9조건 거절, 변경 C++ 정적 검사·UE 빌드도 확인했다.
실행기 가상환경 경로 오류의 준비 단계 실패·중단과 수정 전 component 실패도 분리 보존했다.
앞선 Clock/Power 복구·명시적 clear·비활성 journal archive/restore 근거와 합쳐 선언한 M9
기능 범위를 마감한다. Native4ms/wall·Target, 무제한 보존/자동 용량 회수, 다른 kernel의
Clock 운영과 학습자 review는 별도다. 과거 실패는 당시 분모와 함께 [보관 이력](implementation-history.md)에 유지한다.

### 이전 milestone 소프트웨어 후속

제동 배분 피드백을 PI의 음수 적분 보류까지 연결하고, journal data 쓰기 전에 영속적인
pending 의도를 남기도록 보강했다. 제동 용량/응답 보호·source/expiry·DTC 코드·명시적
clear 조건은 유지한다. 독립 모델 동등성, 실제 allocator 연결, 저장 오류/프로세스 중단과
복원 실패 경계·새 CARLA S03 8000구간은 [후속 검증](../test-plan/evidence/milestone-followup/README.md)에 기록한다.
저장된 S03의 native 재생과 새 서버 S03 실제 실행을 따로 기록했다. 실제 전원 차단/자동 용량 회수와
과거 timing·renderer 원인 규명을 완료한 것으로 올리지 않는다.

후속으로 [세션 경계 EpochRecorder](../interfaces/epoch-retention.md)의 활성 기록 창 회수·DTC 상태
이관과 CLI, [가용력 목표·M10 Host 속도 제안](../interfaces/supervised-speed-proposal.md)의
Supervisor→governor→기존 PI/배분 연결을 추가했다. [검증과 제한](../test-plan/evidence/remaining-improvements/README.md)을
따른다. 이어서 선택형 native speed 실행에 receiver BMS 가용력·원래 dependency·coordinator 보호·DTC를
연결했다. [연결 검증](../test-plan/evidence/runtime-speed-connection/README.md)을 별도로 보존한다.
기본 경로와 기존 milestone 증거는 유지하며 M7 전체 wall 연동은 사용자가 후순위로 두었다.

### 남은 문제와 제한

- Native4ms와 전체 wall 실시간 수용, 실차/Target 적합성은 별도다. 짧은 비영상
  `wall5-hv50-v1` 실행을 장시간·영상·고속 보장으로 확대하지 않는다.
- UE renderer/GC·로딩 중 종료와 일부 과거 서버 종료 실패의 근본 원인은 남아 있다.
  완료된 M9 네 서버의 정상 종료와 구분한다.
- 전체 Reference ODD, Planner/localization과 온라인 경사/저항 추정은 후속이다.
  BMS limits/wheel 기반 가용력과 governor·Supervisor는 선택형 native speed 경로에 연결했다.
  저항은 명시적 SIL 보정값이며 속도 경로에 학습 planner는 없다. M10 사전학습 인지 모델은 별도 영상 경계다. 새 SupervisedSpeed monitor의 qualified Passed와
  안전 정차 후 명시적 clear를 논리 SIL에서 연결했다. 입력 복구·재기동으로 DTC를 지우지 않는다.
  제동 피드백 v3는 component/원본 입력 재생과 새 고정 S03 실행을 통과했다. 전체 ODD 수용은 별도다.
- 기본512-event 경계, 비활성 archive/restore는 유한 운용이다. 새 EpochRecorder는 새 세션에서
  DTC 상태와 원본 이력을 보존하며 활성 창을 회수한다. Outbox/Inbox 및 전용 SOME/IP의 세션 전환·
  수신기 강제 종료/재시작을 연결했다. 고정 membership의 세션 순서 장벽과 ContextualOutbox family,
  실제 SOME/IP 원본 세 stream의 재시작 병합도 [검증](../test-plan/evidence/epoch-merge/README.md)했다.
  선택형 live 3-ECU 경로의 Front/Rear 교체와 Central spool도
  [검증](../test-plan/evidence/native-epoch-replacement/README.md)했다. 역할별 stream을 고정하고
  실제 새 INIT에서 producer 세대를 전환한다. [Central 프로세스 교체](../test-plan/evidence/central-epoch-replacement/README.md)도
  같은 family에 연결했다. [Terminal service의 family 적용](../test-plan/evidence/service-carla-recovery/README.md)까지 완료했다.
  단일 epoch 무중단 회전, 디스크 삭제/외부 보존 정책과
  전체 매체/전원 장애, 다른 kernel의 Clock 운영은 별도다. syscall 저장 오류와 프로세스
  중단 검증은 추가했지만 실제 전원 차단/캐시 소실 시험을 대신하지 않는다.
- 과거 M3/M4·SDK timing/sanitizer 실패와 미채택 후보는 당시 분모로 보존한다.
  최신 환경 probe에서도 FIFO는 가능하나 tracefs/perf 접근이 차단되고 비대화형 sudo 권한이 없다.
  따라서 과거 timer→wakeup→switch/IRQ 원인을 새로 규명한 것으로 올리지 않는다.
  기술 검사 통과로 학습자 설명·최종 수용을 대신하지 않는다.
- M10 실제 검출에서 원거리/가림 미검출과 오검출을 관측했다. 현재 CPU 프로파일은20Hz 전체
  처리량에 미달하고 일부 실행에서100ms miss도 발생했다. 선택형 RTX3090 CUDA의 동일 FP32
  수치·box 동등성과 처리 시간 개선을 확인했다. Cold call의100ms miss를 원래 기록에 남기고,
  별도 startup3회·준비 gate를 추가했다. 준비 후20Hz media600frame 처리와 실제 CARLA/CUDA
  공유 GPU shadow·고장4조건을 검증했다. 실제 camera wall rate는20Hz에 미달한다.
  Late/drop/exception은 가용성 상실로 기록한다. 초기 카메라 설정의 검은 하늘·경고 overlay는
  RGB postprocess를 켠 후속 표본에서 해소했으나 정확도·ODD 품질·장기 renderer 안정성은 미수용이다.
  2D track은 거리·상대 속도·risk가 아니며, 인지 수신 가용성 회복이 차량 permission을 열지 않는다.
- M10 확장 정확도는6종 객체·3기상·개발/보류 각81배치로 비교하고 잠정 gate를 사전 고정했다.
  차량 중복 억제·중앙 확대 후보 모두 미채택이다. V1 정답이 CARLA Rider13을 누락했음을
  원본 mask에서 확인하여 별도 v2 생성기·검사를 추가했다. 기존 점수·실패는 보존하며,
  이미 본 데이터의 v2 재계산은 사후 진단이다. 새로운 사전 고정 평가를 통과한 것으로 세지 않는다.
- 이후 [Rider v2의 새162배치](../test-plan/evidence/m10_quality_v2/README.md)를 별도 freeze로
  수집·평가했다. 실제 settling 뒤204개 actor pose와 원본/정답 재구성을 확인했다. 확대 후보는
  재현율을 높였지만 차량 종류 오분류가 늘어 미채택이다. 보류셋의 원거리/가림 보행자6개가
  최소 지원에 미달하여 coverage도 FAIL이다. 호환되지 않는 다축 truck spawn의 서버 crash와
  미완성20pair는 따로 보존했고, 추론 전 호환 asset으로 수정한 계획으로 전체 재수집했다.

- 이후 [V3의 별도 준비·S/M 새 비교](../test-plan/evidence/m10_quality_v3/README.md)를 완료했다.
  첫 준비의 가림 보행자3개 지원 미달을 추론 전 수정해180장 준비를 통과했다. M 확대는 개발
  P94.6%/R95.3%로 절대 기준을 통과했으나 빈 배경 FP 증가로 상대 기준은 실패했다. 보류는
  P79.8→81.5%/R58.8→85.1%로 개선됐지만 정밀도·truck R·coverage가 실패해 미채택이다.
  별도 준비 site와 다른 보류 위치의 far9개 가시성 부족을 유지했고, 사후 모든 site 지도 검사에서
  보류 far18개의 계획 XY가 가까운 차로/보도에서5.9–10.4m 벗어났음을 확인했다. 이 결과로 후속 준비의
  실제 모든 site geometry/가시성 검사를 요구했다. 서버 종료30초 초과의 전체 FAIL과 동일
  설정 재수집도 보존했으며 renderer 원인을 해결하거나 live20Hz를 수용한 것으로 올리지 않는다.

- [V4 실제 site 도로 맞춤 준비](../test-plan/evidence/m10_road_preparation_v4/README.md)는
  waypoint의 위치·높이·방향을 사용하고 경로 전체 junction/시야/차로를 검사한다.14/24번 site에서
  최종 준비198장과 계획 actor/rider 가시성·부분 가림 참조를 통과했다. 초기 교차로 lane 거절과
  held walker31m24pixel의 실패를 보존했다. 해당 작은 보행자의 미래 far를26m로 한정하고
  준비27m에서30pixel을 확인했다. 미래 평가162개 계획·제외 목록을 봉인했으며 이번 단계의
  모델 추론/정확도 평가는 NOT RUN이었다. 이후 아래 새 평가에서 실제 coverage를 별도로 확인했다.

- [V4 도로 맞춤 새 정확도 평가](../test-plan/evidence/m10_quality_v4/README.md)는 이전1711개 RGB를
  제외하고 새 개발/보류 각81개를 수집했다. 모든 계획 actor/rider와6class×4조건3/3 coverage를
  통과했으나, 지명 M의 보류 P75.9%/R65.9%와 클래스 gate·상대 기준이 FAIL이라 미채택이다.
  보류 M FP27개 중26개는 다른 클래스의 visible GT와 겹쳤다. 작은 VRU/rider·이륜차/차종 구분이
  다음 개선 과제다. 시작 제한2건·종료 실패2건과 별도 진단·metadata 연결 오류를 보존하고,
  raw→준비→점수 회귀를 추가한 새 freeze로 재수집했다. 최종 원본 재감사 PASS와118개 Python·
  설정별13개 component 검사 PASS를 품질 수용과 구분한다. 미래 재사용 금지 목록은1873개다.

- [V5 VRU 다중 시야 후보·새 도로 평가](../test-plan/evidence/m10_quality_v5/README.md)는 소비된 V4
  개발 자료에서 정책을 설계하고 새31/35번에서 준비198장·평가162개를 검사했다. 새 개발의
  consensus P97.5%/R90.7%는 절대·상대 PASS, 보류 P84.5%/R67.4%는 FAIL이다. 보류 FP는
  S32→16·rider TP18→23으로 개선됐으나 truck/far recall이 낮아져 기존 S를 유지했다.
  시작 실패와 임시 spawn 충돌을 원본/source와 보존하고 staging 수정 뒤 전체 재수집했다.
  Python129개·설정별 component13개·수치/원본/압축 재감사 PASS이며 미래 제외는2357개다.

- [V6 고정 L 모델·새 도로 평가](../test-plan/evidence/m10_quality_v6/README.md)는74/80번 준비198장·
  평가162개와 별도152-source freeze를 사용했다. L 원본의 개발 P95.8%/R87.6% 절대·상대는
  PASS다. Context는 절대 PASS지만 truck recall 무하락을 실패해 미지명했다. 지명 L의 새 보류는
  P81.6%/R62.0%와 near person·far 조건이 FAIL이라 기존 S를 유지한다. 보류 truck→bus FP12개를
  관측했다. Python139개·설정별13개·수치/원본/압축 재감사 PASS와 모델 품질 수용을 구분한다.
  미래 RGB 제외는2717개이며 다양한 시야·조명·차종의 전용 개발/학습 자료 확보가 다음 과제다.

- [전용 개발·학습 데이터](../test-plan/evidence/m10_domain_data_v1/README.md)는 자산 사전176장과
  새 Train813/validation267장을 수집했다.4class blueprint·road/RGB/family를 분리하고 bus/truck
  공유를 명시했다. 작은 visible 조각도 양성으로 보존한 PNG·COCO·typed reader를 구현했다.
  가림 부족과 시작 실패를 유지하고 추가 수집 후 사전 split coverage를 통과했다. 모델 학습/추론은
  실행하지 않았다. Python148개·설정별13개·공식 COCO API·원본/압축 재감사 PASS다.
  미래 RGB 제외는3973개이며127번 quality holdout 후보는 미수집이다.

- [첫 L6 학습 후보](../test-plan/evidence/m10_training_v1/README.md)는 train813장·24epoch·4896step의
  실제 FP32 CUDA 학습과 validation267장의 고정 지표 선택을 마쳤다. Epoch17의 개발 정밀도
  93.84%/재현율90.05%·macro F190.55%다.80-class 초기 checkpoint와
  6-class 이식 직후를 따로 기록했다. 새 ONNX[1,8400,11]·native 매핑·CPU/CUDA/OpenCV16probe,
  ONNX CPU/CUDA267장 재추론·원본 선택/tensor·압축 재감사를 통과했다. Python156개·설정별13개와
  이전10묶음 무결성도 PASS다. 이 validation은 checkpoint 선택용 개발 자료이며 새 quality holdout은
  미수집·미평가다. 기존 S/정확도 FAIL·M10 OPEN과 향후 RGB3973개 제외를 유지한다.

- [V7 고정 L6·새 도로 평가](../test-plan/evidence/m10_quality_v7/README.md)는 준비198장·개발215/보류127번
  각81장과 source200개를 봉인했다. 개발 P92.19%/R91.47%·
  bus recall60%로 absolute/relative FAIL이다. 보류 P91.23%/R80.62%·
  absolute FAIL/relative FAIL이다. 원래 기준과 실패를 유지하고
  기본 S를 교체하지 않았다. 개발 시작2회는0frame·exit-9 FAIL이며 동일 source/plan/budget의
  별도 복구 편차도 남겼다. Python161개·설정별13개·수치/원본/압축 재감사·이전11묶음 무결성
  PASS와 model quality 판정을 구분한다. 미래 RGB 제외는4333개다.

### 다음 작업

M10의 상태 기반 Host 속도 제안 입출력·history·risk·fallback 경계는 첫 프로파일로 고정했다.
[감독 DTC의 qualified 복구·해제와 EpochRecorder 송수신 연결](../test-plan/evidence/supervised-recovery-delivery/README.md)을 추가했다.
고정 송신원 집합의 [세션 순서 장벽과 family 병합](../test-plan/evidence/epoch-merge/README.md)을 추가했다.
이어서 [live Front/Rear 교체·Central spool·원본 prefix 재전송](../test-plan/evidence/native-epoch-replacement/README.md)을
연결했다. [Central 교체와 세션 발행자 승계](../test-plan/evidence/central-epoch-replacement/README.md)까지
검증했다. 이어서 [terminal service의 family 적용과 실제 CARLA 복구 주행](../test-plan/evidence/service-carla-recovery/README.md)을
연결했다. 같은 차량·물리/EV 상태를 유지한 실제 새 INIT, 관측·NoDrive 권한 전환과 qualified Passed를
확인했다. 이 두 후속 항목까지 이번 마감 범위는 완료이며, 아래 확장 범위를 M9 종료 조건에 추가하지 않는다.
M10의 모델 고정·RGB 추론·2D 이력·session/clock/timeout·실제 CARLA 정답 분리 평가를
[첫 Host 인지 묶음](../test-plan/evidence/m10_perception/README.md)으로 추가했다.
[후속 묶음](../test-plan/evidence/m10_live_perception/README.md)은 startup 준비/가용성 gate, bounded
실제 카메라 ingress, 공유 GPU shadow, source 정지 시 wall expiry, 원래 frame 기준 취득과
RGB 렌더 설정을 보강했다. 이어서 [정확도 확장 묶음](../test-plan/evidence/m10_quality/README.md)에서
6class·3기상·162배치·잠정 gate·후보2종과 별도 보류 평가를 구현했다. 두 후보의 회귀와 Rider
annotation 누락을 발견했고 기본 모델/threshold를 유지했다. 이어서
[사전 고정한 v2 새 평가](../test-plan/evidence/m10_quality_v2/README.md)에서 Rider 정답·strict
visible box·조건별 coverage와 두 확대 후보를 검증했다. 이후 [V3 준비·S/M 비교](../test-plan/evidence/m10_quality_v3/README.md)에서 별도 준비180장과 새 평가162개를 실행했다.
M 확대는 개발의 절대 기준을 통과했지만 빈 배경 FP 증가와 보류의 정밀도·truck recall·coverage가
실패해 미채택이다. [실제 두 site의 V4 도로 준비](../test-plan/evidence/m10_road_preparation_v4/README.md)를
마친 뒤 [V4 새 평가](../test-plan/evidence/m10_quality_v4/README.md)에서 실제 coverage와 품질을
검사했다. [V5 다중 시야 개선](../test-plan/evidence/m10_quality_v5/README.md)은 새 개발 기준을 통과했으나 새 보류가 실패했다. [V6 L 모델·새 평가](../test-plan/evidence/m10_quality_v6/README.md)도 개발 기준을 통과했지만 보류 기준은 실패했다. 다음은 **소비한 개발 자료의 bus/truck 구분·정밀도 회귀 개선 → 새 후보·다시 새 보류 →
전체wall20Hz·시작/종료 안정성**이다. 준비 영상은 미래 정확도 표본으로 재사용하지 않으며,
작은 held 보행자의 far26m 범위와 별도 quality freeze·실제 평가 coverage 검사를 유지한다.
새 plan을 고정하기 전에 가시성을 확인하고, 이미 본 v1/v2/v3/v4/v5/v6/v7/v8/v9 보류셋과 준비/실패/진단 영상을 새로운 holdout으로 재사용하지 않는다.
같은 Town의 정지 배치를 전체 ODD로 확대하지 않는다.
그 뒤 M11에서 metric fusion/localization·temporal planner 입력·risk·valid classical fallback을
정의하고 기존 감독/제어 경로에 연결한다. 온라인 저항 추정은 별도다.
구체 산출물과 TBD 담당·결정 시점은 [로드맵](../roadmap.md)에서 관리한다.
진행한 시도별 상세 경과와 과거 실행 목록은 [구현·검증 이력](implementation-history.md)에서 찾는다.
