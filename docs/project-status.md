# 프로젝트 상태

정리 기준·최신 검증: **2026-10-29**.
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
| M7 | **시뮬레이션 시간 기능 통합 CLOSED / 실제 wall 실시간 수용 별도 OPEN** | [7개 실제 실행·독립 감사](test-plan/evidence/m7_carla_integrated/simulation-time/README.md) · [ADR-0065](archive/design-decisions.md#adr-0065) |
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

사용자 승인 [ADR-0065](archive/design-decisions.md#adr-0065)에 따라 M7 기능 종료와 wall 실시간 수용을
분리한다. `m7-simulation-time-v1`의 실제7개 case가 통과했다. 비영상·영상 각각 한 세션60s/
6000 physics·6000 EV 정산, INIT 이후 정상5919구간, 가속·회생·제동·재출발6주기다.
영상은 RGB/GT 각1200개이며 원본 frame/timestamp 일치·누락0이다.
보호 시험은400구간 중 index278부터 자연 sleep122구간, 마지막100구간 동일 pose를 확인했다.
RGB 누락·stale snapshot·불완전 work·native SIGSTOP/실제10s 응답 감시 모두 다음 tick을 차단했다.
마지막 세 고장에는 완료 physics1구간의 EV 미정산을 남겼으며 완전한 에너지 정산이나 실제 정지로 세지 않는다.

Normal/ASan 각114/114, 연속성·session·숨은 reset·timestamp·정상 권한 손상6/6 거부.
비영상/영상60s의 실제 loop는 약213.88/244.37s였다. 원본320 substep 기록·검증과 의도적 pause를
포함한 관측값이며 CARLA 단독 성능 benchmark나 실시간 보장이 아니다.
[전체 원본·분모·재현](test-plan/evidence/m7_carla_integrated/simulation-time/README.md)을 따른다.

아래는 이전 통합과 별도 실시간 경로의 근거다. 새 기능 수용으로 과거 실패를 바꾸지 않는다.

| 범위 | 확인한 결과 | 실행 근거 |
| --- | --- | --- |
| 기능 주행·에너지·영상 | 고정 VehicleRequest → 실제8-role Actual → NoDrive → solver work → 단일 EV. 가속·회생·마찰 제동·휠 정지·재출발과 RGB/GT 검증 | [통합 실행](test-plan/evidence/m7_carla_integrated/README.md) |
| 보호 Actual·로딩 중 종료 | 기능 clock의 보호 Actual 연속 적용, 로딩 중 sync RPC 종료 교착 수정·검증 | [수정·실행](test-plan/evidence/m7_carla_recovery/README.md) · [요청 인과 검증](test-plan/evidence/m7_carla_recovery/causal-followup/README.md) |
| 보호 정지·client-loss 종료 | opt-in 보호 hold에서 body/wheel exact0·pose 유지; client 단절 시 동기 tick 종료 교착 수정. 고정 Town03/V1 범위 FIXED_LIMITED | [일괄 검증](test-plan/evidence/m7_carla_recovery/batch-closeout/README.md) |
| 독립 wall 감시 | 2ms/4ms 감시 → 로컬 보호 선택 → 다음 tick 차단. Terminal native owner는 입력 단절 뒤에도 보호 Actual 생성 | [wall guard](test-plan/evidence/m7_carla_wall_guard/README.md) · [terminal 응답](test-plan/evidence/m7_carla_wall_guard/terminal-response/README.md) |
| 증거 전달 최적화 | Raw solver journal 회수와 compact 전달을 분리하고 기존 physics/work/Actual 동등성 검증. 정상 wall timing 수용은 아님 | [전달 경로](test-plan/evidence/m7_carla_wall_guard/pipeline/README.md) |
| Wall owner component | 실제 monotonic timer·분리된 IO·유한 mailbox, 원래8-role service와 보호·완료 work 정산 검증. 합성 stationary 입력 범위 | [component 실행](test-plan/evidence/m7_carla_wall_guard/wall-owner/README.md) |
| 실제 CARLA wall 연결 | model/wall을 분리하고 비영상5ms profile에서 짧은 정상 주행·실제 보호 정지 확인. 반복 중 EV 입력 만료·서버 종료 실패가 남아 **안정화 OPEN** | [비영상 개선·반복 실패](test-plan/evidence/m7_carla_wall_guard/carla-runtime/nonvideo-wall5/README.md) · [이전10ms 실패](test-plan/evidence/m7_carla_wall_guard/carla-runtime/README.md) |

이전 기능 시험의 정상5실행은 각각900구간, 약4.77215m 이동·최대 전방 속도 약1.259m/s다.
영상2실행은 각각 RGB180/GT180이다. Reference 30km/h 추종이나 전체 ODD 검증은 아니다.
마지막 wall 연결의 Normal/ASan 각113/113·TSan 경계26/26과 정상901/보호401개 replay 일치는
component/회귀 근거이며 실제 wall 주행 성공을 뜻하지 않는다.

## 남은 문제와 제한

| 항목 | 현재 처리 |
| --- | --- |
| 엔진 프레임 공백 | 최소 state 경로의10ms 요청1000구간은 source/공식 패키지 모두 최대 약10.83ms. RGB+GT에서는30ms 초과가 source200/1000·패키지17/1000으로 재현됨. 영상 경로의 지연 기여를 확인했으며 세부 blocking 원인은 미확정. 패키지 종료−11 실패 별도 보존. [대조 시험](test-plan/evidence/m7_carla_wall_guard/carla-runtime/frame-diagnostic/README.md) |
| Clock·실시간 실행 | simulation elapsed와 CLOCK_MONOTONIC을 분리. 고정 offset·heartbeat·timeout 증가로 2ms/4ms·30ms 수용을 대신할 수 없음 |
| 비영상 wall 반복 안정성 | 5ms plant·수신/physics 분리·중복 JSON 제거로 실제 속도에 가까운 정상 주행 가능성을 확인. 반복 중 이전 EV/HV 입력 의존성이30ms를 넘는 사례가 남음. 실제 원본 시각 재생으로 거부 원인을 확인했으며 source/timeout을 바꾸지 않음 |
| Wall fault 후 실제 제동 | 정상 세션 이후 새 LocalProtection Actual의 실제 제동·자연 정지를 짧은 비영상 시험에서 확인.100ms physics 보류는 game thread 자체 정지가 아니며 장시간·전체 wall fault 수용은 OPEN |
| Source 서버 종료 | 비영상 반복 중 UE thread pool 종료에서SIGSEGV. actor 정리·물리 감사와 server 정상 종료를 분리하며 해당 전체 case는 FAIL |
| Renderer | 카메라 없이 rendering만 켠 기본 source 경로는 최대16.66ms, RGB+GT의10ms 요청에서는 최대65.08ms/5frame 반복 지연. 영상 capture/render/readback과 물리 진행의 결합을 우선 조사. 과거 Distance Field SIGSEGV·전체 content/장시간 안정성은 미해결 |
| 과거 M3/M4·SDK | timing/FIFO·native·SDK sanitizer 기능 미완료 OPEN은 각 당시 분모·실패와 함께 보존 |
| DDS | 정규 제어 gate CLOSED, adapter 미착수. 기존 종료·20ms·TSan FAIL 및 접근 제한 이력 유지 |
| 전체 시스템·Target | 32개 요구/29개 system TC, Jetson·실제 IO·Host–Target 검증은 NOT RUN. C++ 제어/AI도 후속 |

## M7 종료 조건

**m7-simulation-time-v1의 고정 Town03/V1 기능 범위는 CLOSED**다. 연속 정상·영상·원본 work/EV·
보호 Actual 자연 정지·센서/work 누락·Host 정지 차단·Actual-only/single writer·pause/reset/새 INIT를
실행·독립 검사했다. 고정 VehicleRequest 시험이며 M8 경로 추종·Reference30km/h·AI 수용은 아니다.

실제 wall 전체 수용은 **별도 OPEN**이다. 비영상5ms의 짧은 정상·보호 정지 근거를 확보했지만
정상 반복 실패·EV 입력 전달 여유·서버 종료 안정성·영상·장시간 검증이 남는다.
M6 wall 계약·수치·수용은 그대로이며 기존 wall 실패도 보존한다. source30ms·expiry는
기능 profile의 동일 simulation domain에서 유지하고 timestamp를 고쳐 쓰지 않는다.
상세 계약은 [시뮬레이션 시간 연속 실행](interfaces/carla-plant-adapter.md#시뮬레이션-시간-연속-실행)에 있다.

**다음 작업은 M8의 종방향 모델→C++ 공통 vector 동등성 및 속도 폐루프**다.
이후 경로/횡제어·Reference 속도 시험을 진행한다. wall 실시간 gate는 기능 개발과 별도로 추적한다.
