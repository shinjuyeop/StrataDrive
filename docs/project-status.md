# 프로젝트 상태

정리 기준·최신 검증: **2026-11-16**.
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
| M10 | **준비 수정·첫30초 통과 / 후속 HV 만료·owner 대기 분석 / 장기 안정성·전체 OPEN** | [최신 실행·입력 나이 분석](test-plan/evidence/m10_host_clock_v2/README.md) · [HV 실패 분석](test-plan/evidence/m10_state_path_v3/README.md) · [5분 실패](test-plan/evidence/m10_host_endurance_v1/README.md) |
| M11 | 상태 속도 제안·BMS 가용력·native 보호 연결; temporal learned planner·metric world model NOT RUN | [제안 계약](interfaces/supervised-speed-proposal.md) · [로드맵](roadmap.md) |
| M12–M13 | PLANNED / NOT RUN | [로드맵](roadmap.md) |

## 최신 M10 판단

선택한 Host 배치는 물리 owner2코어, native1코어, 렌더러·영상 공유4코어, 관측1코어다.
카메라2560×1536·D-FINE-M960 CUDA·목표10Hz, 렌더러 최대20Hz를 유지한다. 빈 월드 대기,
passive ORT, CUDA blocking, NVMe 원본 BGRA 저장을 적용했다. 물리5ms·native2/4ms·
HV30ms·인지100ms와 원래 수치 적분 조건은 변경하지 않았다.

앞선 [F/G/H30초3회](test-plan/evidence/m10_host_profile_v5/README.md)는 통과했지만,
[후속5분](test-plan/evidence/m10_host_endurance_v1/README.md)과 상태 경로 V3는 HV 의존 입력
만료로 실패했다. 내부 JSON 왕복을 제거한 [Structured state 후보](test-plan/evidence/m10_structured_state_v1/README.md)는
기존 계산·외부 검사·NaN/무한대 거부를 보존하는 선택 옵션이며, 기본 설정으로 채택하지 않았다.
이 후보의 앞선214ms 감시 슬롯 실패도 그대로 보존한다.

앞선 [Monitor timing V1](test-plan/evidence/m10_watch_timing_v1/README.md)은 첫30초 통과,
후속5.097초 HV 만료로 실패했다. 새 입력 이전에 보유 입력이30.350ms로 만료되는 순서를
정확 재생으로 확인했고 최초 입력 오류를 보존하도록 고쳤다. 최고99°C와 전체 코어의
약800MHz 보고 구간도 관측했으나 전원·펌웨어 원인은 확정하지 않았다.

[Host clock V1](test-plan/evidence/m10_host_clock_v1/README.md)의70% 최대 부스트 요청 시험은
첫30초 통과·후속 준비132ms 실패였다. 모델 준비가 관측 CPU0,8을 상속하고 영상 쪽의
OpenCV 선언값을 적용받지 못하는 문제를 수정했다. 준비·worker 생성에 영상 CPU와
기존 CV4/resize4를 적용하고 관측 호출 스레드는 원래 배치로 복원한다.

최신 [Host clock V2](test-plan/evidence/m10_host_clock_v2/README.md)는 수정한 준비 단계가
실제70% 동시 실행 두 번에서33.3–44.7ms로 통과했다. **첫30초는 정상5830/INIT170/보호0으로
PASS**다. **두 번째는1.794초에 HV 의존 입력30.490ms로 만료**, 정상195/INIT162/보호5643으로
FAIL이다. 두 실행 모두 native 누락·기한 초과0이며, 두 번째 전체150010슬롯을 확인했다.
5분은 첫 실패 중단 규칙에 따라 NOT RUN이다.

CPU 최고는74/77°C,50ms 관측의 모든 CPU별 thermal counter 증가0, 전체850MHz 이하
샘플0이다. 감시 최대 기상 지연은0.557/0.495ms였다. 부스트 제한만으로 HV30ms 반복
안정성은 확보하지 못했고70%를 기본 설정으로 채택하지 않는다.

고정된 최초 오류 입력은 만들어질 때 이미 의존 데이터가21.597ms 오래됐고, 보유 중
8.893ms가 더해져 만료됐음을 보여 준다. 같은 호출의 새 입력은8.893ms지만 기존 입력
만료 검사가 먼저다. 해당 물리 tick은 wall7.940ms / thread CPU1.982ms였고 다음 작업의
직전 완료→승인도5.158ms였다. 아직 thread 스케줄 지연·physics worker 대기·RPC·
권한 조건 대기를 구별하지 못하므로 다음 계측 대상은 이 owner 대기 구간이다.
기한·원래 source 시각·검사 순서는 변경하지 않았다.

영상은284/282장, 실제 카메라9.30/9.27Hz다. 원래 획득→결과 지연은 중앙값81.00/80.20ms,
p95 87.59/87.33ms이고100ms 초과는1/2회다. 두 번째 보호 이후 수치를 정상 주행 성능으로
해석하지 않는다. 초반 가감속 뒤 정지 유지하는 시나리오이며 연속 경로 주행 시험이 아니다.

Python501·동결85검사, 두 실행의 원래 제어 출력·최초 오류 정확 재생과 원본566장
BGRA/RGB 검증을 완료했다. 미래 품질 제외는16633개다. 보관 위치 오류 비교와 중복 복원
수정도 확인했다. 사용자 helper는 owner 종료 뒤 호스트 상한100%를 자동 복원했고 공유
파일6개의 원래 SHA도 일치한다. 검증된 압축·중복 삭제만 수행하고 모든 원본을 보존한다.

**5분 안정성·냉각 여유, native 인지 수용0, 전체 장면·독립 품질·각 Jetson 배포·M10 종료는
OPEN**이다. 이전 실패와 미채택 설정은 [Host 실행 이력](archive/implementation-history.md#m10-host-실행-이력)을 따른다.

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

1. [V2 최초 HV 만료](test-plan/evidence/m10_host_clock_v2/normal-30s-02/first-fault-analysis.json)의 frame657/658을 기준으로 owner pump 대기 사유·thread 스케줄·physics worker 대기를 구별한다. 원래 HV30ms·source 시각을 유지하고, 원인이 확인된 뒤 별도 후보의 유한 반복→5분 순으로 검증한다.70% 제한만으로 해결됐다고 보지 않는다.
2. [물리/렌더링 분리 계약](interfaces/perception-render-isolation-v1.md)의 같은 프레임 wheel/bone/material 상태·자산 식별과 native 연결을 완성한다. 전체 장면이 없으면 인지 제어 수용은 닫고 Required는 opt-in SIL로 둔다.
3. 후보·센서·모델 설정을 고정한 뒤 새 준비·개발·독립 보류 평가를 수행한다. 이미 본 V1–V9 보류·준비·실패·진단 영상은 새 holdout으로 재사용하지 않는다.
4. M11의 metric fusion/localization·temporal planner·risk·classical fallback을 정의하고, M12에서 각 Jetson의 동일 Reference 배포·측정 뒤 보드별 최적화를 검토한다.

구체 산출물과 미결정 항목은 [로드맵](roadmap.md)을 따른다.

## M10 비동기 실행 후속

상태·인지·consumer의 독립 실행 계약은 [비동기 인지 경계](interfaces/perception-async-native-v1.md),
최신 판정은 이 문서 상단, 실행 근거는 [Host 실행 이력](archive/implementation-history.md#m10-host-실행-이력)에 모았다.

## M9 기능 범위 마감

선언한 유한 Host·simulation10ms 기능 범위만 종료했다. [마감 검증](test-plan/evidence/m9_followup/README.md)과
[상세 이력](archive/implementation-history.md#m10-정리-전-상세-기록)을 따른다.

## 이전 milestone 소프트웨어 후속

제동 피드백·저장 오류·세션 이관·실제 CARLA 복구 등 완료 경과는
[통합 이력](archive/implementation-history.md#m10-정리-전-상세-기록)에 보존했다.
