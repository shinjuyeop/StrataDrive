# Project status

Updated: **2026-10-18**. 현재 단계는 **M3 — IN PROGRESS**다.
[README](../README.md)는 프로젝트 소개와 실행 진입점이며, 이 문서는 현재 구현 범위·검증 결과·다음 작업을 정리한다.
단계별 일정은 [로드맵](roadmap.md), 날짜별 시험 이력·도구·로그 경로는 [품질 기록](quality_policy.md)에 둔다.

## Milestone 현황

| 단계 | 상태 | 남은 항목 |
| --- | --- | --- |
| M0 — 계약·아키텍처 | BASELINED | [종료 검토](m0_baseline.md)는 문서 계약의 검토 결과 |
| M1 — DBC·vCAN | TECHNICAL CHECKS PASS / REVIEW PENDING | Wire baseline 채택, 학습자 설명·직접 재현 |
| M2 — Actuator·EV 모델 | TECHNICAL CHECKS PASS / REVIEW PENDING | 학습자 직접 재현·수용 검토 |
| M3 — Timing·실행 | IN PROGRESS | 비동기 Actual·4 ms Host 완료 guard·수신 이중 감시·배치 비교; RT/Target 및 수용 검토 |
| M4–M13 | PLANNED | Central/Zone → DDS → 차량/CARLA → control·diagnostics·AI·보드 비교 |

## 구현·시험한 범위

현재 구현은 **Host functional SIL component**다. [실행 경계 정리](learning/m2_execution_boundaries.md)로 ECU 판단과 물리 실행 연결을 분리했다. 모델의 설정값은 첫 시험 fixture이며 실차 calibration은 아니다.

| 영역 | 구현한 내용 | 상세 안내 |
| --- | --- | --- |
| CAN FD 통신 | Actuator Command/Actual 6개 + EV/BMS 6개 frame, DBC·codec·AUTOSAR R25-11 E2E Profile 5·receiver·SocketCAN | [Actuator frame](learning/m1_steering_frame_codec.md), [EV/BMS](learning/m1_bms_codec.md) |
| 세션·수신 연속성 | 영속 Epoch 발급, bounded queue, overflow/restart, 이전 Epoch 거부와 P05 state 오염 방지 | [Session/queue](learning/m1_session_queue.md) |
| Steering | Delay/rate/angle 제한, source-loss hold, 별도 angle sensor와 정상 응답 범위·residual/dwell 고장 검출 | [응답 모델](learning/m2_steering_model.md), [고장 검출](learning/m2_steering_fault_monitor.md) |
| Brake | 압력 가압/감압·지연·포화, 별도 pressure sensor와 stuck/slow 응답 검출, 보호 floor 요청·관측 구분 | [압력 모델](learning/m2_brake_model.md), [고장 검출](learning/m2_brake_fault_monitor.md) |
| Drive | Signed torque/zero ramp, BMS·trusted permission·local HV/speed gate와 capability; 비동기 취득 시각 보존·Actual socket TX→독립 RX | [응답 모델](learning/m2_drive_model.md), [필수 gate](learning/m2_drive_gate.md), [Actual CAN](learning/m3_drive_feedback.md) |
| Battery·BMS | 실제 DC 기반 단일 energy/SOC owner, 전압·전류·온도·셀 극값 관측, 방향별 derating·보호 dwell/latch | [Battery](learning/m2_battery_model.md), [BMS](learning/m2_bms_controller.md) |
| Power lifecycle | 실제 접점·RC bus 기반 precharge/READY, 전류 확인·접점 open·잔류 전압 방전, shutdown blocked | [전원 상태 흐름](learning/m2_power_lifecycle.md) |
| 에너지·회로 연결 | Actual torque/speed→motor DC·손실→Battery SOC, capacitor·경로 손실과 atomic commit; 정상/용착/센서 상실/지속 부하 | [이상적 HV 연결](learning/m2_drive_energy.md), [실제 회로 연결](learning/m2_ev_power_circuit.md) |
| 주기 실행·감시 | Steering 및 Brake/Drive/Power 10 ms·BMS 20 ms, 실제 RX·독립 감시, owner별 CPU 배치·전체 body/CPU/sleep·RX 시간 대조·4 ms 교차 guard와 수신 이중 감시 | [다중 주기](learning/m3_multirate_runtime.md), [CPU 부하](learning/m3_cpu_placement.md), [전체 cycle](learning/m3_owner_cycles.md) |

Receiver는 유효 0과 unknown, 원천 source/dependency age, 원래 요청에 묶인 expiry를 구분한다.
중계·재발행으로 오래된 측정이나 제한값을 fresh하게 만들지 않는다.
Isolated DriveActuator의 speed/capability는 unavailable이며, 필수 EV gate는 별도 DriveController가 담당한다.
Steering TrackingError와 Brake ResponseError는 정상 응답 계약 위반을 검출한다. 단일 센서로 기계 원인을 고유하게 진단하지 않는다.

## 검증 결과와 한계

| 검사 | 결과 / 범위 |
| --- | --- |
| 전체 unit | Normal·ASan/UBSan **각각 C++ 521개 PASS**; Python **43개 PASS**. 기존 파일에 guard/peer/tail·수신 이중 감시·배치 6개 추가 |
| Local vCAN·DBC | 직전 전체 회귀 각각 97개·12개 frame/36개 C++ payload PASS 이력; 이번 wire 변경 없음, 이 범위는 재실행하지 않음 |
| Build·정적 분석 | 3 build PASS; 변경 C++ 2개 clang-tidy/cppcheck PASS; 이전 trace schema 2/3/4의 7개 기록 재분석 PASS |
| Runtime 고장 회귀 | 기존 IO map의 17조건×3 build **51/51 PASS**, 상속 배치 normal build **17/17 PASS** |
| 새 배치 비교 | Schema 5 **56 runs: 51 PASS / 5 FAIL**. 배치·부하 control은 56/56 PASS. IO 동반 배치 14/14, monitor 별도 코어 13/14 PASS |
| 전체 시스템 검증 | 32개 requirement/29개 system TC **NOT RUN**; 학습자 M1/M2 수용 기록 PENDING |

완료 guard는 monitor와 plant가 상대의 release별 완료를 검사한다. 2 ms 주기·4 ms 시한의 1211개 대상 slot에서
누락도 miss로 남기며 floor/zero는 latch된다. 유효 수신도 각자 별도 상태로 감시해 monitor 120 ms 정지 중
plant가 수신 상실을 검출한다. Actual의 원래 취득 시각·각 보조 source age·실제 socket bytes/Accepted 검사는 유지한다.

최종 series **124 runs: 119 PASS / 5 FAIL**와 107개 배치 control을 기록했다. 다섯 실패는 RX 누락 3 runs와
monitor 누락 2 runs다. 누락 job 수는 RX 4개·monitor guard 3개이며 plant guard 누락은 없었다.
새 guard가 보호하더라도 정상 timing은 FAIL이다. 직전 schema 4에서 owner skip이 있어도 PASS였던 기록과 합치지 않는다.
이 Host에서는 기존 IO 동반 map(ECU CPU B, RX/monitor/plant CPU A)을 다음 시험의 기준으로 유지한다.
별도 CPU가 항상 더 낫다는 증거는 없고 무부하 조건에도 누락이 있었다. 특정 kernel/VM 원인은 식별하지 않았다.

상세 표·재현 명령·로그는 [품질 기록](quality_policy.md), 동작 설명은 [완료 guard 학습 안내](learning/m3_owner_cycles.md)와
[ADR-0039](adr/ADR-0039-owner-completion-guards.md)에 있다. 단위/기능 SIL과 실제 wall-time 측정을 구분한다.
VCan은 실제 CAN 전기적 동작을 검증하지 않으며 Host 표본은 Target·전체 E2E·WCET 보장이 아니다.
Plant/process/OS가 멈춘 동안 모델은 진행하지 못한다. 복귀 시 늦은 완료는 검출하지만 공백 중 실제 동작을 보장하지 않는다.
RT priority probe는 앞서 EPERM·RLIMIT_RTPRIO=0으로 거부됐다. 이번 RT/TSan 실행은 NOT RUN이다.

## 다음 작업

1. **RT/배포 환경 검증:** 현재 IO map·동일 workload/시한에서 실행 가능한 RT 환경의 우선순위·간섭 조건을 비교한다. Process/OS 공통 정지의 외부 감시도 배포 경계에서 정한다.
2. **M3 수용 검토:** 취득/생성/TX/RX 시각, task/owner miss 분모, 보호 요청과 실제 적용의 차이, 실패·미검증 범위를 검토한다. 현재 4 ms는 Host fixture 설정이다.
3. **학습자 수용:** M2 [검토표](m2_acceptance_review.md)와 M3 trace를 직접 재현·설명한 기록을 남긴다. Central/Zone 통합은 M4다.

## 후속 통합 범위

Central의 단일 vehicle management/allocation/session/feedback bridge와 Front/Rear 독립 연결은
[채택한 아키텍처](adr/ADR-0021-central-coordination-and-parallel-zones.md)다.
Front는 Steering/Brake, Rear는 Drive/BMS를 담당하며 feedback도 담당 Zone→Central→Host를 거친다.
두 Zone runtime·DDS 통신과 실제 Central coordinator는 M4/M5 범위이며 현재 request/grant·relay는 fixture다.

통합 EV 예제의 speed는 외부 고정값 20 rad/s다. 차량 관성·타이어·마찰제동 배분·CARLA closed-loop는 M4/M6/M7,
Owner별 배치는 Host에서 비교했고 RT 우선순위와 Target timing은 후속 배포 단계, DTC 통합은 M9에 남는다. Classical control·AI·Target 배포도 후속 단계다.
Leaf는 [Classic 개발 체계](adr/ADR-0022-leaf-classic-development-methodology.md)를 따르는 방향을 채택했고,
실제 OS/RTE/BSW stack·toolchain은 pilot에서 검토한다.

설계 범위의 기준은 [RG-01 회생·마찰 배분](icd/regenerative_braking_design.md),
[EV-01 Battery/BMS·전원](icd/ev_power_bms_design.md), [개발·학습 계획](engineering_plan.md)이다.
