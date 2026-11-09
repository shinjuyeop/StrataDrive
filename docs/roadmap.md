# 로드맵과 미결정 항목

현재 구현·검증·OPEN은 [프로젝트 상태](project-status.md)에서 관리한다.
이 문서는 남은 단계의 산출물과 결정할 항목만 다룬다.

## 후속 단계

| 단계 | 산출물 |
| --- | --- |
| M10 | Host 인지·live shadow·V6 L 모델/새162개 평가 완료. 지명 L 개발 절대·상대 PASS, 보류 P81.6%/R62.0% FAIL·기존 S 유지. 다양한 개발/학습 자료와 작은 VRU·차종 개선·새 보류·전체wall20Hz·장기 안정성·주행 통합 남음 |
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
- 선택형 Supervisor→BMS 가용력 governor→기존 PI/배분과 고장 시 coordinator 보호·DTC를 연결했다. 실제 CARLA nominal/input-loss와 독립 감사·원본 재생을 통과했다. 새 monitor의 qualified 복구/clear와 정상 정지 전환은 논리 SIL에서 검증했다. [실제 CARLA 복구 주행](test-plan/evidence/service-carla-recovery/README.md)도 같은 차량의 새 INIT로 검증했다. 실제 모델·온라인 저항 추정은 별도다.
- Host 인지 fixture의 scenario·camera·model/hash/FP32·SW fingerprint·stage wall 측정은 고정했다. Board 비교와 전체 Reference의 동일 workload·실시간 수용 조건은 M12 전에 정한다.
- 실제 ACK/통신 손실의 주입 위치·기대 물리 반응을 먼저 정하고, tick 차단과 차량 정지를 구분한다.
- 고정 membership의 다중 source 병합 장벽과 실제 SOME/IP 원본 재전송은 [검증](test-plan/evidence/epoch-merge/README.md)했다. 선택형 live Front/Rear 교체와 Central spool은 [추가 검증](test-plan/evidence/native-epoch-replacement/README.md)했다. [Central 교체](test-plan/evidence/central-epoch-replacement/README.md)도 연결했다. [Terminal service의 family 적용](test-plan/evidence/service-carla-recovery/README.md)까지 검증했다. 다른 kernel/Target, 세션 내 무중단 기록 이관·디스크 보존 정책과 학습자 최종 수용은 별도 gate로 관리한다.

M7–M9의 구현 경과·중간 실패·미채택 후보는 [보관 이력](archive/implementation-history.md)을 따른다.
