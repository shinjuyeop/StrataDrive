# 프로젝트 상태

정리 기준: **2026-10-29**, 검증 근거: 2026-10-28까지 저장된 실행 결과. 작업 중인 10-29 변경은 별도 표시한다.
이 문서가 현재 구현·수용 범위와 다음 작업의 기준이다. 실행 중인 미기록 변경은 완료로 세지 않는다.

## 단계별 현재 판정

| 단계 | 판정 | 근거 |
| --- | --- | --- |
| M0 | 요구·구조 baseline 확정 | [M0 검토](archive/milestone-reviews.md#m0) |
| M1–M2 | 통신·actuator/EV component 기술 검사 완료; 학습자 review 별도 | [M2 검토](archive/milestone-reviews.md#m2) |
| M3 | Host FIFO 기준 사용; 과거 timing 예외·전체 종료 OPEN | [M3 검토](archive/milestone-reviews.md#m3) |
| M4 | Host IO/FIFO component 한정 수용; 전체 NOT CLOSED | [Host 수용](archive/milestone-reviews.md#m4-host) · [종료 검토](archive/milestone-reviews.md#m4) |
| M5 | Central↔Front/Rear 3-process SOME/IP Host FIFO 기능 한정 수용 | [실행 근거](test-plan/evidence/m5_someip_rear_adapter/README.md) |
| M6 | **Host quiet SIL/Python MIL 범위 CLOSED** | [종료 검토](archive/milestone-reviews.md#m6) · [최종 물리 응답](test-plan/evidence/m6_physical_response/README.md) |
| M7 | **시뮬레이션 시간 기능 통합 검증 진행; 실시간 수용은 별도 OPEN** | 아래 결과·종료 조건과 [ADR-0065](archive/design-decisions.md#adr-0065) |
| M8–M13 | PLANNED / NOT RUN | [로드맵](roadmap.md) |

기술 검사와 학습자 설명·수용은 별도다. Component PASS를 전체 system/Target PASS로 올리지 않는다.

## 구현·검증한 범위

Central은 조정·배분·영속 Epoch·8-role 세션과 RunLease를 소유한다.
Front는 Steering/Brake, Rear는 Drive/BMS/Power를 별도 process에서 단독 소유한다.
실제 SOME/IP·IP·owner-wire·CAN/P05 경계로 INIT/Release ACK/credit/arm,
명령·Actual·health·로컬 보호와 새 Epoch 재가입을 연결했다.

M6에서는 persistent physical process가 actuator·SimpleVehicle·EV/Battery를 소유하고
같은 구간 motor work로 차량과 전기 에너지를 결합한다. 실제 wheel feedback이 Central로 돌아온다.
최종 C++ Normal/ASan 각1018/1018, 계측 TSan 경계35/35, Python/무build export 각54/54는
[해당 quiet fixture의 근거](test-plan/evidence/m6_physical_response/README.md)다.
100ms loss 검출과 230ms 물리 응답의 기점·범위는 [물리 계약](interfaces/vehicle-energy.md#physical-response-contract)을 따른다.
실제 C++ 속도 폐루프는 미구현이며 Python 종방향 PI/MIL은 별도 모델이다.

## M7 CARLA 통합 결과

| 범위 | 확인한 결과 | 실행 근거 |
| --- | --- | --- |
| 기능 주행·에너지·영상 | 고정 VehicleRequest → 실제8-role Actual → NoDrive → solver work → 단일 EV. 가속·회생·마찰 제동·휠 정지·재출발과 RGB/GT 검증 | [통합 실행](test-plan/evidence/m7_carla_integrated/README.md) |
| 보호 Actual·로딩 중 종료 | 기능 clock의 보호 Actual 연속 적용, 로딩 중 sync RPC 종료 교착 수정·검증 | [수정·실행](test-plan/evidence/m7_carla_recovery/README.md) · [요청 인과 검증](test-plan/evidence/m7_carla_recovery/causal-followup/README.md) |
| 보호 정지·client-loss 종료 | opt-in 보호 hold에서 body/wheel exact0·pose 유지; client 단절 시 동기 tick 종료 교착 수정. 고정 Town03/V1 범위 FIXED_LIMITED | [일괄 검증](test-plan/evidence/m7_carla_recovery/batch-closeout/README.md) |
| 독립 wall 감시 | 2ms/4ms 감시 → 로컬 보호 선택 → 다음 tick 차단. Terminal native owner는 입력 단절 뒤에도 보호 Actual 생성 | [wall guard](test-plan/evidence/m7_carla_wall_guard/README.md) · [terminal 응답](test-plan/evidence/m7_carla_wall_guard/terminal-response/README.md) |
| 증거 전달 최적화 | Raw solver journal 회수와 compact 전달을 분리하고 기존 physics/work/Actual 동등성 검증. 정상 wall timing 수용은 아님 | [전달 경로](test-plan/evidence/m7_carla_wall_guard/pipeline/README.md) |
| Wall owner component | 실제 monotonic timer·분리된 IO·유한 mailbox, 원래8-role service와 보호·완료 work 정산 검증. 합성 stationary 입력 범위 | [component 실행](test-plan/evidence/m7_carla_wall_guard/wall-owner/README.md) |
| 실제 CARLA wall 연결 | model10ms work와 원래 monotonic 취득을 분리해 공유 전달. **엔진 프레임 공백으로 Drive30ms 근거 만료, 정상 wall 주행 FAIL** | [최신 실행·실패](test-plan/evidence/m7_carla_wall_guard/carla-runtime/README.md) |

기능 시험의 정상5실행은 각각900구간, 약4.77215m 이동·최대 전방 속도 약1.259m/s다.
영상2실행은 각각 RGB180/GT180이다. Reference 30km/h 추종이나 전체 ODD 검증은 아니다.
마지막 wall 연결의 Normal/ASan 각113/113·TSan 경계26/26과 정상901/보호401개 replay 일치는
component/회귀 근거이며 실제 wall 주행 성공을 뜻하지 않는다.

## 남은 문제와 제한

| 항목 | 현재 처리 |
| --- | --- |
| 엔진 프레임 공백 | 정상 wall 주행의 직접 차단 원인. Render fence 대기는 관측했지만 FIFO·예열·null-RHI·inline-render 비교로 원인 제거를 증명하지 못함 |
| Clock·실시간 실행 | simulation elapsed와 CLOCK_MONOTONIC을 분리. 고정 offset·heartbeat·timeout 증가로 2ms/4ms·30ms 수용을 대신할 수 없음 |
| Wall fault 후 실제 제동 | 정상 wall 세션 → LocalProtection Actual → CARLA 연속 적용·정지의 통합 수용 OPEN. 초기화 실패에서 unavailable Actual을 만들어 적용하지 않음 |
| Renderer | 과거 Distance Field SIGSEGV 원인 미확정. 짧은 영상 성공을 전체 content/장시간 안정성으로 확대하지 않음 |
| 과거 M3/M4·SDK | timing/FIFO·native·SDK sanitizer 기능 미완료 OPEN은 각 당시 분모·실패와 함께 보존 |
| DDS | 정규 제어 gate CLOSED, adapter 미착수. 기존 종료·20ms·TSan FAIL 및 접근 제한 이력 유지 |
| 전체 시스템·Target | 32개 요구/29개 system TC, Jetson·실제 IO·Host–Target 검증은 NOT RUN. C++ 제어/AI도 후속 |

## M7 종료 조건

[ADR-0065](archive/design-decisions.md#adr-0065)는 같은 simulation time의 기능 통합을 먼저 완성하고
실제 시간 연동을 별도 검증하는 순서다. 작업 트리에 `--simulation-time`/연속 실행 구현이 추가되고
있지만 **새 실행 근거가 저장되기 전에는 수용 완료로 세지 않는다.**

1. 같은 세션의 연속 정상·영상 실행에서 원래8-role Actual·단일 writer·완전한 solver work/단일 EV 정산을 검증한다.
2. 보호 Actual의 자연 제동·정지, sensor/work 누락·pause/reset·응답 정지 시 차단/정리와 기존 회귀를 함께 판정한다.

Controller20ms·Zone/vECU10ms·world10ms·영상50ms·source30ms·exclusive expiry를 원래
simulation domain에서 유지한다. 늦은 실행을 새 source로 restamp하거나 가짜 Actual·두 번째 plant로
메우지 않는다. 실제 실행 지연과 watchdog/종료 결과를 따로 기록한다.
상세 계약은 [시뮬레이션 시간 연속 실행](interfaces/carla-plant-adapter.md#시뮬레이션-시간-연속-실행)에 있다.

**다음 작업은 이 기능 profile의 연속 실행·fault 검증과 근거 수집**이다. 실제 wall30ms·owner2ms/4ms,
정상 wall 세션의 보호 제동/정지는 별도 OPEN으로 유지한다. 이 후속에서는 엔진 프레임 공백을
해결한 정상·영상 wall 실행과 queued/in-flight work·sensor/writer/lifecycle을 함께 검증해야 한다.
기존 wall FAIL과 M6 구현·수용 기준은 바꾸지 않는다.
