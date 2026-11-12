# 프로젝트 상태

정리 기준·최신 검증: **2026-11-12**.
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
| M10 | **비영상5ms 유한 물리 실행·장면 IPC 원형 검증 / 실제 렌더 분리·연속 wall 주행·독립 품질 OPEN** | [물리 실행·IPC](test-plan/evidence/m10_owner_split_v2/README.md) · [첫 관측 실패](test-plan/evidence/m10_owner_split_v1/README.md) · [카메라·fence 비교](test-plan/evidence/m10_fence_compare_v1/README.md) |
| M11 | 상태 속도 제안·BMS 가용력·native 보호 연결; temporal learned planner·metric world model NOT RUN | [제안 계약](interfaces/supervised-speed-proposal.md) · [로드맵](roadmap.md) |
| M12–M13 | PLANNED / NOT RUN | [로드맵](roadmap.md) |

## 최신 M10 판단

최신 [2K 지연 개선 비교](test-plan/evidence/m10_latency_2k_v1/README.md)는20Hz를 필수 조건으로
삼지 않고 세 조건만 비교했다. 기존2K는17.55Hz/촬영→추론 평균94.20ms, 입력 버퍼 재사용은
17.68Hz/91.73ms였다.2.48ms 개선은 사전에 정한3ms 채택 폭에 못 미쳐 선택 옵션으로 보존하고
기본 개발 구성은 유지한다. GPU 비동기 읽기+월드 상한100 조건은17.54Hz/127.74ms,
유효 조회10.53% 및 구간별 fresh 소비 FAIL로 채택하지 않았다. 조건을 바꿔 성공으로 만들거나
20Hz까지 추가 튜닝하지 않았고, 자격 후보가 없어 조건부 확인 실행도 하지 않았다.
월드·상태/카메라/소비자의 비동기 구조와 원래 source/receipt100ms는 유지한다. 실제시간1×는
목표이며 느린 시뮬레이션을 목표로 삼은 것이 아니다.636개 소스는 기존 누락 도우미를 이번부터
사전 포함했고, 첫 실측 전 별도 경로 import/19개 테스트로 확인했다. Python378·변조88건,
개발81장 및 신규300장 입력 exact·실패 원본까지 검증했고 미래 제외는8975개다.
기존 모듈/화면 설정을 복원했다. 속도 튜닝을 마치고 아래 unavailable 보호·Host 기능 연결을 수행했으며,
새 독립 품질·장기 수용·각 Jetson 배포와 보드별 최적화는 별도다.

[2K 기능 연결](test-plan/evidence/m10_native_2k_control_v1/README.md)은 Python의 원래 callback
receipt를 보존하는 export, 별도 C++ 수신부, 실제10개 관측의 영상 추적, 선택형 availability 보호를
추가했다. 보존된902개 조회 중 state 초기화 전3개는 unavailable로 유지하고899개를 C++에서
재생해 원본 가용성과 일치했다.9개 논리 SIL에서는 Shadow가 기존 명령/물리 결과를 바꾸지 않고,
Required는 공백·오류에 기존 보호를 적용하며, 영상 복원만으로 재허가하지 않고 새 global INIT 뒤에
정상 제어로 복구했다. 새 C++24개·기존 회귀64개, ASan/UBSan24개, Python385개와 별도 source archive
빌드·재생을 확인했다. 이는 실제 카메라에서 CARLA 차량까지의 live 연결이나 production IPC가 아니다.
이후 [실제 owner shadow 연결](test-plan/evidence/m10_live_shadow_v1/README.md)에서는 비차단
private IPC와 native INIT 경계를 추가했고, 실제2K 결과1개(검출0개)가 원래 기한 안에 C++에
전달됐다. 다만 차량은3개 물리 구간 뒤 기존 Steering/Brake/Drive/Power `ControlDeadline`으로
보호됐으며 정상 주행은 시작되지 않았다. 보호는 첫 live 추론보다50.33ms 먼저 발생했고 별도 wall
watch3880건에는 overrun이 없었다. 당시 카메라 정리 순서 오류까지 원본 FAIL로 남기고
소유권 해제 뒤 정리하도록 수정했다.
C++101·Python395·ASan/UBSan37개와 사전1235-file archive 재빌드/실제 프로세스 통신을 검증했다.
신규 원본1장을 포함해 미래 품질 제외는8976개다. 이는 제한된 전달 확인이며 연속 주행 수용이 아니다.

후속 [시작 오류 수정](test-plan/evidence/m10_startup_v1/README.md)에서는 원본775개 서비스 시각과
3개 물리 응답으로 위 실패를 완전히 재현했다. 공통 전력 입력 대기가 ECU 실행 자체를 미뤄
첫 실행이 enable+30.009ms가 된 것이 원인이었다. 입력은 미가용 상태로 유지하며 ECU를 원래
10ms/20ms 주기에 실행하도록 수정했고, 기존30ms 입력 보호와 source/expiry를 유지했다.
회귀181개·ASan/UBSan67개·1296-file 사전 재빌드가 통과했다. 새 live에서도 첫 실행10.000/20.006ms,
첫 fault0으로 확인했지만 서버 PumpWall 호출에64.77ms 공백이 생겼고 물리 응답2개 이후 새 입력이
없어 enable+30.005ms에 기존 보호가 작동했다. 연속 주행은 여전히 FAIL/OPEN이며 renderer/driver/
scheduling 중 공백 원인은 아직 특정하지 않았다. 추론은 보호21.90ms 이후 시작돼 원인으로 볼 근거가 없다.
새 trial은 원본 영상1개·fresh 수신0개이며 INIT 뒤 실제 상태가 없어 수신기 초기화도 열지 않았다.
789개 서비스/2개 물리 응답과 startup 관측을 exact 재생했고, 카메라 정리 수정은 이번 live에서 통과했다.
모듈/화면 설정을 복원했고 미래 품질 제외는8977개다.

이후 [서버 실행 계측](test-plan/evidence/m10_server_timing_v1/README.md)에서는 UE와 CARLA의
유한 계측을 추가한 한 번의 시험으로 공백 위치를 확인했다. PumpWall 사이65.16ms 중61.71ms
(94.71%)가 UE의 `FFrameEndSync::Sync` 안에 있었고, 그 구간의 game-thread CPU 사용은0.73ms였다.
첫 추론은 보호18.82ms 뒤에 시작됐다. 따라서 인지 worker 비동기화와 별개로 엔진의 게임·렌더
동기화가 다음 물리 tick을 미루는 지점임을 확인했다. 내부 GPU/driver 원인과 해소 방법은 아직 OPEN이다.
1303개 소스를 사전 고정하고17개 검사를 별도 경로에서 재현했으며, 원본5555개 계측에 overflow가 없었다.
788개 서비스/2개 물리 응답 exact 재생·11개 변조 검출이 통과했다. 주행은 기존 입력 보호로 FAIL,
fresh 수신0개이며 원본 영상1개를 포함해 미래 품질 제외는8978개다. UE 실행 파일·CARLA 모듈·설정을 복원했다.

후속 [카메라·fence 비교](test-plan/evidence/m10_fence_compare_v1/README.md)는 renderer와 모델 준비를
동일하게 유지한 카메라 없음/2K 각1회를 사전 선언했다. 2K의45.95ms PumpWall 공백 중42.21ms는
렌더 스레드 완료 이벤트 대기였고 직접 RHI/GPU fence 분기는 선택되지 않았다. 렌더 스레드 뒤의
GPU·driver·초기화 원인까지 특정한 것은 아니다. 카메라 없음은80개 물리 구간/arm 관측 뒤 입력 보호,
2K는2개 구간/no arm으로 종료됐으며 **둘 다 정상 물리 구간0개·FAIL**이다. 이번2K는 첫 영상
수신 전 종료돼 정상 촬영 성능으로 해석할 수 없다. 카메라 없음의 native 서비스 중 최대 기록 공백은
3.01ms지만 별도의 입력·실행 허용 조건 실패가 남아 있다. 1308-file 사전 고정·별도23개 검사,
두 trial의1537/768개 서비스와80/2개 원본 응답 exact 재생·21개 변조 검출을 확인했다.
원본 영상은0개여서 미래 제외8978개를 유지하며 서버 파일4개와 설정을 복원했다.
[분리 경계](interfaces/perception-render-isolation-v1.md)는 단일 물리 owner와 별도 렌더링 프로세스,
유한 snapshot 전달과 원래 장면 취득 시각 보존으로 정했다.

후속 [원본 명령 분석·첫5ms 시험](test-plan/evidence/m10_owner_split_v1/README.md)에서는
10ms 실행의 최초 거절 관측에서 명령 잔여12.298575ms가 물리10ms+기존 preview4ms보다 짧음을
확인했다. 기존 admission 시험에도 있는 피드백 의존이며 ECU 결함을 새로 수정한 것은 아니다.
기존5ms 물리를 명시적으로 선택한 비영상 owner profile을 추가했고 HV30·ECU 주기·원래 보호는 유지했다.
첫 시험은 관측기의10ms 고정값 때문에 첫5ms 상태를 거절한 FAIL로 원본과1315-file 사전 고정을 보존했다.

[별도 선언한 수정 시험](test-plan/evidence/m10_owner_split_v2/README.md)은 관측기에 신뢰된5ms/10ms
설정을 명시하고 실제 준비 worker의 첫 callback 회귀를 추가했다.400개 물리 구간·400개 EV 정산,
정상234개·보호0개, 모델2.000000s/실제2.002217s로 완료됐다.10020개 owner slot의 누락·지각과
만료 명령 적용은0개이며 최대 정상 HV source/dependency age는11.046/21.135ms였다.
최대 속도0.427m/s의 짧은 비영상 조건에 한정된 PASS이며 장기·2K 주행 수용은 아니다.
2007개 native 서비스와400개 응답 exact 재생,13개 변조 검출,1317-file 사전 고정의 별도69 Python/23 C++
검사를 통과했다. 관측·IPC 정리와 외부 제어 차단을 확인했고 원래 서버 파일4개·설정은 복원 상태다.

이후 장면 IPC 원형은 처리 중1개+대기 최신1개만 유지하며 원래 취득 시각·pose를 보존한다.
별도 소비 프로세스 정지 시험과 원본400개 응답 재생,최종 Python423개·C++ admission23개/wheel38개를
통과했다. 아직 실제 CARLA 렌더러와 연결하지 않았으며 전체 동적 장면·영상 provenance 매핑도 남아 있다.
새 원본 영상·holdout은 없고 미래 제외8978개를 유지한다.

기술 검사와 학습자 설명·수용은 별도다. Component PASS를 전체 system/Target PASS로 올리지 않는다.

## 현재 구현과 수용 경계

| 영역 | 현재 범위 | 상세 근거 |
| --- | --- | --- |
| 통신·세션 | Central/Front/Rear 3-process SOME/IP, 8-role INIT/Release/RunLease, 원래 source/expiry와 새 Epoch 재가입 | [SOME/IP 계약](interfaces/someip-rear-adapter.md) |
| 모델·제어 | 독립 종방향 MIL, C++ 모델 동등성, 고정 속도·경로 fixture, 방향별 배분 포화 피드백과 정상 정지/HV-off | [M8 종료 검토](archive/milestone-reviews.md#m8) |
| CARLA | 원본 CAN/P05 Actual의 NoDrive 적용, solver work의 단일 EV 정산, simulation-time 기능 | [Plant 계약](interfaces/carla-plant-adapter.md) · [실행 안내](carla-guide.md) |
| 진단 | 원본 검출·인과 ID·보호·Actual·DTC, qualified 복구와 명시적 clear, 재기동/연속성 심사 | [진단 계약](interfaces/diagnostics.md) |
| 기록 보존 | 유한 journal, 비활성 store의 독점 잠금 archive/restore, byte 동일한 이력 복원 | [보존 계약](test-plan/diagnostic-retention-protocol.md) |
| 영상 인지 | 기존 S/640 baseline과 선택형 D-FINE-M960/2K 경계; RGB-only·영상 추적·원래 두 기한·Host 보호 검증 | [영상 계약](interfaces/perception.md) · [2K 수신·보호](interfaces/perception-native-2k-control-v1.md) |

문서 이력과 공통 진단 발행기·감사 decoder를 정리한 뒤의 동등성·회귀 검증은
[M9 이후 구조 정리 근거](test-plan/evidence/post-m9-refactor/README.md)를 따른다.

## 남은 문제와 제한

- Native 4ms와 전체 wall 실시간 성능, 장시간 영상 실행, 전체 Reference ODD·실차·Target 적합성은 미수용이다. 짧은 비영상 wall 시험과 시뮬레이션 시간의 기능 통과는 각각의 조건에 한정된다.
- UE renderer/GC·로딩 중 종료 및 일부 과거 서버 종료 실패의 근본 원인은 남아 있다. M9 지정 서버의 정상 종료가 전체 renderer 안정성을 입증하지는 않는다.
- 실제 metric world model·localization·temporal learned planner와 온라인 경사/저항 추정은 후속이다. 기존 상태 기반 속도 제안·Supervisor·가용력 governor·PI 경로에는 명시적 SIL 저항값을 사용한다.
- RGB 객체와 2D track은 거리·상대 속도·risk가 아니다. 모델 후보의 개발 성능 개선과 독립 품질 수용을 구분하고 기본 S/runtime640을 유지한다. 늦은 결과·drop·exception·공급 공백은 unavailable이며 가용성 회복만으로 주행 permission을 열지 않는다.
- 기록 보존은 유한 journal·세션별 회수/이관 범위다. 단일 Epoch의 무중단 회전, 디스크 삭제/외부 보존 정책, 전체 매체·실제 전원 차단/캐시 소실 및 다른 kernel의 Clock 운영은 별도 검증 대상이다.
- 과거 M3/M4·DDS/SDK timing·sanitizer 실패와 미채택 후보는 OPEN 또는 당시 판정으로 보존한다. tracefs/perf 접근 제한으로 과거 scheduling 원인을 새로 규명한 것으로 보지 않는다. 기술 검사와 학습자 설명·최종 수용은 별도다.

상세 실패·복구·보류셋 사용 이력은 [통합 이력](archive/implementation-history.md#m10-정리-전-상세-기록),
모델 후보의 선정 근거는 [모델 선정 안내](perception-model-selection.md)를 따른다.

## M7 종료 조건

시뮬레이션 시간 기능 범위는 CLOSED다. 연속 주행·회생/제동·영상·보호와 고장7조건의
[원본 및 독립 감사](test-plan/evidence/m7_carla_integrated/simulation-time/README.md)를 기준으로 한다.
Wall/Target과 전체 renderer 안정성은 별도이며 [당시 종료 검토](archive/implementation-history.md#m7-종료-조건)에 보존한다.

## M8 종료 조건

제어기·고정 fixture 기능 SIL 범위는 CLOSED다. 모델/C++ 동등성, 속도/경로 폐루프,
고정30km/h fixture·추진 포화·정상 정지를 [종료 검토](archive/milestone-reviews.md#m8)와
[마감 무결성](test-plan/evidence/m8_closeout/README.md)으로 확인했다. 전체 Reference·wall·Target은 별도다.

## 다음 작업

1. 검증한 비영상5ms owner와 장면 IPC 원형을 바탕으로 [물리/렌더링 분리 계약](interfaces/perception-render-isolation-v1.md)의 전체 장면 취득·적용, 별도 CARLA 렌더러, 영상과 원래 물리 snapshot의 provenance 매핑을 구현한다. 새2K 시험을 사전 선언해 렌더 정지·종료에도 실제 물리 응답이 이어지고 늦은 영상은 unavailable인지 검증한다. 원래 기한·보호를 유지하며 Required는 opt-in SIL로 둔다.
2. 후보와 센서·모델 설정을 먼저 고정한 뒤 새 준비·개발·독립 보류 평가를 수행한다. 이미 본 V1–V9 보류·준비·실패·진단 영상을 새로운 holdout으로 재사용하지 않는다.
3. 시작/종료·장기 부하·전체 지연과 실시간 동작을 별도로 검증한다. 정지 장면이나 짧은 관측을 전체 ODD 수용으로 확대하지 않는다.
4. M11의 metric fusion/localization·temporal planner·risk·classical fallback을 정의하고, M12에서 각 Jetson의 동일 Reference 배포·측정 뒤 보드별 최적화를 검토한다.

구체 산출물과 미결정 항목은 [로드맵](roadmap.md)을 따른다.

## M10 비동기 실행 후속

상태·인지·consumer의 독립 실행 계약은 [비동기 인지 경계](interfaces/perception-async-native-v1.md),
최신 판정은 이 문서 상단, 시도별 수치와 실패는 [통합 이력](archive/implementation-history.md#m10-정리-전-상세-기록)에 모았다.

## M9 기능 범위 마감

선언한 유한 Host·simulation10ms 기능 범위만 종료했다. [마감 검증](test-plan/evidence/m9_followup/README.md)과
[상세 이력](archive/implementation-history.md#m10-정리-전-상세-기록)을 따른다.

## 이전 milestone 소프트웨어 후속

제동 피드백·저장 오류·세션 이관·실제 CARLA 복구 등 완료 경과는
[통합 이력](archive/implementation-history.md#m10-정리-전-상세-기록)에 보존했다.
