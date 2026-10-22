# Project status

Updated: **2026-10-22**. 현재 구현·수용 범위의 대표 문서다.
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
| M7–M13 | PLANNED / NOT RUN | [로드맵](roadmap.md) |

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

**M7 첫 작업: CARLA 접속 전 호환 환경과 actual-only/synchronous bridge 계약 확정**.
[종료 검토의 선행 조건](m6_exit_review.md#다음-한-단계--m7-최초-접속-계약과-환경-확인)에 따라
버전/GPU,50ms tick·단일 writer·좌표/단위/dynamics 소유권,20Hz state와 원래30ms freshness의
경계를 먼저 확인한다. M7 구현은 아직 시작하지 않았다. 과거 OPEN 전체 해결이나 새 극단 시험을
이 첫 작업의 선행 조건으로 추가하지 않는다.
