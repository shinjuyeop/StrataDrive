# 프로젝트 상태

정리 기준·최신 검증: **2026-11-17**.
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
| M10 | **5분 HV 만료 지속 / 재시험 모델 준비 실패 / 라이브러리 I/O 후보 준비 / 전체 OPEN** | [최신 시작 실패](test-plan/evidence/m10_gc_recovery_v1/README.md) · [후속 후보](test-plan/evidence/m10_gc_recovery_v2/README.md) |
| M11 | 상태 속도 제안·BMS 가용력·native 보호 연결; temporal learned planner·metric world model NOT RUN | [제안 계약](interfaces/supervised-speed-proposal.md) · [로드맵](roadmap.md) |
| M12–M13 | PLANNED / NOT RUN | [로드맵](roadmap.md) |

## 최신 M10 판단

최신 비교의 Host 배치는 물리 owner3코어, native1코어, 렌더러·영상 공유3코어, 관측1코어다.
카메라2560×1536·D-FINE-M960 CUDA·목표10Hz, 렌더러 조회20Hz·MaxFPS60을 유지한다.
물리5ms·native2/4ms·HV30ms·인지100ms와 원래 수치 적분 조건은 변경하지 않았다.

마지막으로 물리 측정까지 진행한 [GC owner3 V1](test-plan/evidence/m10_gc_owner3_v1/README.md)은
**30초 두 번 PASS, 5분60.196초 HV 만료로 FAIL**이다. 짧은 시험은 각각 정상5838·
INIT162·보호0이다. 5분은60000구간·정상11874·INIT162·보호47964이다.
첫 본 GC는 이전19.108→16.653ms로 줄었고, 첫 증분 정리는419회·최장164.231us로
나뉘어2.073초에 끝났다. GC4회와61.1초·12220프레임 주기는 그대로다.

GC 뒤 정상 프레임 세 개가 진행됐지만 기존 wheel/actuator 시각을 계속 상속했다.
다음 갱신은 추가 preview1ms에서 대기했고, GC 종료13.607ms 뒤 HV 나이30.383242ms로
원래 보호가 걸렸다. 원래 admission60000개·ingress36006개 재생과 최초 오류가 일치했다.
[원본 계측·회복 구간 분석](test-plan/evidence/m10_gc_owner3_v1/normal-300s-01/recovery-window-analysis.json).

이번 native1,500,010개 eligible 슬롯의 누락·지연은0이다. 이전 간헐적 누락의 지속적
해결을 확정하지 않는다. CPU 최고88°C·관측 열 제한 증가0, 카메라 약9.24Hz다.
오류 전 영상556개는 중앙80.60ms·p95 86.62ms·100ms 초과1회로, 이전2코어의
78.37 /85.37ms보다 소폭 늘었다. 보호 유지 영상은 정상 주행 수용과 구분한다.
원본3338장을 보존했고 미래 품질 제외는34241개다. 공유6파일·부스트100%를 복원했다.

최신 실제 시도 [Recovery V1](test-plan/evidence/m10_gc_recovery_v1/README.md)은 첫 모델 준비가
10초를 넘겨 **제어 시작 전 FAIL**이다. 물리·native·카메라0, 후속 두 시험 NOT RUN으로
300us 회복 효과는 미측정이다. 준비 작업 스레드의20/20 D 상태·major fault370 증가와
GPU0%가 관측됐다. worker 종료5초 뒤에도 busy였고 클라이언트SIGSEGV도 보존했다.
원본 crash stack이 없어 그 직접 원인은 확정하지 않는다. 공유6파일·100%는 복원됐다.

후속 [Recovery V2](test-plan/evidence/m10_gc_recovery_v2/README.md)는 동일300us 모듈·CPU 배치에서
고정 라이브러리12개·1.91GB를 모델 생성 전 순차 읽고 해시 검증한다. 추론을 추가하거나
원래 준비10초·후속100ms·물리5ms·HV30ms·최종 검사를 바꾸지 않는다. 별도 읽기 비용도
기록하며30초 초과는 시작 거절이다. 페이지 고정이나 준비 실패의 영구 제거를 보장하지 않는다.
Python537·동결125·실제 모델 양쪽 준비 경로를 통과했고 동일 C++29·빈 renderer 검증을
재사용한다. 본시험은 **NOT STARTED**다.70%는 유한 시험의 임시 조건이다.

초반 가감속 뒤 정지 유지하는 유한 시나리오이며 연속 경로 주행 시험이 아니다.
이전 조건·실패·저장 정리는 [Host 실행 이력](archive/implementation-history.md#m10-host-실행-이력)에 남긴다.

**5분 안정성·냉각 여유·native 인지 수용0·전체 장면·독립 품질·각 Jetson 배포·M10 종료는 OPEN**이다.

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

1. [GC recovery V2](test-plan/evidence/m10_gc_recovery_v2/README.md)을 같은70%에서30초→30초→5분 검증한다. 첫 실패에 후속 실행을 중단한다. 원래 모델 준비·최종5ms·HV30ms를 유지하면서 준비가 완료되고 GC 뒤 갱신이 회복되는지, native 누락·영상 지연·열 여유를 확인한다. 다음 분석 추천은 GPT-6 Astra / xhigh다.
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
