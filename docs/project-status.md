# 프로젝트 상태

정리 기준·최신 검증: **2026-11-10**.
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
| M9 | **선언한 유한 Host·simulation10ms 기능 범위 CLOSED / wall·Target·장기 운용 별도** | [진단 계약](interfaces/diagnostics.md) · [마감 검증·원본·제한](test-plan/evidence/m9_followup/README.md) |
| M10 | **Host 인지·live shadow·L6/V7 및 사전학습5종 개발324장 비교 완료 / 모델 최종 선정·정확도·전체wall20Hz·시작 안정성·주행 통합 OPEN** | [모델 선정 순서](perception-model-selection.md) · [5종 개발 비교](test-plan/evidence/m10_model_screen_v1/README.md) · [V7 실패 보존](test-plan/evidence/m10_quality_v7/README.md) |
| M11 | 상태 속도 제안·BMS 가용력·native 보호 연결; temporal learned planner·metric world model NOT RUN | [제안 계약](interfaces/supervised-speed-proposal.md) · [로드맵](roadmap.md) |
| M12–M13 | PLANNED / NOT RUN | [로드맵](roadmap.md) |

기술 검사와 학습자 설명·수용은 별도다. Component PASS를 전체 system/Target PASS로 올리지 않는다.

2026-11-10 사용자 지시에 따라 **현재는 Jetson 배포 가능성을 고려한 사전학습 모델 비교를
우선하고 보드별 최적화는 후속**으로 둔다. S는 초기 연동 기준이며 최적 모델로 확정하지 않았다.
5종의 같은 개발324장 비교에서는 L이 P94.23%/R88.57%로 가장 높은 F1을 보였으나,
개발 탐색·S 대비 P+2.85%p·기존 V6 보류 실패를 유지하므로 runtime을 교체하지 않는다.
새 학습·보류 재사용·보드 engine/양자화는 하지 않았다. [현재 판단과 다음 순서](perception-model-selection.md)를 따른다.

## M9 기능 범위 마감

[최종 근거](test-plan/evidence/m9_followup/README.md)는 남아 있던 부하 시 명령 갱신과
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
해석하지 않는다. [사전 계약](test-plan/carla-sampled-actual-protocol.md)을 따른다.

변경 CARLA component는 Release·Debug·ASan/UBSan·TSan 각각52개, 총208개를 통과했다.
Python54개와 잘못된 profile/실행 환경9조건 거절, 변경 C++ 정적 검사·UE 빌드도 확인했다.
실행기 가상환경 경로 오류의 준비 단계 실패·중단과 수정 전 component 실패도 분리 보존했다.
앞선 Clock/Power 복구·명시적 clear·비활성 journal archive/restore 근거와 합쳐 선언한 M9
기능 범위를 마감한다. Native4ms/wall·Target, 무제한 보존/자동 용량 회수, 다른 kernel의
Clock 운영과 학습자 review는 별도다. 과거 실패는 당시 분모와 함께 [보관 이력](archive/implementation-history.md)에 유지한다.

## 이전 milestone 소프트웨어 후속

제동 배분 피드백을 PI의 음수 적분 보류까지 연결하고, journal data 쓰기 전에 영속적인
pending 의도를 남기도록 보강했다. 제동 용량/응답 보호·source/expiry·DTC 코드·명시적
clear 조건은 유지한다. 독립 모델 동등성, 실제 allocator 연결, 저장 오류/프로세스 중단과
복원 실패 경계·새 CARLA S03 8000구간은 [후속 검증](test-plan/evidence/milestone-followup/README.md)에 기록한다.
저장된 S03의 native 재생과 새 서버 S03 실제 실행을 따로 기록했다. 실제 전원 차단/자동 용량 회수와
과거 timing·renderer 원인 규명을 완료한 것으로 올리지 않는다.

후속으로 [세션 경계 EpochRecorder](interfaces/epoch-retention.md)의 활성 기록 창 회수·DTC 상태
이관과 CLI, [가용력 목표·M10 Host 속도 제안](interfaces/supervised-speed-proposal.md)의
Supervisor→governor→기존 PI/배분 연결을 추가했다. [검증과 제한](test-plan/evidence/remaining-improvements/README.md)을
따른다. 이어서 선택형 native speed 실행에 receiver BMS 가용력·원래 dependency·coordinator 보호·DTC를
연결했다. [연결 검증](test-plan/evidence/runtime-speed-connection/README.md)을 별도로 보존한다.
기본 경로와 기존 milestone 증거는 유지하며 M7 전체 wall 연동은 사용자가 후순위로 두었다.

## 현재 구현과 수용 경계

| 영역 | 현재 범위 | 상세 근거 |
| --- | --- | --- |
| 통신·세션 | Central/Front/Rear 3-process SOME/IP, 8-role INIT/Release/RunLease, 원래 source/expiry와 새 Epoch 재가입 | [SOME/IP 계약](interfaces/someip-rear-adapter.md) |
| 모델·제어 | 독립 종방향 MIL, C++ 모델 동등성, 고정 속도·경로 fixture, 방향별 배분 포화 피드백과 정상 정지/HV-off | [M8 종료 검토](archive/milestone-reviews.md#m8) |
| CARLA | 원본 CAN/P05 Actual의 NoDrive 적용, solver work의 단일 EV 정산, simulation-time 기능 | [Plant 계약](interfaces/carla-plant-adapter.md) · [실행 안내](carla-guide.md) |
| 진단 | 원본 검출·인과 ID·보호·Actual·DTC, qualified 복구와 명시적 clear, 재기동/연속성 심사 | [진단 계약](interfaces/diagnostics.md) |
| 기록 보존 | 유한 journal, 비활성 store의 독점 잠금 archive/restore, byte 동일한 이력 복원 | [보존 계약](test-plan/diagnostic-retention-protocol.md) |
| 영상 인지 | 고정 YOLOX-S FP32 CPU·선택형 CUDA, RGB-only·2D 검출/tracking·queue/expiry·C++ 검증, GT 분리 평가 | [영상 계약](interfaces/perception.md) · [실행 근거](test-plan/evidence/m10_perception/README.md) |

문서 이력과 공통 진단 발행기·감사 decoder를 정리한 뒤의 동등성·회귀 검증은
[M9 이후 구조 정리 근거](test-plan/evidence/post-m9-refactor/README.md)를 따른다.

## 남은 문제와 제한

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
  실제 SOME/IP 원본 세 stream의 재시작 병합도 [검증](test-plan/evidence/epoch-merge/README.md)했다.
  선택형 live 3-ECU 경로의 Front/Rear 교체와 Central spool도
  [검증](test-plan/evidence/native-epoch-replacement/README.md)했다. 역할별 stream을 고정하고
  실제 새 INIT에서 producer 세대를 전환한다. [Central 프로세스 교체](test-plan/evidence/central-epoch-replacement/README.md)도
  같은 family에 연결했다. [Terminal service의 family 적용](test-plan/evidence/service-carla-recovery/README.md)까지 완료했다.
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
- 이후 [Rider v2의 새162배치](test-plan/evidence/m10_quality_v2/README.md)를 별도 freeze로
  수집·평가했다. 실제 settling 뒤204개 actor pose와 원본/정답 재구성을 확인했다. 확대 후보는
  재현율을 높였지만 차량 종류 오분류가 늘어 미채택이다. 보류셋의 원거리/가림 보행자6개가
  최소 지원에 미달하여 coverage도 FAIL이다. 호환되지 않는 다축 truck spawn의 서버 crash와
  미완성20pair는 따로 보존했고, 추론 전 호환 asset으로 수정한 계획으로 전체 재수집했다.

- 이후 [V3의 별도 준비·S/M 새 비교](test-plan/evidence/m10_quality_v3/README.md)를 완료했다.
  첫 준비의 가림 보행자3개 지원 미달을 추론 전 수정해180장 준비를 통과했다. M 확대는 개발
  P94.6%/R95.3%로 절대 기준을 통과했으나 빈 배경 FP 증가로 상대 기준은 실패했다. 보류는
  P79.8→81.5%/R58.8→85.1%로 개선됐지만 정밀도·truck R·coverage가 실패해 미채택이다.
  별도 준비 site와 다른 보류 위치의 far9개 가시성 부족을 유지했고, 사후 모든 site 지도 검사에서
  보류 far18개의 계획 XY가 가까운 차로/보도에서5.9–10.4m 벗어났음을 확인했다. 이 결과로 후속 준비의
  실제 모든 site geometry/가시성 검사를 요구했다. 서버 종료30초 초과의 전체 FAIL과 동일
  설정 재수집도 보존했으며 renderer 원인을 해결하거나 live20Hz를 수용한 것으로 올리지 않는다.

- [V4 실제 site 도로 맞춤 준비](test-plan/evidence/m10_road_preparation_v4/README.md)는
  waypoint의 위치·높이·방향을 사용하고 경로 전체 junction/시야/차로를 검사한다.14/24번 site에서
  최종 준비198장과 계획 actor/rider 가시성·부분 가림 참조를 통과했다. 초기 교차로 lane 거절과
  held walker31m24pixel의 실패를 보존했다. 해당 작은 보행자의 미래 far를26m로 한정하고
  준비27m에서30pixel을 확인했다. 미래 평가162개 계획·제외 목록을 봉인했으며 이번 단계의
  모델 추론/정확도 평가는 NOT RUN이었다. 이후 아래 새 평가에서 실제 coverage를 별도로 확인했다.

- [V4 도로 맞춤 새 정확도 평가](test-plan/evidence/m10_quality_v4/README.md)는 이전1711개 RGB를
  제외하고 새 개발/보류 각81개를 수집했다. 모든 계획 actor/rider와6class×4조건3/3 coverage를
  통과했으나, 지명 M의 보류 P75.9%/R65.9%와 클래스 gate·상대 기준이 FAIL이라 미채택이다.
  보류 M FP27개 중26개는 다른 클래스의 visible GT와 겹쳤다. 작은 VRU/rider·이륜차/차종 구분이
  다음 개선 과제다. 시작 제한2건·종료 실패2건과 별도 진단·metadata 연결 오류를 보존하고,
  raw→준비→점수 회귀를 추가한 새 freeze로 재수집했다. 최종 원본 재감사 PASS와118개 Python·
  설정별13개 component 검사 PASS를 품질 수용과 구분한다. 미래 재사용 금지 목록은1873개다.

- [V5 VRU 다중 시야 후보·새 도로 평가](test-plan/evidence/m10_quality_v5/README.md)는 소비된 V4
  개발 자료에서 정책을 설계하고 새31/35번에서 준비198장·평가162개를 검사했다. 새 개발의
  consensus P97.5%/R90.7%는 절대·상대 PASS, 보류 P84.5%/R67.4%는 FAIL이다. 보류 FP는
  S32→16·rider TP18→23으로 개선됐으나 truck/far recall이 낮아져 기존 S를 유지했다.
  시작 실패와 임시 spawn 충돌을 원본/source와 보존하고 staging 수정 뒤 전체 재수집했다.
  Python129개·설정별 component13개·수치/원본/압축 재감사 PASS이며 미래 제외는2357개다.

- [V6 고정 L 모델·새 도로 평가](test-plan/evidence/m10_quality_v6/README.md)는74/80번 준비198장·
  평가162개와 별도152-source freeze를 사용했다. L 원본의 개발 P95.8%/R87.6% 절대·상대는
  PASS다. Context는 절대 PASS지만 truck recall 무하락을 실패해 미지명했다. 지명 L의 새 보류는
  P81.6%/R62.0%와 near person·far 조건이 FAIL이라 기존 S를 유지한다. 보류 truck→bus FP12개를
  관측했다. Python139개·설정별13개·수치/원본/압축 재감사 PASS와 모델 품질 수용을 구분한다.
  미래 RGB 제외는2717개이며 다양한 시야·조명·차종의 전용 개발/학습 자료 확보가 다음 과제다.

- [전용 개발·학습 데이터](test-plan/evidence/m10_domain_data_v1/README.md)는 자산 사전176장과
  새 Train813/validation267장을 수집했다.4class blueprint·road/RGB/family를 분리하고 bus/truck
  공유를 명시했다. 작은 visible 조각도 양성으로 보존한 PNG·COCO·typed reader를 구현했다.
  가림 부족과 시작 실패를 유지하고 추가 수집 후 사전 split coverage를 통과했다. 모델 학습/추론은
  실행하지 않았다. Python148개·설정별13개·공식 COCO API·원본/압축 재감사 PASS다.
  미래 RGB 제외는3973개이며127번 quality holdout 후보는 미수집이다.

- [첫 L6 학습 후보](test-plan/evidence/m10_training_v1/README.md)는 train813장·24epoch·4896step의
  실제 FP32 CUDA 학습과 validation267장의 고정 지표 선택을 마쳤다. Epoch17의 개발 정밀도
  93.84%/재현율90.05%·macro F190.55%다.80-class 초기 checkpoint와
  6-class 이식 직후를 따로 기록했다. 새 ONNX[1,8400,11]·native 매핑·CPU/CUDA/OpenCV16probe,
  ONNX CPU/CUDA267장 재추론·원본 선택/tensor·압축 재감사를 통과했다. Python156개·설정별13개와
  이전10묶음 무결성도 PASS다. 이 validation은 checkpoint 선택용 개발 자료이며 새 quality holdout은
  미수집·미평가다. 기존 S/정확도 FAIL·M10 OPEN과 향후 RGB3973개 제외를 유지한다.

- [V7 고정 L6·새 도로 평가](test-plan/evidence/m10_quality_v7/README.md)는 준비198장·개발215/보류127번
  각81장과 source200개를 봉인했다. 개발 P92.19%/R91.47%·
  bus recall60%로 absolute/relative FAIL이다. 보류 P91.23%/R80.62%·
  absolute FAIL/relative FAIL이다. 원래 기준과 실패를 유지하고
  기본 S를 교체하지 않았다. 개발 시작2회는0frame·exit-9 FAIL이며 동일 source/plan/budget의
  별도 복구 편차도 남겼다. Python161개·설정별13개·수치/원본/압축 재감사·이전11묶음 무결성
  PASS와 model quality 판정을 구분한다. 미래 RGB 제외는4333개다.

## M7 종료 조건

시뮬레이션 시간 기능 범위는 CLOSED다. 연속 주행·회생/제동·영상·보호와 고장7조건의
[원본 및 독립 감사](test-plan/evidence/m7_carla_integrated/simulation-time/README.md)를 기준으로 한다.
Wall/Target과 전체 renderer 안정성은 별도이며 [당시 종료 검토](archive/implementation-history.md#m7-종료-조건)에 보존한다.

## M8 종료 조건

제어기·고정 fixture 기능 SIL 범위는 CLOSED다. 모델/C++ 동등성, 속도/경로 폐루프,
고정30km/h fixture·추진 포화·정상 정지를 [종료 검토](archive/milestone-reviews.md#m8)와
[마감 무결성](test-plan/evidence/m8_closeout/README.md)으로 확인했다. 전체 Reference·wall·Target은 별도다.

## 다음 작업

M10의 상태 기반 Host 속도 제안 입출력·history·risk·fallback 경계는 첫 프로파일로 고정했다.
[감독 DTC의 qualified 복구·해제와 EpochRecorder 송수신 연결](test-plan/evidence/supervised-recovery-delivery/README.md)을 추가했다.
고정 송신원 집합의 [세션 순서 장벽과 family 병합](test-plan/evidence/epoch-merge/README.md)을 추가했다.
이어서 [live Front/Rear 교체·Central spool·원본 prefix 재전송](test-plan/evidence/native-epoch-replacement/README.md)을
연결했다. [Central 교체와 세션 발행자 승계](test-plan/evidence/central-epoch-replacement/README.md)까지
검증했다. 이어서 [terminal service의 family 적용과 실제 CARLA 복구 주행](test-plan/evidence/service-carla-recovery/README.md)을
연결했다. 같은 차량·물리/EV 상태를 유지한 실제 새 INIT, 관측·NoDrive 권한 전환과 qualified Passed를
확인했다. 이 두 후속 항목까지 이번 마감 범위는 완료이며, 아래 확장 범위를 M9 종료 조건에 추가하지 않는다.
M10의 모델 고정·RGB 추론·2D 이력·session/clock/timeout·실제 CARLA 정답 분리 평가를
[첫 Host 인지 묶음](test-plan/evidence/m10_perception/README.md)으로 추가했다.
[후속 묶음](test-plan/evidence/m10_live_perception/README.md)은 startup 준비/가용성 gate, bounded
실제 카메라 ingress, 공유 GPU shadow, source 정지 시 wall expiry, 원래 frame 기준 취득과
RGB 렌더 설정을 보강했다. 이어서 [정확도 확장 묶음](test-plan/evidence/m10_quality/README.md)에서
6class·3기상·162배치·잠정 gate·후보2종과 별도 보류 평가를 구현했다. 두 후보의 회귀와 Rider
annotation 누락을 발견했고 기본 모델/threshold를 유지했다. 이어서
[사전 고정한 v2 새 평가](test-plan/evidence/m10_quality_v2/README.md)에서 Rider 정답·strict
visible box·조건별 coverage와 두 확대 후보를 검증했다. 이후 [V3 준비·S/M 비교](test-plan/evidence/m10_quality_v3/README.md)에서 별도 준비180장과 새 평가162개를 실행했다.
M 확대는 개발의 절대 기준을 통과했지만 빈 배경 FP 증가와 보류의 정밀도·truck recall·coverage가
실패해 미채택이다. [실제 두 site의 V4 도로 준비](test-plan/evidence/m10_road_preparation_v4/README.md)를
마친 뒤 [V4 새 평가](test-plan/evidence/m10_quality_v4/README.md)에서 실제 coverage와 품질을
검사했다. [V5 다중 시야 개선](test-plan/evidence/m10_quality_v5/README.md)은 새 개발 기준을 통과했으나 새 보류가 실패했다. [V6 L 모델·새 평가](test-plan/evidence/m10_quality_v6/README.md)도 개발 기준을 통과했지만 보류 기준은 실패했다. 다음은 **소비한 개발 자료의 bus/truck 구분·정밀도 회귀 개선 → 새 후보·다시 새 보류 →
전체wall20Hz·시작/종료 안정성**이다. 준비 영상은 미래 정확도 표본으로 재사용하지 않으며,
작은 held 보행자의 far26m 범위와 별도 quality freeze·실제 평가 coverage 검사를 유지한다.
새 plan을 고정하기 전에 가시성을 확인하고, 이미 본 v1/v2/v3/v4/v5/v6/v7 보류셋과 준비/실패/진단 영상을 새로운 holdout으로 재사용하지 않는다.
같은 Town의 정지 배치를 전체 ODD로 확대하지 않는다.
그 뒤 M11에서 metric fusion/localization·temporal planner 입력·risk·valid classical fallback을
정의하고 기존 감독/제어 경로에 연결한다. 온라인 저항 추정은 별도다.
구체 산출물과 TBD 담당·결정 시점은 [로드맵](roadmap.md)에서 관리한다.
진행한 시도별 상세 경과와 과거 실행 목록은 [구현·검증 이력](archive/implementation-history.md)에서 찾는다.
