# 프로젝트 상태

정리 기준·최신 검증: **2026-11-19**.
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
| M10 | **30초·5분 동시 실행 및 개발 인지 품질 PASS / 보류 인지 품질 FAIL · 실시간 수용 OPEN** | [GPU 전처리 실행](test-plan/evidence/m10_cuda_resize_v1/README.md) · [보류 장소 101 평가](test-plan/evidence/m10_parking_holdout_v1/README.md) |
| M11 | 상태 속도 제안·BMS 가용력·native 보호 연결; temporal learned planner·metric world model NOT RUN | [제안 계약](interfaces/supervised-speed-proposal.md) · [로드맵](roadmap.md) |
| M12–M13 | PLANNED / NOT RUN | [로드맵](roadmap.md) |

## 최신 M10 판단

**M10은 아직 OPEN이다.** [0.5ms 통신 처리 후보](test-plan/evidence/m10_service_half_v1/README.md)가
30초·5분의 실제 동시 실행, 원본 전체 검증, 추가 감사기 8개 재현을 통과했다.
5분의 물리 기록 60000개와 native 호출 599963개가 정확히 재생됐고, 보호 진입·물리 중 만료가
없었다. 독립 watch 1500000 슬롯의 누락·지연은 0이다. 모델 시간 300초에 실제 시간
300.00098초가 걸렸다. 유한 가감속 뒤 대부분 정지 유지한 조건의 결과다.
이전 [HV50/cache V2](test-plan/evidence/m10_hv50_cache_v2/README.md)의 실패는 그대로 보존한다.

| 확인한 문제 | 현재 판단 |
| --- | --- |
| 반복 sudo 입력 | 설치한 전용 70%·30분 자동 복원 도구로 무인 실행 가능 |
| 시작 전 자산 읽기·모델 준비 지연 | 별도 빈 서버 준비, 동일 CUDA 라이브러리 준비, 원본을 보존한 NVMe 자산 배치 구현 |
| 기록 캐시와 GC 중 디스크 읽기 | 닫힌 raw shard를 sync한 뒤 캐시 해제. V2의 GC 4회는 major fault 증가 0, 약 13~17ms. 다른 부하까지 해결됐다는 뜻은 아님 |
| HV 의존 입력 30ms 만료 | 기존 ADR-0066의 명시적 HV50 프로필을 endurance/replay에 연결. source·wheel·Actual·명령 기한은 그대로. 과거 HV30 실패는 그대로 보존 |
| 새 후륜 명령 전달 지연 | 원래 1ms polling의 145770ns 지각을 확인. 0.5ms 후보의 실제 30초·5분은 기존 만료·순차 ACK를 유지한 채 PASS |
| 배포용 영상 서버 비교 | 중앙 장면 지연 약 496ms로 부적합. 기존 source editor 영상 서버로 복귀 |

같은 모델과 원본 픽셀을 유지한 GPU 전처리로 30초·5분 동시 실행을 마쳤다. 5분 동안
물리 기록 60,000개와 native 호출 599,962개가 원본과 일치했다. 관측 슬롯의 누락·지연은
0건이었다. 30초·5분 모두 원본 영상과 추가 검사 8개를 보관본에서 재검증했다.
[GPU 실행 및 판정](test-plan/evidence/m10_cuda_resize_v1/README.md)

원본 보관·검증의 중복 읽기를 줄인 [검증기](test-plan/evidence/m10_archive_stream_v1/README.md)도
전체 파일·영상 해시와 원래 판정을 유지하면서 검증했다.

현재 후보는 owner 4코어/native 1코어/영상 2코어/관측 1코어, 2560×1536,
D-FINE-M960 CUDA, 카메라 목표 10Hz·렌더러 조회 20Hz·MaxFPS60이다.
20Hz 카메라 달성 자체는 종료 기준이 아니다. 원래 100ms 기한과 실제 wall 시간에서의
가용성을 측정한다. 유한 가감속 뒤 정지 유지 시나리오이며 연속 경로 주행 수용이 아니다.

5분 영상 결과의 장면 기준 지연 중앙값은 CPU 전처리 93.97ms에서 GPU 전처리
76.42ms로, p95는 104.12ms에서 84.15ms로 줄었다. 100ms 이상 걸린 결과는
321/2,772개에서 9/2,769개로 줄었다. 다만 새 결과가 그 기한 안에 존재한 시간은
5분의 최대 21.09%였고 최대 공백은 633ms였다. 실제 인지 제어 입력 수용은 0건이다.
[기존 5분 원본 집계](test-plan/evidence/m10_service_half_v1/latency-300s-audited.json) · [GPU 5분 원본 집계](test-plan/evidence/m10_cuda_resize_v1/latency-300s.json)

정지 상태의 두 서버에서 차량 2대와 보행자 1대를 각각 16프레임 관측했다.
뼈대 80개와 재질 슬롯 59개를 포함한 측정값이 일치했고, 실제 카메라 원본 8장의
프레임·시각·픽셀 해시를 확인했다. [정지 장면 비교](test-plan/evidence/m10_visual_inspect_v1/README.md)

움직이는 차량의 물리 처리·정산 400회를 확인했다. 16개 원본 물리 프레임에서 차량은
1.85m 이동했고, 별도 렌더러가 만든 2K 영상 16장을 원본과 연결했다. 완료된 애니메이션 값을
재현했을 때 바퀴 각도 차이는 최대 0.000033°였다. [움직이는 장면 비교](test-plan/evidence/m10_visual_inspect_v1/moving-comparison-03.json)

물리 시뮬레이션에서 주행 중 실제 인지 IPC 연결을 끊으면 네이티브 수신기가 단절을 감지하고
다음 10ms 물리 프레임에서 보호 제동을 적용했다. 두 번째 시험에서 0.429m/s였던 차량과 네 바퀴는
시뮬레이션 시간 0.80초 뒤 정지했고 400회 정산이 완료됐다.
[단절 시험](test-plan/evidence/m10_visual_inspect_v1/transport-loss-02/physical-response.json)

개발·보류 준비는 각 99장 통과했다. 개발 평가 81장에서 D-FINE-M960은 정밀도 82.69%,
재현율 59.93%로 절대 기준 85%·80%에 미달했다. 배경 차량 세 대가 차량 누락 205건을 차지한다.
이 초기 모델은 개발 단계에서 탈락했다. 정상 인지의 실시간 수용·만료·재가입 및 최종 안정성 검증이 남았다.
[개발 점수와 비교 실험](test-plan/evidence/m10_fresh_quality_2k_v1/results.md) Jetson별 배포는 M12에서
수행하며 현재 보드 최적화를 앞당기지 않는다. M10 종료로 표시하지 않는다.
다른 도로에서 RGB·마스크 432쌍을 새로 수집했다. 기존 학습 전용 자료를 합쳐 D-FINE을 학습하고
독립 검증 자료 315장으로 후보를 선택했다. 개발 영상에서 디코더 학습은 정밀도 98.83%·재현율 63.11%,
승용차 분류층 추가 학습은 83.26%·72.66%였다. 검증 자료로 신뢰도·중복 억제를 선택한 후보는
64.48%·80.90%였다. 이 세 후보는 두 절대 기준을 동시에 충족하지 못했다. [학습·오검출 판정](test-plan/evidence/m10_occlusion_transfer_v1/README.md)

독립 지도에서 학습 264장·검증 384장을 추가했다. 승용차 박스·가림 보정과 버스·트럭 중복 처리 후
개발 장소 90에서 432개 정검출·10개 오검출·102개 누락으로 정밀도 97.74%, 재현율 80.90%를 기록했다.
CUDA ONNX와 PyTorch의 81장 판정이 일치했고, 개발 절대 기준과 YOLOX-S 대비 상대 기준을 모두 통과했다.
독립 검증 두 집단에서도 정밀도 85%·재현율 80%를 넘었다. [개발 후보 및 고정 기록](test-plan/evidence/m10_parking_verifier_v1/README.md)

고정 후보를 보류 장소 101의 81장에서 한 번 평가했다. 정답 129개 중 106개를 맞히고 오검출 2건으로 정밀도 98.15%·재현율 82.17%를 기록했다. YOLOX-S 대비 상대 기준 여섯 항목은 통과했지만 사람 재현율 26/42(61.90%)가 클래스별 최소 70%에 미달해 전체 판정은 FAIL이다. 승용차는 33/33, 근거리 보행자는 3/3이었다. 실시간 제어 수용과 Jetson 성능은 미검증이다. [보류 점수·마스크 재검산](test-plan/evidence/m10_parking_holdout_v1/README.md)

별도 검증 699장에서 놓친 보행자 5건은 모두 가림 장면이었다. 4건은 위치가 맞는 박스의 사람 점수가 낮았고 1건은 박스 위치가 빗나갔다. 점수 기준을 0.60에서 0.35로 낮추면 보행자 1건을 회복하고 사람 오검출이 7건 늘었다. 검증 자료의 30m 이상 보행자는 0건이다. [학습·검증 진단](test-plan/evidence/m10_person_diagnosis_v1/README.md)

이전 실패와 원본은 각 evidence와 [Host 실행 이력](archive/implementation-history.md#m10-host-실행-이력)에 보존한다.

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

1. 30m 이상·부분 가림·이륜차 중첩 보행자를 독립 개발 장소에서 보강하고 현재 0.60 기준과 개선 후보의 보행자·탑승자 검출 및 오검출을 비교한다. 후보를 고정한 뒤 새 독립 장소로 검증한다. [보행자 누락 진단](test-plan/evidence/m10_person_diagnosis_v1/README.md)
2. 보류 기준을 통과하면 물리 서버와 영상 서버의 동일 프레임을 대조하고, 실제 영상 결과의 native 수신·만료·중단·재가입과 제어 지연을 검증한다. [물리/렌더링 분리 계약](interfaces/perception-render-isolation-v1.md)
3. M11의 metric fusion/localization·temporal planner·risk·classical fallback을 정의하고, M12에서 각 Jetson의 동일 Reference 배포·측정 뒤 보드별 최적화를 검토한다.

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
