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
| M7-1a | 공식 package/별도 Python 환경·버전/연결·비주행 ego 정상/예외 lifecycle 한정 완료; 원본6시도1PASS/5FAIL 보존 | [실행 근거](test-plan/evidence/m7_carla_1a/README.md) |
| M7-1b | 비주행 RGB/GT/state 수집·tick/센서 lifecycle 완료, fault/pause/reset 부분 검증; 4시도1PASS/3FAIL·native incomplete 보존 | [실행 근거](test-plan/evidence/m7_carla_1b/README.md) |
| M7-1c | test-only Actual/fake backend·원래 Drive 논리 검증 완료: Normal/ASan 각39/39, 관련 기존120/120. 실제 CARLA writer/전송은 NOT RUN | [논리 근거](test-plan/evidence/m7_carla_1c/README.md) |
| M7-1d | world/state10ms·영상50ms 계약 개정 및 비주행 main state600/600·RGB/GT120/120, drop/pause/reset 한정 검증. startup60ms·wall 지연·종료SIGSEGV OPEN | [실행 근거](test-plan/evidence/m7_carla_1d/README.md) |
| M7-1e | wheel 물리 회전각 RPC 원천 확인·4조건×2회 비용 분리·clock 진단 완료. metadata RTF1.014~1.033, 실제 wall 수용 미검증; 빈 서버도 종료139 재현 | [진단/대안](test-plan/evidence/m7_carla_1e/README.md) |
| M7-1f | 별도 functional clock·실제8-role native 세션/credit/Actual 경로·CARLA 비주행 shadow 구현. Normal/ASan 각14/14, 기존144/144와1c39/39. CARLA wheel/actuation은 미연결 | [구현/실행 근거](test-plan/evidence/m7_carla_1f/README.md) |
| M7-1g | 실제 PhysX wheel→native DriveActual→Rear/Central 반환 한정 연결. 내리막400tick·반환396·최대 age10ms. Normal/ASan 각22/22. 평지 음수 측정 연결 FAIL·정상 actuation 미연결 | [원본/실패/남은 gate](test-plan/evidence/m7_carla_1g/README.md) |
| M7-1h | M7 actuator/electrical owner 분리·실제 wheel 기반1ms ZOH 예측 연결. Normal/ASan 각32/32. 평지 SubResolutionNegative 거부 유지; CARLA 실제 work/actuation 미연결 | [구현/실행/제한](test-plan/evidence/m7_carla_1h/README.md) |
| M7 후속–M13 | PLANNED / NOT RUN; 정상 CARLA 주행 연결 BLOCKED | [로드맵](roadmap.md) |

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

**다음은 M7-1i 정상 actuation 방식과 sensor 오차/validity 근거 확정**.
[M7-1h](test-plan/evidence/m7_carla_1h/README.md)에서 별도 actuator/electrical owner를 구현했다.
차량 운동을 중복 적분하지 않고, 전기 모델에 각1ms 구간 begin 이전의 실제 wheel 원천을 넣는다.
400tick의3,989구간을 독립 ZOH oracle로 확인했다. 이 에너지는 CARLA에 적용되지 않은 모델 예측이다.
Normal/ASan 각32/32, 기존 관련144/144·1c39/39. 미세 음수는 zero-bin 진단 후 거부하며
평지 문제를0 clamp로 감추지 않았다. rad/Nm/Pa 변환·applied Actual receipt/interval work와
정지 부근 signed sensor의 근거 있는 오차/validity 결정이 남는다. source build는 하지 않았다.

[M7-1g](test-plan/evidence/m7_carla_1g/README.md)에서 직접 PhysX omega를 기존 Drive 센서에
연결했다. 내리막400tick에서 원래 vECU·CAN/P05·Rear·Central Actual 반환을 확인했다.
중력 이동이며 controller가 CARLA를 가속한 결과는 아니다. fractional timestamp의 pending
덮어쓰기 버그를 수정했으며 Normal/ASan 각22/22와 기존 관련144/144·1c39/39를 확인했다.
평지에서는 미세 음수 wheel로 기존 전진 전용 검증이 거부한다. 정지 잡음/측정 분해능 계약,
실제 CARLA work 연결, rad/Nm/Pa 역변환·full Actual interval gate가 남는다.1h의 포트 분리는 위 범위만 수용한다.
임의 epsilon/clamp나 명령 우회는 추가하지 않았다.6live 시도의 실패3개와 서버 종료139를 보존했다.

[M7-1f](test-plan/evidence/m7_carla_1f/README.md)에서 별도 opt-in simulation-clock shadow를
구현했다. 원래 native8-role actor의 INIT/Release ACK/RunLease/arm·Actual 반환 경로를
stationary SIL fixture로 실행하며 CARLA10ms tick 전 barrier를 확인한다.100ms Host 지연·
250ms pause에도 logical age/권한을 유지하고, 누락·중복은 다음 tick을 차단한다.
1f 당시에는 CARLA wheel을 입력으로 사용하지 않았고,1g가 센서 입력만 연결했다. Actual의 CARLA 적용은 미연결이다.
M6 wall runtime·2ms/4ms guard·30ms freshness는 그대로다. 기능 검증의 시간 진행 경로는
확보했지만 calibrated normal driving이나 실제 wall 성능 수용은 미완료다.

[M7-1e 진단](test-plan/evidence/m7_carla_1e/README.md)에서 physics-on wheel 회전각 RPC 원천을
확인했다.1g에서는 직접 omega를 선택해 각도 차분을 사용하지 않는다. 전체 ODD/측정 validity는 미검증이다. 영상 audit을 뺀1e 정적 수집은
RTF1.014~1.033, 각400tick에서30ms 초과0이지만 max26.654ms로 실제 ECU 여유는 작다.
전체 실행에서 platform→monotonic 고정 offset 가정은 불일치했다.1f의 simulation clock은
이 mapping을 사용하지 않는 별도 모드이며, 현재 M6 wall 실행 계약을 변경한 것은 아니다.

[M7-1d](test-plan/evidence/m7_carla_1d/README.md)는 사용자 승인으로 world/state10ms·영상50ms를
채택했다. 본 관측 state600/600·RGB/GT 각120/120, 누락·pause/reset을 한정 검증했다.
최초 camera 간격60ms는 startup 변동으로 보존하며 첫 oracle FAIL과 수정 후 확인 실행을 구분한다.
1d 당시 논리 sampling 충돌은 제거했으나 실제 ECU 적합은 NOT RUN이었다.1g wheel 논리 경로의 한정 검증과 wall 수용을 구분한다.1d 최종 nominal RTF0.764923,
pause 제외 snapshot 완료 간격>30ms12/798이며 wall100Hz 수용이 아니다.
[M7-1c](test-plan/evidence/m7_carla_1c/README.md)의 native Drive stale/latch 결과와 M6 계약은 유지한다.
실제 Central→Zone→vECU→CARLA 전송·writer/권한·calibration·중복 dynamics/energy는 미검증이다.

**OPEN-M7-1D-01:** actor0·world 설정 복원 확인 뒤 서버 SIGTERM 종료 중 native SIGSEGV/139.
M7-1e의 빈 서버SIGTERM/빈 서버SIGINT/진단 후SIGTERM 새3프로세스에서도139를 관측했다.
센서/reset 없이 재현되며 root cause는 미확정이다. 현재 서버/포트는 정리됐다.
M7-1a/b/c의 원본 실패와 OPEN-M7-1B-01/02는 그대로 유지한다.
정상 CARLA 주행 연결은 wheel 정지 잡음/ODD validity·full Actual dependency/interval·calibration 입증 전까지
**BLOCKED**다. wall 모드에는 source clock mapping·native2ms/4ms guard 검증도 별도로 필요하다.
functional 모드의 성공으로 wall gate를 면제하지 않는다. M6 종료·코드·수치·판정은 변경하지 않았다.
