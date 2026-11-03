# 검증 안내

현재 수용 판정·OPEN은 [프로젝트 상태](../project-status.md), 시험 방법과 기준은
[검증 전략](verification-strategy.md)·[시나리오](scenario-baseline.md)·[추적성](requirements-traceability.md)을 따른다.
함수/구체 test/판정/evidence 연결은 [component 추적표](component-traceability.csv)에 있다.

M8의 범위별 완료·후속 이관은 [종료 검토표](../archive/milestone-reviews.md#m8),
source/원본 증거의 최종 대조는 [마감 기록](evidence/m8_closeout/README.md)을 따른다.

M9는 [진단 계약](../interfaces/diagnostics.md)과
[component·통합 검증 프로토콜](diagnostics-protocol.md)을 따른다. Central hook·SimpleVehicle 연결 뒤
CARLA30km/h fault matrix와 실제 transport 진단 수집은 후속이다.

## 대표 실행 결과

| 찾는 내용 | 실행 원본·재현 |
| --- | --- |
| M9 유한 event/DTC 집계·Linux journal·clear·queue TSan | [component 검증](evidence/m9_diagnostics_component/README.md) |
| M9 SpeedRequest/NormalStop 검출 hook·SimpleVehicle 입력 누락·원본 보호/Actual·DTC | [연결 검증](evidence/m9_control_hooks/README.md) |
| M9 SD-1001 입력 복원·INIT·Passed·명시적 clear·writer 재시작·재고장 | [연속 복구 검증](evidence/m9_speed_recovery/README.md) |
| M9 Zone/Leaf 소유자별 원본 검출·전달 구분·SD-2001/2002/4002 복구 | [소유자 경계 검증](evidence/m9_owner_sources/README.md) |
| M9 Gateway native/ACK/차량 응답·BMS/Power component 복구·registry2 | [native 원인 검증](evidence/m9_native_causes/README.md) |
| M9 BMS electrical/Power current 누락·차량 보호/정지/HV·새 INIT 복구 | [차량 입력 손실 검증](evidence/m9_native_vehicle/README.md) |
| M9 Release 전 Attempt·기동 ACK 누락·최초 deadline·실제 새 Release 복구 | [기동 진단 검증](evidence/m9_startup_sources/README.md) |
| M9 Event-only wire·유한 spool·commit 후 ACK 유실·송수신 process 재시작 | [전송·spool 검증](evidence/m9_delivery_spool/README.md) |
| M9 실제 SOME/IP/TCP·새 logical source·live writer·ACK 유실/replica 재시작 | [SOME/IP 진단 검증](evidence/m9_someip_live/README.md) |
| M9 원격 accepted credit·Central 원본 context 대조·유한 대기·두 stream 독립 ACK | [원격 context component](evidence/m9_remote_context/README.md) |
| M9 실제 native3-ECU·context2/source9·원본 검출/ACK·TCP·merged journal | [native 진단 배선](evidence/m9_native_routing/README.md) |
| M9 진단 전달 객체 재개·원본 재전송·source/replica/merged SIGKILL 경계 | [전달 이력 복구](evidence/m9_delivery_restart/README.md) |
| 실제3-process SOME/IP·8-role·부하/고장/재가입 | [M5 Rear adapter](evidence/m5_someip_rear_adapter/README.md) |
| M6 모델·Python MIL | [SimpleVehicle](evidence/m6_simple_vehicle/README.md) |
| M6 에너지·회로·물리 응답 최종 판정 | [물리 응답](evidence/m6_physical_response/README.md) · [이전 energy 실패 포함](evidence/m6_vehicle_energy/README.md) |
| M7 기능 주행·회생·제동·영상 | [통합 실행](evidence/m7_carla_integrated/README.md) |
| M7 시뮬레이션 시간 연속 주행·영상·보호·고장 7개 시험 | [연속 실행](evidence/m7_carla_integrated/simulation-time/README.md) |
| M7 보호 Actual·로딩 중 종료 | [Recovery](evidence/m7_carla_recovery/README.md) · [요청 인과 보완](evidence/m7_carla_recovery/causal-followup/README.md) |
| M7 보호 hold 정지·client-loss 종료 | [일괄 검증](evidence/m7_carla_recovery/batch-closeout/README.md) |
| Wall 감시·입력 단절 뒤 native 보호 | [wall guard](evidence/m7_carla_wall_guard/README.md) · [terminal 응답](evidence/m7_carla_wall_guard/terminal-response/README.md) |
| Solver 전달 분리·physics/work 동등성 | [Pipeline](evidence/m7_carla_wall_guard/pipeline/README.md) |
| Wall owner timer·IO component | [Wall owner](evidence/m7_carla_wall_guard/wall-owner/README.md) |
| 실제 CARLA wall10ms 연결 실패 | [CARLA runtime](evidence/m7_carla_wall_guard/carla-runtime/README.md) |
| 비영상 wall5ms 정상·보호 정지와 반복/종료 실패 | [비영상 wall 개선](evidence/m7_carla_wall_guard/carla-runtime/nonvideo-wall5/README.md) |
| CARLA HV source/dependency 예산 분리·정상2/보호2 실행 | [wall5-hv50-v1 결과](evidence/m7_carla_wall_guard/carla-runtime/hv-budget-v1/README.md) |
| CARLA 기본 state·영상·확장 경로 지연 대조 | [Frame 진단](evidence/m7_carla_wall_guard/carla-runtime/frame-diagnostic/README.md) |
| M8 전 공통 구현·빌드·감사 reader 정리와 회귀 | [리팩터링 검증](evidence/pre-m8-refactor/README.md) |
| M8 별도30km/h NormalStop·10s 제동 계약 | [실행 근거](evidence/m8_stop30/README.md) · [protocol](carla-stop30-protocol.md) |
| M8 정지 hold 이후 보호 전환·30km/h 예산 계약 검토 | [실행 근거](evidence/m8_stop_fault/README.md) · [protocol](carla-stop-fault-protocol.md) · [30km/h 검토](normal-stop-30-contract-review.md) |
| M8 저속 NormalStop/HV-off·현재 속도 입력 누락의 물리 정지 | [실행 근거](evidence/m8_stop/README.md) · [protocol](carla-stop-protocol.md) |
| M8 추진 배분 포화·참조 필요조건 | [실행 근거](evidence/m8_saturation/README.md) · [protocol](propulsion-saturation-protocol.md) |
| M8 S01 직선·S03 위치 기반30→20km/h·구동 포화 실패와 v2 | [실행 근거](evidence/m8_reference/README.md) · [protocol](carla-reference-protocol.md) |
| M8 고정 곡선30km/h·Pure Pursuit·pose 시각 불일치 | [실행 근거](evidence/m8_route/README.md) · [protocol](carla-route-protocol.md) |
| M8 CARLA V1 저속 속도 폐루프·원천/계산 시각·snapshot/work 누락 | [실제 CARLA 실행](evidence/m8_carla_speed/README.md) · [protocol](carla-speed-protocol.md) |
| M8 SimpleVehicle 속도 폐루프·Actual/명령 손실·NormalStop | [논리 시간 폐루프](evidence/m8_speed_loop/README.md) · [protocol](speed-loop-protocol.md) |
| M8 종방향 PI의 Python/C++ 출력·상태·고장/INIT 동등성 | [SpeedPI component](evidence/m8_speed_pi/README.md) · [사전 protocol](longitudinal-equivalence-protocol.md) |
| DDS 제어 gate CLOSED의 근거 | [DDS shutdown 후속](evidence/m5_dds_shutdown_followup/README.md) |

## Evidence 보관 규칙

`evidence/`는 과거 실행별 디렉터리다. 이름을 새 단계로 바꾸거나 실패를 최신 통과로 덮어쓰지 않는다.
README는 당시 판정/재현과 탐색용이고, raw CSV/log·sensor·JSON·source snapshot·hash는 실행 증거다.
현재 결과와 과거 분모를 합쳐 전체 PASS로 표시하지 않는다. 무결성 목록이 있는 실행은 해당 SHA를 확인한다.

M7-1a–1s는 환경/센서 → clock·native 반환 → source/NoDrive → geometry/V1 → solver/EV/lifecycle의
당시 개별 시험이다. 세부 재현이 필요할 때 해당 `evidence/m7_carla_1*/README.md`를 찾는다.
과거 사전 계획은 [보관 문서](../archive/README.md)로 이동했고, 현재 CARLA 재실행은
[실행 안내](../carla-guide.md)를 따른다.
