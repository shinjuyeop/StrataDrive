# Project status

Updated: **2026-10-23**. 현재 구현·수용 범위의 대표 문서다.
단계/TBD는 [로드맵](roadmap.md), 종료 판단은 아래 review, 실행 원본·과거 분모는 각 evidence와
[품질 이력](quality_policy.md)을 따른다. 이력의 당시 미구현/FAIL을 현재 상태로 해석하지 않는다.

## Milestone 현황

| 범위 | 현재 판정 | 근거 |
| --- | --- | --- |
| M0 | BASELINED | [M0 검토](m0_baseline.md) |
| M1/M2 | Host 기술 검사 완료, 학습자 review 별도 | [M2 검토](m2_acceptance_review.md) |
| M3 | Host FIFO 기준 사용, 전체 종료/과거 timing 예외 OPEN | [M3 검토](m3_acceptance_review.md) |
| M4 | Host native IO/FIFO component 한정 수용, **전체 NOT CLOSED** | [한정 수용](m4_host_acceptance_review.md), [종료 검토](m4_exit_review.md) |
| M5 | **Central↔Front/Rear 3-vECU SOME/IP Host FIFO 기능 한정 수용, Rear 연결 완료** | [3-vECU/부하·고장·재가입 근거](test-plan/evidence/m5_someip_rear_adapter/README.md), [ADR-0062](adr/ADR-0062-someip-rear-host-adapter.md) |
| M6 | **Host quiet SIL/Python MIL 범위 CLOSED** | [종료 검토표·TBD 분할·제한](m6_exit_review.md) |
| M7-0 | 환경 조사·ICD 초안·M7-1 계획 작성 완료; CARLA runtime NOT RUN | [조사/시험 계획](test-plan/m7_carla_preflight.md), [Plant Adapter ICD](icd/carla_plant_adapter.md) |
| M7-1 이후–M13 | PLANNED / NOT RUN; 정상 CARLA 주행 연결 BLOCKED | [로드맵](roadmap.md) |

## 구현·시험한 범위

Central은 조정·배분·SessionCoordinator/영속 Epoch·RunLease 발급을 소유한다.
Front는 FrontZone/Steering/Brake, Rear는 RearZone/Drive/BMS/Power를 별도 프로세스에서
단독 소유한다. 실제 IP/SOME/IP/owner-wire/CAN/P05 경계를 통해 실제8참여자의
INIT/Release ACK/credit/arm, 명령·Actual/health·보호·새 Epoch 재가입을 연결했다.

Persistent SIL physical process가 actuator·센서·SimpleVehicle·EV/Battery를 소유하고
동일 구간 motor work로 차량/전기 에너지를 결합한다. 실제 wheel feedback이 Central에 돌아온다.
SIL 입력 시나리오와 물리·센서 bus는 fixture이며 명령·권한 전달을 우회하지 않는다.
실제 C++ 속도 폐루프는 미구현이다. Python 종방향 PI/MIL은 별도 모델이며 M8 동등성과 구분한다.
[배포/실행 경계](architecture/deployment_architecture.md), [M6 모델 계약](icd/vehicle_energy.md)을 따른다.

## 검증 결과와 한계

M6 최종 [물리 응답 근거](test-plan/evidence/m6_physical_response/README.md):
전체 C++ Normal/ASan 각1018/1018, 실제 계측 TSan 경계35/35,
Python/무build export 각54/54. SDK 신규3회2PASS/1FAIL이며 수정 후 command-loss1/1과
영향 없는 nominal1/1이 수용 근거다. 과거 원본·분모는 합쳐 PASS로 바꾸지 않았다.
100ms loss 검출/230ms 실제 보호 응답의 기점·모델 범위는 [물리 계약](icd/vehicle_energy.md#physical-response-contract)에 있다.
M6는 quiet 범위이며 M5의 제한된 부하 수용을 다른 workload로 확장하지 않는다.

| 남은 문제/제한 | 현재 처리와 근거 |
| --- | --- |
| OPEN-M6-ENERGY-01 | 현재 모델/응답 판정 불일치 범위 해소. 옛100ms FAIL·옛1MPa 미관측은 보존 |
| OPEN-M6-ENERGY-02 | 실제 instrumented SDK의 wall/송수신·SDK 오류/기능 미완료 OPEN. 경계 sanitizer PASS로 대체하지 않음; [원본](test-plan/evidence/m6_vehicle_energy/README.md) |
| M4·M3 과거 timing/FIFO/native/physical pause | 역사적 OPEN 유지. 후속 통과로 과거 원인 해소를 주장하지 않음; [M4 검토](m4_exit_review.md), [native 근거](test-plan/evidence/m5_someip_native_watch/README.md) |
| DDS | **정규 제어 gate CLOSED, adapter 미착수**. 종료/20ms/TSan FAIL·접근 제한 이력 보존; [DDS 후속](test-plan/evidence/m5_dds_shutdown_followup/README.md). 제한된 작업을 우회·재시도하지 않음 |
| Target/전체 시스템 | Jetson·실제 IO·Host–Target 검증,32req/29system TC는 NOT RUN. 학습자 설명/수용은 기술 판정과 별도 |

## 다음 작업

**M7-1: 비주행 CARLA 연결·센서 수집·경계 시험 준비**.
[M7-0 조사](test-plan/m7_carla_preflight.md)에서 Host Ubuntu22.04.5/i7-11700/RTX3090 24GB/
RAM32GB를 확인했다. CARLA0.9.16·Client0.9.16/Python3.10·ScenarioRunner v0.9.16을 후보로
유지하며 설치/실행은 NOT RUN이다. [ICD 초안](icd/carla_plant_adapter.md)은 actual-only·단일 writer,
50ms tick·20/10ms 주기·GT 분리·원천 metadata를 유지한다. **20Hz state→Drive30ms freshness와
50ms interval의 실제 actuation 갱신, Nm/Pa calibration·중복 dynamics/energy는 미해결**이므로
정상 주행 연결은 차단한다. M7-1 비주행/negative 시험은 착수 가능하다.
기존 M6 종료·수치·OPEN과 요구사항을 변경하지 않았으며 CARLA 시험 PASS는 없다.
