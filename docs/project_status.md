# Project status

Updated: **2026-10-16**. 현재 단계는 **M3 — IN PROGRESS**다.
[README](../README.md)는 프로젝트 소개와 실행 진입점이며, 이 문서는 현재 구현 범위·검증 결과·다음 작업을 정리한다.
단계별 일정은 [로드맵](roadmap.md), 날짜별 시험 이력·도구·로그 경로는 [품질 기록](quality_policy.md)에 둔다.

## Milestone 현황

| 단계 | 상태 | 남은 항목 |
| --- | --- | --- |
| M0 — 계약·아키텍처 | BASELINED | [종료 검토](m0_baseline.md)는 문서 계약의 검토 결과 |
| M1 — DBC·vCAN | TECHNICAL CHECKS PASS / REVIEW PENDING | Wire baseline 채택, 학습자 설명·직접 재현 |
| M2 — Actuator·EV 모델 | TECHNICAL CHECKS PASS / REVIEW PENDING | 학습자 직접 재현·수용 검토 |
| M3 — Timing·실행 | IN PROGRESS | 다중 주기·독립 task/CAN 감시 검사 완료; 고정 부하·CPU 배치·Target 검증 |
| M4–M13 | PLANNED | Central/Zone → DDS → 차량/CARLA → control·diagnostics·AI·보드 비교 |

## 구현·시험한 범위

현재 구현은 **Host functional SIL component**다. [실행 경계 정리](learning/m2_execution_boundaries.md)로 ECU 판단과 물리 실행 연결을 분리했다. 모델의 설정값은 첫 시험 fixture이며 실차 calibration은 아니다.

| 영역 | 구현한 내용 | 상세 안내 |
| --- | --- | --- |
| CAN FD 통신 | Actuator Command/Actual 6개 + EV/BMS 6개 frame, DBC·codec·AUTOSAR R25-11 E2E Profile 5·receiver·SocketCAN | [Actuator frame](learning/m1_steering_frame_codec.md), [EV/BMS](learning/m1_bms_codec.md) |
| 세션·수신 연속성 | 영속 Epoch 발급, bounded queue, overflow/restart, 이전 Epoch 거부와 P05 state 오염 방지 | [Session/queue](learning/m1_session_queue.md) |
| Steering | Delay/rate/angle 제한, source-loss hold, 별도 angle sensor와 정상 응답 범위·residual/dwell 고장 검출 | [응답 모델](learning/m2_steering_model.md), [고장 검출](learning/m2_steering_fault_monitor.md) |
| Brake | 압력 가압/감압·지연·포화, 별도 pressure sensor와 stuck/slow 응답 검출, 보호 floor 요청·관측 구분 | [압력 모델](learning/m2_brake_model.md), [고장 검출](learning/m2_brake_fault_monitor.md) |
| Drive | Signed torque 응답, 양·음수 명령 상실 시 zero ramp, BMS 한계·trusted permission·local HV/speed gate와 capability | [응답 모델](learning/m2_drive_model.md), [필수 gate](learning/m2_drive_gate.md) |
| Battery·BMS | 실제 DC 기반 단일 energy/SOC owner, 전압·전류·온도·셀 극값 관측, 방향별 derating·보호 dwell/latch | [Battery](learning/m2_battery_model.md), [BMS](learning/m2_bms_controller.md) |
| Power lifecycle | 실제 접점·RC bus 기반 precharge/READY, 전류 확인·접점 open·잔류 전압 방전, shutdown blocked | [전원 상태 흐름](learning/m2_power_lifecycle.md) |
| 에너지·회로 연결 | Actual torque/speed→motor DC·손실→Battery SOC, capacitor·경로 손실과 atomic commit; 정상/용착/센서 상실/지속 부하 | [이상적 HV 연결](learning/m2_drive_energy.md), [실제 회로 연결](learning/m2_ev_power_circuit.md) |
| 주기 실행·감시 | Steering 및 Brake/Drive/Power 10 ms·BMS 20 ms, 실제 SocketCAN RX·독립 task/유효 RX 감시, snapshot·CSV와 정지/CRC 손상 검사 | [조향 실행](learning/m3_steering_timing.md), [다중 주기](learning/m3_multirate_runtime.md) |

Receiver는 유효 0과 unknown, 원천 source/dependency age, 원래 요청에 묶인 expiry를 구분한다.
중계·재발행으로 오래된 측정이나 제한값을 fresh하게 만들지 않는다.
Isolated DriveActuator의 speed/capability는 unavailable이며, 필수 EV gate는 별도 DriveController가 담당한다.
Steering TrackingError와 Brake ResponseError는 정상 응답 계약 위반을 검출한다. 단일 센서로 기계 원인을 고유하게 진단하지 않는다.

## 검증 결과와 한계

| 검사 | 결과 / 범위 |
| --- | --- |
| 전체 unit | Normal·ASan/UBSan **각각 C++ 516개 PASS**; Python 리포터 **8개 PASS**; 이번 valid RX/trusted context 11개·리포터 3개 추가 |
| Local vCAN | **97개 case PASS 이력** = M1 89개 + model 8개; 최신 구조 정리 단계의 재실행은 normal·sanitizer 각각 model 8개 |
| DBC·CRC | 기존 12개 frame/C++ payload 36개와 독립 CRC 교차 검증 PASS |
| Build·정적 분석 | M3 production build, 변경 C++ clang-tidy·cppcheck PASS; TSan은 Host memory mapping 오류로 미실행 |
| Demo·Timing | M2 구조 정리의 90개 CLI 비교 이력; 이번 multirate는 normal·sanitizer 각각 16 / production 8 runs, Steering 회귀 각각 4 runs PASS |
| 전체 시스템 검증 | 32개 requirement와 29개 system TC의 전체 Result는 **NOT RUN**; component 부분 증거와 구분 |

상세 case 수·실행 명령·증거 경로는 [품질 기록](quality_policy.md)과 [추적성](test-plan/traceability.md)에 있다.
Unit·manual-clock demo와 M3 wall-time trace는 구분한다. M3는 Host component의 elapsed wall time 측정이며 Target/전체 E2E 증거는 아니다.
비동기 Drive sensor의 원천 시각을 보존하므로 현 wire의 torque scalar는 unavailable이다. 실제 torque는 physical trace에서 확인하며 Actual CAN 송신→독립 feedback RX는 후속이다.
VCan은 실제 CAN의 전기적 동작을 검증하지 않는다.
Wire 채택과 학습자의 직접 재현·이해 기록은 PENDING이다.

## 다음 작업

1. **M3 부하·배치:** 고정 부하 조건에서 task별 budget·handoff·miss와 계측 비용을 비교하고 CPU affinity/우선순위 실험 조건을 정한다.
2. **Drive 관측 계약:** sampling 동기화 또는 torque timestamp 계약을 검토해 비동기 Actual 보고 경로를 완성한다.
3. **수용 검토:** M2 [검토표](m2_acceptance_review.md)와 M3 trace를 직접 재현·설명하고 Host 부분 결과·Target 미검증 범위를 구분한다.

## 후속 통합 범위

Central의 단일 vehicle management/allocation/session/feedback bridge와 Front/Rear 독립 연결은
[채택한 아키텍처](adr/ADR-0021-central-coordination-and-parallel-zones.md)다.
Front는 Steering/Brake, Rear는 Drive/BMS를 담당하며 feedback도 담당 Zone→Central→Host를 거친다.
두 Zone runtime·DDS 통신과 실제 Central coordinator는 M4/M5 범위이며 현재 request/grant·relay는 fixture다.

통합 EV 예제의 speed는 외부 고정값 20 rad/s다. 차량 관성·타이어·마찰제동 배분·CARLA closed-loop는 M4/M6/M7,
고정 부하·CPU 배치와 Target timing은 M3 이후 배포 단계, DTC 통합은 M9에 남는다. Classical control·AI·Target 배포도 후속 단계다.
Leaf는 [Classic 개발 체계](adr/ADR-0022-leaf-classic-development-methodology.md)를 따르는 방향을 채택했고,
실제 OS/RTE/BSW stack·toolchain은 pilot에서 검토한다.

설계 범위의 기준은 [RG-01 회생·마찰 배분](icd/regenerative_braking_design.md),
[EV-01 Battery/BMS·전원](icd/ev_power_bms_design.md), [개발·학습 계획](engineering_plan.md)이다.
