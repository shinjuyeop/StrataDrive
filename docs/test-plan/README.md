# 검증 안내

현재 수용 판정·OPEN은 [프로젝트 상태](../project-status.md), 시험 방법과 기준은
[검증 전략](verification-strategy.md)·[시나리오](scenario-baseline.md)·[추적성](requirements-traceability.md)을 따른다.
함수/구체 test/판정/evidence 연결은 [component 추적표](component-traceability.csv)에 있다.

## 대표 실행 결과

| 찾는 내용 | 실행 원본·재현 |
| --- | --- |
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
| 최신 실제 CARLA wall 연결 실패 | [CARLA runtime](evidence/m7_carla_wall_guard/carla-runtime/README.md) |
| DDS 제어 gate CLOSED의 근거 | [DDS shutdown 후속](evidence/m5_dds_shutdown_followup/README.md) |

## Evidence 보관 규칙

`evidence/`는 과거 실행별 디렉터리다. 이름을 새 단계로 바꾸거나 실패를 최신 통과로 덮어쓰지 않는다.
README는 당시 판정/재현과 탐색용이고, raw CSV/log·sensor·JSON·source snapshot·hash는 실행 증거다.
현재 결과와 과거 분모를 합쳐 전체 PASS로 표시하지 않는다. 무결성 목록이 있는 실행은 해당 SHA를 확인한다.

M7-1a–1s는 환경/센서 → clock·native 반환 → source/NoDrive → geometry/V1 → solver/EV/lifecycle의
당시 개별 시험이다. 세부 재현이 필요할 때 해당 `evidence/m7_carla_1*/README.md`를 찾는다.
과거 사전 계획은 [보관 문서](../archive/README.md)로 이동했고, 현재 CARLA 재실행은
[실행 안내](../carla-guide.md)를 따른다.
