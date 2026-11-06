# 검증 안내

현재 수용 판정·OPEN은 [프로젝트 상태](../project-status.md) 한곳에서 관리한다.
시험 방법은 [검증 전략](verification-strategy.md), 고정 입력은 [시나리오](scenario-baseline.md),
요구와 구체 test/evidence 연결은 [추적성](requirements-traceability.md)·[component 추적표](component-traceability.csv)를 따른다.

## 대표 실행 결과

| 수용 범위 | 원본·재현·제한 |
| --- | --- |
| Native 속도 감독 운영 연결 | [BMS 가용력·보호·DTC와 실제 CARLA 두 실행](evidence/runtime-speed-connection/README.md) |
| 선택형 기록 이관·가용력 목표·M10 Host 착수 | [상태 보존·기존 제어 연결·제약](evidence/remaining-improvements/README.md) |
| 이전 milestone 소프트웨어 후속 | [제동 피드백·저장 실패/중단 경계](evidence/milestone-followup/README.md) |
| M9 이후 문서·진단 코드 정리 | [공통 발행기·decoder 동등성·회귀](evidence/post-m9-refactor/README.md) |
| M9 유한 Host·simulation10ms 마감 | [SDK 부하7/7·서비스18/18·CARLA4/4](evidence/m9_followup/README.md) |
| M9 Clock/Power 복구·비활성 기록 보존 | [차량 조합·archive/restore·선행 부하 실패](evidence/m9_remaining/README.md) |
| M8 제어기·고정 fixture 기능 SIL | [종료 검토](../archive/milestone-reviews.md#m8) · [마감 무결성](evidence/m8_closeout/README.md) |
| M7 simulation-time 기능 | [연속 주행·영상·보호·고장7조건](evidence/m7_carla_integrated/simulation-time/README.md) |
| M7 제한 wall 실행 | [비영상 wall5-hv50-v1](evidence/m7_carla_wall_guard/carla-runtime/hv-budget-v1/README.md) |
| M6 Host SIL/Python MIL | [SimpleVehicle](evidence/m6_simple_vehicle/README.md) · [최종 물리 응답](evidence/m6_physical_response/README.md) |
| M5 3-process SOME/IP·8-role | [Rear adapter](evidence/m5_someip_rear_adapter/README.md) |

## 진단 분야별 근거

M9는 [Fault event/DTC 계약](../interfaces/diagnostics.md)과
[component·통합 프로토콜](diagnostics-protocol.md)을 기준으로 검증했다.
정상 성공과 고장에 대한 예상 거절, 기능과 wall 성능, sanitizer 검사는 구분한다.

| 경계 | 근거·고정 조건 |
| --- | --- |
| 집계·기록·clear·재고장 | [component](evidence/m9_diagnostics_component/README.md) · [Speed 복구/clear](evidence/m9_speed_recovery/README.md) |
| 소유자별 실제 검출·보호·차량 응답 | [Owner](evidence/m9_owner_sources/README.md) · [Gateway/BMS/Power](evidence/m9_native_causes/README.md) · [센서 matrix](evidence/m9_sensor_matrix/README.md) |
| 기동·Clock·Power lifecycle | [Startup](evidence/m9_startup_sources/README.md) · [Clock](clock-recovery-protocol.md) · [Power](power-lifecycle-vehicle-protocol.md) |
| 전달·재기동·연속성 | [native 배선](evidence/m9_native_routing/README.md) · [발행자 adoption](evidence/m9_producer_adoption/README.md) · [Central 재기동](evidence/m9_central_restart/README.md) |
| 인가·심사·명시적 해제 | [로컬 서비스](evidence/m9_continuity_service/README.md) · [서비스/sanitizer 분리](service-validation-protocol.md) |
| CARLA 실제 fault chain | [입력·ACK/link·제동 timeout](evidence/m9_completion/README.md) · [silent loss·10ms 수용 계약](carla-sampled-actual-protocol.md) |
| SDK 부하와 실제 응답 | [FIFO1 배치](sdk-fifo-protocol.md) · [유한 soak](service-soak-protocol.md) · [응답 감사](service-response-protocol.md) |
| 저장 실패·유한 보존 | [Proposal 이전 incident](evidence/m9_bootstrap/README.md) · [archive/restore](diagnostic-retention-protocol.md) |

세부 개발 순서·실패·미채택 후보와 전체 과거 실행 목록은
[구현·검증 이력](../archive/implementation-history.md#과거-실행-근거-찾기)에 모았다.
이전 분모와 최신 수용 결과를 합쳐 전체 PASS로 표시하지 않는다.

## Evidence 보관 규칙

`evidence/`는 실행별 원본이다. 디렉터리 이름·timestamp·source snapshot·hash를 바꾸거나
실패를 최신 통과로 덮어쓰지 않는다. README는 당시 판정과 재현 방법이며, raw CSV/log·센서·
JSON·journal은 실행 증거다. Git LFS 파일을 받은 뒤 각 `SHA256SUMS`로 무결성을 확인한다.

M7-1a–1s 등 고정 식별자는 당시 개별 시험에 유지한다. 현존 runner가 읽는 protocol 경로도
그대로 둔다. 현재 CARLA 재실행은 [실행 안내](../carla-guide.md), 문서·코드 변경 원칙은
[개발 정책](../development-guide.md)을 따른다.
