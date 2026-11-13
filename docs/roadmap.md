# 로드맵과 미결정 항목

현재 구현·검증·OPEN은 [프로젝트 상태](project-status.md)에서 관리한다.
이 문서는 남은 단계의 산출물과 결정할 항목만 다룬다.

<a id="m9-시작-범위"></a>
과거 M9 착수 범위는 [구현 이력](archive/implementation-history.md#m9-이번-후속-구현)에 보존하며,
현재 종료 범위는 [프로젝트 상태](project-status.md#m9-기능-범위-마감)를 따른다.

## 후속 단계

| 단계 | 산출물 |
| --- | --- |
| M10 | Host 인지의 unavailable 보호·주행 기능 연결, 새 독립 품질 평가, 시작/종료·장기 부하·전체 지연 검증. 현재 구성과 실측은 프로젝트 상태를 따름 |
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
| TBD-09 | Jetson board/RAM·platform stack·모델/workload·측정 / compute·AI | [M10 Host 모델·hash·FP32 CPU/CUDA·camera fixture](interfaces/perception.md)와 wall 측정 고정; 독립 품질·장기 실행·전체 실시간 수용 및 M12 독립 보드 비교 전 |
| TBD-10 | perception/planner shape·history·risk·fallback / AI·safety | [2D 인지·관측10frame·원천100ms 경계](interfaces/perception.md), [상태 속도 제안](interfaces/supervised-speed-proposal.md)·Supervisor 구현. Metric fusion·temporal learned planner·risk 보정·주행 통합 후속 |
| TBD-11 | compiler/CI·도구·license, 제어 tuning·transition·반복 / toolchain·control | Host C++17/core·C++20/SOME-IP 사용. S03 v1 구동 포화 FAIL 보존; v2 startup20s/감속6s 고정. 추진 포화 feedback·관성 필요조건 검증; [제동 피드백 v3의 component/입력 재생·새 S03](test-plan/evidence/milestone-followup/README.md) 검증; BMS 가용력 adapter·native governor/보호 연결 및 실제 CARLA 속도 두 조건 검증; 온라인 저항 추정·전체 ODD와 추가 toolchain 변경은 후속 검증 |
| TBD-12 | 전원 sequence·INIT/permission·shutdown/복구 / vehicle management | M6 startup/RunLease/stop/HV-off 검증. 실차 LV/충전/Target 반응은 후속 |
| TBD-13 | battery/thermal·limits·efficiency·energy 오차 / 모델 | M6 계수·M7 단일 EV work 정산 사용. Chemistry/OEM 적합성은 미결정 |
| TBD-14 | BMS/EV wire·원천/dependency·hop budget / interface·timing | Host P05·receiver·원천 전달 검증. 다른 kernel/Target clock은 후속 |
| TBD-15 | Central–Zone schema/QoS·queue·INIT/rejoin·배치 / architecture·통신 | Front/Rear·8-role·owner-wire·SOME/IP 한정 결정. Target/system TC 후속 |
| TBD-16 | MBD 도구·solver/sample·공통 vector·numeric tolerance·generator / model·control | M6 Python/binary64 MIL·M8 수작업 C++ 동등성·SimpleVehicle 폐루프 검증. [CARLA 저속 simulation-time 연결](test-plan/carla-speed-protocol.md) 검증. [단일 곡선30km/h](test-plan/evidence/m8_route/README.md)와 [S01/S03 고정 fixture](test-plan/evidence/m8_reference/README.md) 검증; M8 제어기 기능 범위 종료; 전체 Reference·선택적 생성 도구 후속 |

M6에서 결정된 수치·소유권과 후속 gate의 상세 구분은 [M6 검토](archive/milestone-reviews.md#m6)에 있다.
수치 변경은 이전/새 값·이유·영향 requirement/ICD/profile/test·결과를 함께 기록한다.
문서/YAML의 `TBD`·`null`을 0·default·disabled로 해석하지 않는다.


## M10 진행과 후속 gate

현재 구성·최근 비교 결과·다음 작업은 [프로젝트 상태](project-status.md#다음-작업)에서 관리한다.
모델 지명과 개발/보류 분리, 보드 배포 순서는 [모델 선정 안내](perception-model-selection.md)를 따른다.
추가 학습과 보드별 최적화를 필수 선행 작업으로 두지 않는다.

- **기능 연결:** unavailable·stale·입력 정지와 복구를 기존 상태/보호·Actual 경로에서 검증한다.
- **독립 품질:** 후보·센서 설정을 사전 고정하고 미사용 평가 자료로 판정한다. 소비한 보류는 새 수용에 재사용하지 않는다.
- **실행 성능:** 실제시간 동작, 시작/종료, 장기 부하와 전체 지연을 조건별로 측정한다. Reference 수치 변경은 요구사항 변경·영향 검토를 거친다.
- **배포:** M12의 각 보드에서 동일 Reference를 측정한 뒤 TensorRT·정밀도·입력/rate 변경을 검토하고 품질·차량 동작을 재검증한다.

## 최신 M10 후속 범위

최신 판단은 [프로젝트 상태](project-status.md#최신-m10-판단), 완료된 시도와 실패는
[Host 실행 목록](archive/implementation-history.md#m10-host-실행-이력)과 각 evidence에서 확인한다.
이 문서에는 개별 실행 수치와 날짜별 경과를 누적하지 않는다.
