# 로드맵과 미결정 항목

현재 구현·검증·OPEN은 [프로젝트 상태](project-status.md)에서 관리한다.
이 문서는 남은 단계의 산출물과 결정할 항목만 다룬다.

## 후속 단계

| 단계 | 산출물 |
| --- | --- |
| M10 | Native4K 준비·10/13/20Hz 공급 공백과240장2회 반복 관측. Renderer/SDK age·callback·상태/보호 연결, 새 독립 품질·wall20Hz·장기 부하·각 보드 배포 남음. 기존 S 유지 |
| M11 | Metric world model/localization·temporal learned planner, Safety Supervisor·유효 classical fallback, 인식/판단 한계 검토 |
| M12 | Thor 또는 Orin NX에 각각 독립 배포·동일 Reference 비교 후 profile별 최적화·재검증 |
| M13 | 전체 SIL/V&V·회귀·추적성 검토와 검증된 범위·제약 공개 |

M8은 모델/코드 동등성과 차량 성능을 따로 판정한다. AI는 trajectory/target speed/risk를
제안하고 safety 검사·Classical Controller를 거친다. Actuator를 직접 제어하지 않는다.
Compute 비교는 같은 scenario/seed·요구·sensor/model/precision·SW revision을 먼저 고정한다.

## Open M0 Decisions

기존 TBD ID를 유지한다. 최종 결정 책임은 학습자(project owner)에게 있고 역할 표시는 담당 분야다.
부분 결정은 해당 Host/모델 범위에만 유효하다. 후속 수치·도구·Target 선택까지 CLOSED로 올리지 않는다.

| ID | 결정할 내용 / 담당 | 결정 시점·현재 경계 |
| --- | --- | --- |
| TBD-01 | CAN layout·scaling·Data ID·sequence / 통신 | M1 Host DBC/P05 구현됨. Wire/schema 변경 시 재검증 |
| TBD-02 | 차체·차륜 geometry, 단위·부호·actuation mapping / 모델·interface | M6 모델과 M7 V1 선택됨. 실제 차량 calibration·다른 blueprint는 후속 |
| TBD-03 | actuator 응답·보호·저속 hold·물리 오차 / plant | M6 fixture·M7 가상 EV 범위 결정. OEM·전체 ODD 수용은 별도 |
| TBD-04 | clock·freshness·job/monitor deadline·측정 / timing | M7 기능은 simulation domain 수용(ADR-0065). CARLA wall5-hv50-v1은 HV source30ms/dependency50ms 분리(ADR-0066);wheel/Actual·owner2ms/4ms·M6 유지. 전체 wall 안정화는 기능 수용과 별도 |
| TBD-05 | middleware·격리·bridge/discovery / 통신 | Host vSomeIP3.7.6 한정 사용; DDS 제어 gate CLOSED. Target은 배포 전 결정 |
| TBD-06 | 배분·충돌/가용성·local protection·DEGRADED / 차량 제어 | M4 component와 M8 고정 fixture의 회생/마찰 전환·차량 응답 검증. 전체 Reference·Target envelope는 후속 |
| TBD-07 | CARLA/UE/client·map/route·tick·fidelity / simulation | 고정 source/Town03/V1의 simulation 기능 수용. 비영상 wall5ms는 제한 검증;영상·서버 종료·전체 renderer 안정성 OPEN; M8 고정 S01/S02/S03 경로 적합성 검증 |
| TBD-08 | DTC code·debounce·persistence·clear / diagnostics | [계약](interfaces/diagnostics.md)과 실제 monitor·전달·유한 부하·simulation10ms 기능 [M9 기술 검증](test-plan/evidence/m9_followup/README.md) 완료; 학습자 최종 수용·wall/Target·무제한 보존 별도 |
| TBD-09 | Jetson board/RAM·platform stack·모델/workload·측정 / compute·AI | [M10 Host 모델·hash·FP32 CPU/CUDA·camera fixture](interfaces/perception.md)와 wall 측정 고정; 정확도·cold startup/전체20Hz 수용 및 M12 독립 보드 비교 전 |
| TBD-10 | perception/planner shape·history·risk·fallback / AI·safety | [2D 인지·관측10frame·원천100ms 경계](interfaces/perception.md), [상태 속도 제안](interfaces/supervised-speed-proposal.md)·Supervisor 구현. Metric fusion·temporal learned planner·risk 보정·주행 통합 후속 |
| TBD-11 | compiler/CI·도구·license, 제어 tuning·transition·반복 / toolchain·control | Host C++17/core·C++20/SOME-IP 사용. S03 v1 구동 포화 FAIL 보존; v2 startup20s/감속6s 고정. 추진 포화 feedback·관성 필요조건 검증; [제동 피드백 v3의 component/입력 재생·새 S03](test-plan/evidence/milestone-followup/README.md) 검증; BMS 가용력 adapter·native governor/보호 연결 및 실제 CARLA 속도 두 조건 검증; 온라인 저항 추정·전체 ODD OPEN; M10 모델 도입 전 갱신 |
| TBD-12 | 전원 sequence·INIT/permission·shutdown/복구 / vehicle management | M6 startup/RunLease/stop/HV-off 검증. 실차 LV/충전/Target 반응은 후속 |
| TBD-13 | battery/thermal·limits·efficiency·energy 오차 / 모델 | M6 계수·M7 단일 EV work 정산 사용. Chemistry/OEM 적합성은 미결정 |
| TBD-14 | BMS/EV wire·원천/dependency·hop budget / interface·timing | Host P05·receiver·원천 전달 검증. 다른 kernel/Target clock은 후속 |
| TBD-15 | Central–Zone schema/QoS·queue·INIT/rejoin·배치 / architecture·통신 | Front/Rear·8-role·owner-wire·SOME/IP 한정 결정. Target/system TC 후속 |
| TBD-16 | MBD 도구·solver/sample·공통 vector·numeric tolerance·generator / model·control | M6 Python/binary64 MIL·M8 수작업 C++ 동등성·SimpleVehicle 폐루프 검증. [CARLA 저속 simulation-time 연결](test-plan/carla-speed-protocol.md) 검증. [단일 곡선30km/h](test-plan/evidence/m8_route/README.md)와 [S01/S03 고정 fixture](test-plan/evidence/m8_reference/README.md) 검증; M8 제어기 기능 범위 종료; 전체 Reference·선택적 생성 도구 후속 |

M6에서 결정된 수치·소유권과 후속 gate의 상세 구분은 [M6 검토](archive/milestone-reviews.md#m6)에 있다.
수치 변경은 이전/새 값·이유·영향 requirement/ICD/profile/test·결과를 함께 기록한다.
문서/YAML의 `TBD`·`null`을 0·default·disabled로 해석하지 않는다.


## M10 진행과 후속 gate

현재 작업 순서는 [모델 선정 안내](perception-model-selection.md)를 따른다.2026-11-10 사용자는
Jetson 각각의 배포 가능성을 고려하되 현 단계의 보드별 최적화는 미뤘다. 사전학습5종의
[개발324장 비교](test-plan/evidence/m10_model_screen_v1/README.md)를 완료했으며 추가 학습은
필수가 아니다. Host 비교를 Jetson 성능/모델 최종 채택으로 올리지 않는다.

그 뒤 [V8 새 Town04 평가](test-plan/evidence/m10_quality_v8/README.md)를 완료했다. 공식 L은
개발 절대/상대 PASS·보류 FAIL이며 작은 보행자·이륜차·차종 혼동이 남았다. 소비된 보류를
재사용하지 않고 개발 자료에서 사전학습 후보 비교를 확대했다. 기본 S와 보드 최적화 후속 원칙은 유지한다.

[비교 V2](test-plan/evidence/m10_model_screen_v2/README.md)는 D-FINE-M·RT-DETRv4-S·
DAMO legacy를 추가해6종의 개발324장 confidence calibration과 봉인 뒤 Town04 개발81장을
확인했다. D-FINE은 Town04 절대 PASS지만 앞선 도로의 FP가 남고 RT-DETRv4는 작은
person/bicycle recall이 부족하다. L의 과거 보류 FAIL도 유지한다. 최종 Reference는 미지명이며
오류 분리와 후보 설정 고정을 후속으로 수행했다. 새 보류·학습·Jetson 최적화는 이번 비교에 포함하지 않았다.

[오류 분석](test-plan/evidence/m10_model_diagnostics_v1/README.md) 뒤 별도
[클래스별 confidence 실험](test-plan/evidence/m10_class_calibration_v1/README.md)을 수행했다.
개발324장에서31,250개 조합을 비교하고 봉인한 D-FINE 설정은 calibration P92%/R89.15%,
이미 소비한 Town04 regression P89.84%/R89.15%로 절대 PASS다. 상대 FAIL은 유지한다.
이 D-FINE 설정을 고정한 [V9 새 도로 평가](test-plan/evidence/m10_quality_v9/README.md)를 완료했다.
모델 없는 준비198장 뒤 새 개발81장은 P95.20%/R92.25%·절대/상대 PASS, 봉인 뒤 새 보류81장은
P86.09%/R76.74%·상대 PASS/절대 FAIL이다. 보류 person/motorcycle 각50%가 남는다.
전459 raw pair와 실패/복구·미래 RGB5449개 제외·full model raw 재감사를 보존한다.
다음은 개발 자료의 작은 VRU/Rider 누락과 입력 해상도/사전학습 후보 효과 검증·새 설정 고정·
다시 새 보류 평가다. 최종 모델 채택·runtime 교체·Jetson 배포/최적화는 미실행이다.


[입력 해상도 후속](test-plan/evidence/m10_resolution_v2/README.md)은 수치 미달1280을 제외하고
640/960을 비교했다.960의 원래 car 회귀 거절 뒤 별도 confidence 후속을 고정했다.486개 개발
설계에서 P95.15%/R91.34%·기존 gate PASS지만 독립 품질 수용은 아니다. 다음은 이 단일
960 후보와 S의 모델 없는 준비·새 개발·봉인 뒤 새 보류 평가다. 기존 보류는 재사용하지 않는다.

M9의 선언한 Host·simulation10ms 기능 범위는 [프로젝트 상태](project-status.md)와
[마감 검증](test-plan/evidence/m9_followup/README.md)을 기준으로 종료했다.
기존 검출·보호·Actual·진단 계약은 다음 단계의 회귀 기준으로 유지한다.

- YOLOX-S RGB→`[1,3,640,640]` FP32→`[1,8400,85]`→최대100개2D 객체, 10frame 관측 history와 bounded worker·C++ 수신 경계를 [첫 인지 계약](interfaces/perception.md)으로 구현했다. 실제 모델·CARLA 정답 분리·원거리/가림 평가·overload/timeout/exception을 [검증](test-plan/evidence/m10_perception/README.md)했다. 정확도·20Hz·정상 영상 ODD와 native 주행 통합은 미완료다.
- 상태 기반 Host 속도 제안의 `[4,6]` 입력·`[16]` 출력·history/risk/fallback은 [첫 계약](interfaces/supervised-speed-proposal.md)으로 구현했다. 새2D 객체를 이 tensor나 metric planner 입력으로 자동 변환하지 않는다.
- [명시적 준비·live camera 후속 검증](test-plan/evidence/m10_live_perception/README.md)에서 준비3회와 센서 분모를 분리하고, 실제 CARLA/CUDA 공유 GPU·원본 frame5 취득·고장4조건·source 정지 wall expiry를 확인했다. 기본 sensor_tick의40/60ms 실패와 서버 강제 종료도 보존한다. RGB postprocess Low/Epic 재수집·동일 모델 평가를 추가했으며 성능/정확도 gate는 결과에 맞춰 완화하지 않는다.
- [확장 정확도 비교](test-plan/evidence/m10_quality/README.md)는 개발/보류 각81배치·6class·3기상과 사전 고정 잠정 gate를 적용했다. 두 후보 모두 채택하지 않았다. Rider13 누락을 고친 별도 v2 정답 생성기·사후 재계산과 당시 실패·지명·원본을 보존한다.
- [V2의 새 사전 고정 평가](test-plan/evidence/m10_quality_v2/README.md)는 실제 pose·Rider 정답·조건별 coverage와 중앙/VRU 확대를 비교했다. 재현율 개선과 차량 종류 오분류 증가를 함께 관측했고, 보류 보행자6개의 지원 미달로 coverage도 실패했다. 실패한 NW truck spawn을 성공 표본으로 세거나 보류 장면을 바꾸어 통과시키지 않는다.
- [V3 준비·S/M 비교](test-plan/evidence/m10_quality_v3/README.md)는 수정 준비180장과 새 개발/보류162개를 실행했다. M 확대는 개발 절대 gate를 통과했지만 빈 배경 FP 증가와 보류 정밀도·truck recall·coverage가 실패해 미채택이다. 사후 지도 screen은 보류 far18개의 도로 projection 이탈을 검출했다. 이를 후속 실제 site 준비와 빈 배경/차종 충돌 개선의 선행 근거로 삼는다. 종료 timeout·동일 설정 재수집도 보존한다.
- [V4 실제 site 도로 맞춤 준비](test-plan/evidence/m10_road_preparation_v4/README.md)는 전체 경로 junction·차로 대조와 모든 actor/rider 최소 지원을 검사해14/24번198장을 통과했다. 작은 held 보행자는 far26m로 한정했다. [V4 새 정확도 평가](test-plan/evidence/m10_quality_v4/README.md)는 새 개발/보류162개와1711개 RGB 제외·별도 freeze로 실제 coverage를 통과했다. 지명 M은 보류 P75.9%/R65.9%·class/relative FAIL로 미채택이다. 다음은 작은 VRU/rider·이륜차/차종 구분 개선과 새 보류 평가이며 이미 소비한 보류를 재사용하지 않는다. 시작/종료 실패·metadata 수정과 별도 진단을 보존했고 다음 평가용 RGB 제외는1873개다.
- [V5 다중 시야 후보·새 평가](test-plan/evidence/m10_quality_v5/README.md)는 M 원본/확대의 약한 클래스 지지와 body 충돌 억제를 구현했다. 새31/35번 준비198장·평가162개에서 개발 P97.5%/R90.7% 절대·상대 PASS, 보류 P84.5%/R67.4% FAIL이다. FP32→16·rider18→23 개선과 truck/far 회귀를 보존하며 S를 유지한다. 원본/압축 재감사·Python129개·설정별13개 PASS이며 미래 제외는2357개다. 다음은 개발 자료의 VRU 누락·이륜차/차종 충돌 개선과 별도 새 보류 검증이다.
- [V6 고정 L 모델·새 평가](test-plan/evidence/m10_quality_v6/README.md)는 L 원본/전체 class context와74/80번 준비198장·평가162개를 검증했다. Context는 개발 truck recall 무하락을 실패해 미지명했고 L 원본은 개발 P95.8%/R87.6% 절대·상대 PASS다. 지명 L의 보류 P81.6%/R62.0%·near person·far는 FAIL이며 S를 유지한다. 보류 truck→bus FP12개가 남았다. Python139개·설정별13개·수치/원본/압축 재감사 PASS이며 미래 제외는2717개다. 다음은 다양한 시야·조명·차종의 전용 개발/학습 자료와 독립된 새 보류 구성이다.
- [전용 개발·학습 데이터](test-plan/evidence/m10_domain_data_v1/README.md)는 사전176장·Train813/validation267과 손실 없는 PNG/COCO·작은 양성·분리 reader를 구현했다. 원본/추가 가림의 모든 표본과 FAIL을 유지하고 사전 split coverage를 검사했다. Bus/truck 공유를 명시하고127번은 향후 quality holdout으로 남겼다. Python148개·설정별13개·공식 COCO/원본/압축 재감사 PASS다. 다음은 trainer/모델 출력 매핑·학습 후보·수치 검사와 새 quality 평가다.
- [첫 L6 학습 후보](test-plan/evidence/m10_training_v1/README.md)는 고정813장·24epoch·4896step을 학습하고 개발267장 macro F1로 epoch17를 선택했다. 개발 P93.84%/R90.05%·macro F190.55%다. 새6-class ONNX·고정 native mapping과16probe 수치/267장 CPU·CUDA 재추론·원본/tensor/압축 재감사 PASS다. Python156개·설정별13개·이전10묶음 무결성 PASS와 별개로 새 quality holdout·runtime 승격은 미실행이며 S와 M10 OPEN을 유지한다.
- [V7 고정 L6·새 도로 평가](test-plan/evidence/m10_quality_v7/README.md)는215/127번 준비198장·개발/보류162개와 원래 gate를 검증했다. 개발 P92.2%/R91.5%지만 bus recall100→60%·precision 회귀로 FAIL이다. 보류 P91.2%/R80.6%·absolute FAIL/relative FAIL을 남겼다. 시작0frame 실패2회·동일 조건 별도 복구 편차와 cold/late를 보존했고 기본 S를 유지한다. Python161개·설정별13개·수치/원본/압축 재감사와 이전11묶음 무결성 PASS이며 미래 제외는4333개다.
- 선택형 Supervisor→BMS 가용력 governor→기존 PI/배분과 고장 시 coordinator 보호·DTC를 연결했다. 실제 CARLA nominal/input-loss와 독립 감사·원본 재생을 통과했다. 새 monitor의 qualified 복구/clear와 정상 정지 전환은 논리 SIL에서 검증했다. [실제 CARLA 복구 주행](test-plan/evidence/service-carla-recovery/README.md)도 같은 차량의 새 INIT로 검증했다. 실제 모델·온라인 저항 추정은 별도다.
- Host 인지 fixture의 scenario·camera·model/hash/FP32·SW fingerprint·stage wall 측정은 고정했다. Board 비교와 전체 Reference의 동일 workload·실시간 수용 조건은 M12 전에 정한다.
- 실제 ACK/통신 손실의 주입 위치·기대 물리 반응을 먼저 정하고, tick 차단과 차량 정지를 구분한다.
- 고정 membership의 다중 source 병합 장벽과 실제 SOME/IP 원본 재전송은 [검증](test-plan/evidence/epoch-merge/README.md)했다. 선택형 live Front/Rear 교체와 Central spool은 [추가 검증](test-plan/evidence/native-epoch-replacement/README.md)했다. [Central 교체](test-plan/evidence/central-epoch-replacement/README.md)도 연결했다. [Terminal service의 family 적용](test-plan/evidence/service-carla-recovery/README.md)까지 검증했다. 다른 kernel/Target, 세션 내 무중단 기록 이관·디스크 보존 정책과 학습자 최종 수용은 별도 gate로 관리한다.

M7–M9의 구현 경과·중간 실패·미채택 후보는 [보관 이력](archive/implementation-history.md)을 따른다.


[CARLA 원본 해상도 비교](test-plan/evidence/m10_camera_resolution_v1/README.md)는 모델960과
confidence를 유지하고 source640×384부터3840×2304까지 실제 촬영했다.4K를 품질 평가 전에
기술 기준으로 고정했고, 같은 개발 배치 각81장에서640은P98.37%/R93.80%,4K는129TP/0FP/0FN이다.
수치15건 중14PASS/1FAIL과 종료 실패3쌍·사전 복구를 보존했다. 전체180쌍·미래 제외5629개다.
[4K source profile](../profiles/perception-camera-source-candidates-v1.json)은 다음 새 평가용이며
기존 S/runtime640은 유지한다.4K 순차 health/resize/추론 P95 약93.64ms로 live20Hz는 미수용이다.
이후 native ingress/전처리 검증은 아래 후속 기록으로 이어진다. 새 준비·개발/보류와 전체 wall 수용은 남아 있다.
새 학습·보드 최적화·실제 Jetson 배포는 수행하지 않았다.

2026-11-11에는 [native4K 비동기 owner](interfaces/perception-async-native-v1.md)를 추가했다.
기존 개발 media에서 상태 producer100Hz·관측 consumer50Hz가 인지 지연/정지/예외와 독립
진행했지만 정상 인지43건도100ms 내 publication0이다. 원래 오류 fixture FAIL·별도25ms
보완 조건을 [근거](test-plan/evidence/m10_async_native_v1/README.md)에 유지한다. 다음 실행 작업은
PC 색상 변환·전처리 비용 개선과 실제 ingress/기존 제어 연결의 source age·수신/적용 기한 검증이다.
실제 차량 제어 또는 live20Hz·ROS/Jetson 연결을 완료한 것으로 올리지 않는다.

2026-11-11 후속 [전처리 개선·실제4K ingress](test-plan/evidence/m10_native_preprocess_v1/README.md)는
개발84장의 RGB/tensor를 그대로 유지하며 전처리 P95를103.36→42.02ms로 줄였다.
비동기 재생은46회 발행/21개 frame 소비로 개선됐지만, 실제 CARLA/Epic과 GPU를 공유하면
37개 완료가 모두 late여서 fresh-output gate FAIL이다. 실제 camera13.60Hz·관측 consumer50Hz,
world67.72Hz이며 원본60개를 포함한 미래 제외는5689개다. 다음은 실제 부하에서100ms 내
공급을 확보한 뒤 실제 상태/보호·제어 연결과 새 독립 품질 평가를 진행하는 것이다.
기존 모델/기한/runtime·M10 OPEN·Jetson 최적화 후속 원칙을 유지한다.


2026-11-11 후속 [native CPU resize·실제 fresh-output](test-plan/evidence/m10_native_kernel_v1/README.md)은
4K 중간 RGB 복사를 없애고 Pillow와 같은 축소 계산을 병렬화했다. 개발84장과 실제72장
입력이 exact이며, 개발 쌍별 전처리 P95는38.97→16.89ms다. 실제 공유 GPU에서36장/31회
완료 중27회 발행·27개 frame 소비를 확인했다. 초기4회 late는 보존하고 원래100ms 기한을
유지했다. Camera12.93Hz·cold 포함 admission P95115.76ms이므로 전체20Hz 수용은 아니다.
미래 제외5761개·원래 FAIL·기본 S/runtime·M10 OPEN을 유지한다. Startup 준비와 반복/장시간
부하·SDK source age·기존 상태/보호 연결, 새 독립 품질과 각 Jetson 배포가 다음 단계다.

## 최신 M10 후속 범위

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
기존 모듈/화면 설정을 복원했다. 다음은 과도한 속도 튜닝보다 unavailable 보호·기능 연결이며,
새 독립 품질·장기 수용·각 Jetson 배포와 보드별 최적화는 별도다.


앞선 [실제 비동기 월드 비교](test-plan/evidence/m10_world_async_v1/README.md)는4K 인식용
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

앞선 [명시적 준비·주파수별 가용성·실제 반복 검증](test-plan/evidence/m10_native_startup_v1/README.md)의 기준을 유지한다.
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
후속 client는 실패 시에도 최종 decision trace를 저장한다. 이전 [CPU kernel·27개 fresh 근거](test-plan/evidence/m10_native_kernel_v1/README.md)와
기존 live FAIL/품질 FAIL은 유지한다. 다음은 renderer/SDK source age·callback·관측 scheduling
분리 계측과 기존 상태/보호 경로의 unavailable 연결이다. 새 독립 품질·전체wall20Hz·장기 운용·
각 Jetson 전체 stack 배포가 남으며 기본 S/runtime640·M10 OPEN·보드 최적화 후속 원칙을 유지한다.
