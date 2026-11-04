# 로드맵과 미결정 항목

현재 구현·검증·OPEN은 [프로젝트 상태](project-status.md)에서 관리한다.
이 문서는 남은 단계의 산출물과 결정할 항목만 다룬다.

## 후속 단계

| 단계 | 산출물 |
| --- | --- |
| M7 · 기능 범위 CLOSED | [시뮬레이션 시간 기능 수용](project-status.md#m7-종료-조건). HV 예산 분리 후 비영상 wall 정상2/보호2 통과;영상·장시간 wall 수용은 기능 개발과 별도 |
| M8 · 기능 범위 CLOSED | [종료 검토](archive/milestone-reviews.md#m8): 모델/C++ 동등성·속도/경로 폐루프·고정30km/h fixture·추진 포화·정상 정지. 전체 Reference 수용은 후속 통합 |
| M9 | Fault event → 검출 → 보호 → actual response → DTC 통합. TBD-08 계약 고정 후30km/h 입력 손실·제동 timeout·ACK/통신 손실을 같은 추적 형식으로 검증. 기존 로컬 보호 유지 |
| M10–M11 | Perception·temporal learned planner, Safety Supervisor·classical fallback, 인식/판단 한계와 scenario 검토 |
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
| TBD-04 | clock·freshness·job/monitor deadline·측정 / timing | M7 기능은 simulation domain 수용(ADR-0065). CARLA wall5-hv50-v1은 HV source30ms/dependency50ms 분리(ADR-0066);wheel/Actual·owner2ms/4ms·M6 유지. 전체 wall 안정화는 M8 진입 조건이 아님 |
| TBD-05 | middleware·격리·bridge/discovery / 통신 | Host vSomeIP3.7.6 한정 사용; DDS 제어 gate CLOSED. Target은 배포 전 결정 |
| TBD-06 | 배분·충돌/가용성·local protection·DEGRADED / 차량 제어 | M4 component 구현. M8 전 회생/마찰 전환·차량 envelope 검증 |
| TBD-07 | CARLA/UE/client·map/route·tick·fidelity / simulation | 고정 source/Town03/V1의 simulation 기능 수용. 비영상 wall5ms는 제한 검증;영상·서버 종료·전체 renderer 안정성 OPEN; M8 고정 S01/S02/S03 경로 적합성 검증 |
| TBD-08 | DTC code·debounce·persistence·clear / diagnostics | [v0.1 집계/store component](interfaces/diagnostics.md) 구현·검증; 실제 monitor의 predicate·전달·부하·수용 전 OPEN |
| TBD-09 | Jetson board/RAM·platform stack·모델/workload·측정 / compute·AI | M10 model fixture·M12 독립 보드 비교 전 |
| TBD-10 | perception/planner shape·history·risk·fallback / AI·safety | M10–M11 통합 전 |
| TBD-11 | compiler/CI·도구·license, 제어 tuning·transition·반복 / toolchain·control | Host C++17/core·C++20/SOME-IP 사용. S03 v1 구동 포화 FAIL 보존; v2 startup20s/감속6s 고정. 추진 포화 feedback·관성 필요조건 검증; 동적 가용력 기반 참조·제동 측 포화 OPEN; M10 모델 도입 전 갱신 |
| TBD-12 | 전원 sequence·INIT/permission·shutdown/복구 / vehicle management | M6 startup/RunLease/stop/HV-off 검증. 실차 LV/충전/Target 반응은 후속 |
| TBD-13 | battery/thermal·limits·efficiency·energy 오차 / 모델 | M6 계수·M7 단일 EV work 정산 사용. Chemistry/OEM 적합성은 미결정 |
| TBD-14 | BMS/EV wire·원천/dependency·hop budget / interface·timing | Host P05·receiver·원천 전달 검증. 다른 kernel/Target clock은 후속 |
| TBD-15 | Central–Zone schema/QoS·queue·INIT/rejoin·배치 / architecture·통신 | Front/Rear·8-role·owner-wire·SOME/IP 한정 결정. Target/system TC 후속 |
| TBD-16 | MBD 도구·solver/sample·공통 vector·numeric tolerance·generator / model·control | M6 Python/binary64 MIL·M8 수작업 C++ 동등성·SimpleVehicle 폐루프 검증. [CARLA 저속 simulation-time 연결](test-plan/carla-speed-protocol.md) 검증. [단일 곡선30km/h](test-plan/evidence/m8_route/README.md)와 [S01/S03 고정 fixture](test-plan/evidence/m8_reference/README.md) 검증; M8 제어기 기능 범위 종료; 전체 Reference·선택적 생성 도구 후속 |

M6에서 결정된 수치·소유권과 후속 gate의 상세 구분은 [M6 검토](archive/milestone-reviews.md#m6)에 있다.
수치 변경은 이전/새 값·이유·영향 requirement/ICD/profile/test·결과를 함께 기록한다.
문서/YAML의 `TBD`·`null`을 0·default·disabled로 해석하지 않는다.


## M9 시작 범위

M8에서 제안했던 추가30km/h 고장 조합은 원래 M9의 진단 통합 범위로 관리한다.
실행 전 고장별 검출 기점·보호 선택·Actual 응답·DTC 기대값을 고정하고 한 묶음으로 판정한다.

| 순서 | 산출물 / 완료 조건 |
| --- | --- |
| 1. 진단 계약·component | [TBD-08 v0.1](interfaces/diagnostics.md): code·debounce·persistence·clear·clock/causal ID 정의. [집계/store component 검증](test-plan/evidence/m9_diagnostics_component/README.md) 완료; 실제 monitor 통합·TBD 최종 수용 전 |
| 2. 기존 경로 연결 | [SpeedRequest/NormalStop hook·SimpleVehicle 정상/입력 누락](test-plan/evidence/m9_control_hooks/README.md), [SD-1001 복구·명시적 clear·재고장](test-plan/evidence/m9_speed_recovery/README.md) 검증. Timeout/인계 실패는 detector component 연결 검사; 다른 code의 복구·실제 ACK/lane 손실은 후속 |
| 3. 고장별 통합 | 동일30km/h 참조의 입력 손실·제동 timeout·Stop ACK 손실 및 통신 단절을 구분해 시험. 검출/보호/물리 응답/정지 여부/에너지 정산/DTC를 각각 판정 |

소유자별 [ZoneFeedback/Leaf context expiry 수집·복구](test-plan/evidence/m9_owner_sources/README.md)를
추가했다. 후속 [Gateway·BMS/Power native 원인](test-plan/evidence/m9_native_causes/README.md)은
Gateway 차량 논리 SIL·BMS/Power component 복구 범위다.
다른 BMS/Power 자체 고장 조합은 후속이다.
[BMS electrical/Power current 누락](test-plan/evidence/m9_native_vehicle/README.md)은 차량 SIL에서
보호·물리 응답·DTC·새 INIT 복구까지 검증했다. 영구 전류 누락의 energized HV도 구분한다.

[Release 전 기동 시도](test-plan/evidence/m9_startup_sources/README.md)는 trusted Attempt와
실제 Session을 구분해 Prepare/INIT/Release ACK 누락·새8-role handshake 복구를 검증했다.
[Event-only replica/spool](test-plan/evidence/m9_delivery_spool/README.md)은 실제 별도 process의
ACK 유실·재시작·순서/중복과 유한 저장을 부분 검증했다.
[SOME/IP 새 logical source](test-plan/evidence/m9_someip_live/README.md)는 실제 TCP·별도 writer와
live SPSC publish·ACK 유실/replica 재시작을 검증했다.
[원격 context component](test-plan/evidence/m9_remote_context/README.md)는 실제 accepted credit와
Central 원본 Session 대조·유한 대기·두 stream의 동일 원본/독립 ACK를 검증했다.
[실제 native3-ECU 배선](test-plan/evidence/m9_native_routing/README.md)은2개 context와9개 source
stream을 연결하고 정상·Front/Rear 명령 손실·ACK 유실·context 지연을 기능 검증했다.
[진단 전달 객체 재개](test-plan/evidence/m9_delivery_restart/README.md)는 원본 Session 재대조·
ordinal1 재전송·replica-only commit의 merged 복구를 다룬다. Native owner/SDK 연속 객체 재개와
별도 process SIGKILL을 구분한다. [Front/Rear 발행자 adoption](test-plan/evidence/m9_producer_adoption/README.md)은
실제 ECU process kill/rejoin·새 세대·old prefix replay·저장 전 손실 미확인 표시를 연결한다.
[Central process 재기동](test-plan/evidence/m9_central_restart/README.md)은 명시적 issuer 계승·
fresh collector prefix import·생존 source 재전송·미확인 연속성 clear 차단을 연결한다.
[로컬 연속성 심사](test-plan/evidence/m9_continuity_review/README.md)는 미확인 과거 이력의
명시적 수용과 현재 recording Passed/clear를 분리한다.
[Linux 로컬 서비스 연결](test-plan/evidence/m9_continuity_service/README.md)은 kernel peer 인가·
frozen guard·원본 Actual adapter·별도 clear 요청을 연결한다. 실제3-ECU 서비스 owner/SDK
quiesce·새 global Epoch/물리 정지 조합은 [terminal native 서비스](test-plan/evidence/m9_native_service/README.md)에서
부분 검증했다. [이번 후속](test-plan/evidence/m9_completion/README.md)은 최초 TSan support expiry의
원본 원인, 서비스 중 실제 ACK/Actual 손실·Stop 실패 거절, CARLA30 고장4종과 기본 저장 capacity,
BMS9/Power8 component 조합·동일 설정 NormalStop 복구/clear를 다룬다. 실패 분모도 함께 보존한다.
[서비스 순서·시험 IO 후속](test-plan/evidence/m9_service_timing/README.md)의 부모 순서 수정 뒤,
[응답 지연 후속](test-plan/evidence/m9_response_latency/README.md)은 enqueue/RX 알림·SDK trace 버퍼와
monotonic wait를 적용했다. [보조 IO 후속](test-plan/evidence/m9_auxiliary_io/README.md)은 물리 코어
분리와 역할별 marker 조회로 고정30개 중27개를 통과했다. 후속 [입력 snapshot/종료 수정](test-plan/evidence/m9_feedback_order/README.md)은 서비스29/30·기능12/12,
[SDK 직접 계측](test-plan/evidence/m9_timing_trace/README.md)은 서비스28/30·overflow/close-full4/4다.
종료 경합은 이번 Normal/ASan 재시험에서 통과했지만 최종 TSan2개의 원래 command 만료 위반은
남는다. 기록 잠금을 제거해도 SDK send→callback 수ms가 관측돼 SDK IO/dispatcher와 OS scheduling
대기를 분리하는 후속이 필요하다. Host 온도/주파수는 함께 관측하되 단일 원인으로 확정하지 않는다.
Accepted token 통계나 순서/배치 감사 통과를 전체 서비스 수용으로 올리지 않는다.
남은 완료 조건은 native 서비스 TSan timing, silent packet loss의 실제 CARLA subinterval 연결, trusted Clock 복구,
proposal 이전 bootstrap incident, 전체8-role native fault matrix, 실제 부하/장기 보존 정책과
학습자 수용이다. DDS control gate CLOSED는 별도 대안 상태이며 이 SOME/IP 경로의 선행 작업이 아니다.
실제 ACK/전체 통신 손실의 고장 위치·기대 물리 동작은 시험 전에 확정한다.
단순 다음 tick 차단을 차량 정지로 세지 않는다. 검증된 정상 fixture와 무관한 새 경로·
속도·제어 튜닝은 이 묶음에 추가하지 않으며 변경한 경계의 회귀만 실행한다.
