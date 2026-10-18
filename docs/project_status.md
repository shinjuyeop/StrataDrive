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
| M3 — Timing·실행 | IN PROGRESS | 비동기 Actual·owner별 배치·전체 cycle/RX 대응; budget 채택·RT 우선순위/Target 및 수용 검토 |
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
| 주기 실행·감시 | Steering 및 Brake/Drive/Power 10 ms·BMS 20 ms, 실제 RX·독립 감시, owner별 CPU 배치·전체 body/CPU/sleep·RX 시간 대조 | [다중 주기](learning/m3_multirate_runtime.md), [CPU 부하](learning/m3_cpu_placement.md), [전체 cycle](learning/m3_owner_cycles.md) |

Receiver는 유효 0과 unknown, 원천 source/dependency age, 원래 요청에 묶인 expiry를 구분한다.
중계·재발행으로 오래된 측정이나 제한값을 fresh하게 만들지 않는다.
Isolated DriveActuator의 speed/capability는 unavailable이며, 필수 EV gate는 별도 DriveController가 담당한다.
Steering TrackingError와 Brake ResponseError는 정상 응답 계약 위반을 검출한다. 단일 센서로 기계 원인을 고유하게 진단하지 않는다.

## 검증 결과와 한계

| 검사 | 결과 / 범위 |
| --- | --- |
| 전체 unit | Normal·ASan/UBSan **각각 C++ 521개 PASS**; Python 리포터 **37개 PASS**; 이번 cycle/CPU/skip/RX·fault expiry 검사 12개 추가 |
| Local vCAN | 직전 전체 회귀 normal·sanitizer **각각 97개 PASS** = M1 89개 + model 8개; 이번 변경은 runtime/runner 배치 범위 |
| DBC·CRC | 기존 12개 frame/C++ payload 36개와 독립 CRC 교차 검증 PASS |
| Build·정적 분석 | 3 build·변경 C++ 2개 clang-tidy/cppcheck PASS; 이전 trace schema 2/3 재분석 PASS; TSan은 기존 Host 오류로 미실행 |
| Runtime 회귀 | 기존 9+owner 지연 4=13조건을 3 build 및 고정 IO map의 normal/sanitizer에서 **65 runs PASS** |
| Owner 부하 | Schema 4 비교 56 runs: control 56/56 PASS, 기존 정상 계약 33 PASS/23 FAIL. 기존 CPU 실험 6 runs는 control 6/6 PASS·계약 4 PASS/2 FAIL |
| 전체 시스템 검증 | 32개 requirement와 29개 system TC의 전체 Result는 **NOT RUN**; component 부분 증거와 구분 |

상세 case 수·실행 명령·증거 경로는 [품질 기록](quality_policy.md)과 [추적성](test-plan/traceability.md)에 있다.
Unit·manual-clock demo와 M3 wall-time trace는 구분한다. M3는 Host component의 elapsed wall time 측정이며 Target/전체 E2E 증거는 아니다.
Drive Actual은 기존 SourceTimeNs에 실제 torque 취득 시각을 보존하고 speed/capability는 각자 시각으로 검사한다.
Cached torque는 새 sample로 발행하지 않으며 독립 Actual receiver의 Accepted와 raw bytes를 확인한다. 차량 feedback bridge는 후속이다.
VCan은 실제 CAN의 전기적 동작을 검증하지 않는다.
10월 16일 다섯 stream 부하 실험에서 baseline/다른 CPU 부하는 통과했지만 같은 CPU 부하의 14 runs는 RX job 누락과 Drive 활성화 실패를 기록했다.
일반·production 각각 공유 CPU의 RX miss는 48개, sanitizer는 18개였다. 이 배치의 정상 timing 계약 충족은 주장하지 않는다.
10월 18일 새 workload의 1회 smoke에서는 일반 build 4 PASS / 2 FAIL, sanitizer 2 PASS / 4 FAIL이었다.
Sanitizer의 separate 조건에서도 RX miss가 있었고 반복 성능 비교나 Target 보장으로 확대하지 않는다. Deadline은 유지했다.
이전 trace schema 3의 [owner별 비교](adr/ADR-0037-runtime-owner-cpu-placement.md)는 normal·production 각 3회, sanitizer 1회 실행했다.
같은 CPU B 부하에서 RX·monitor·plant를 A로 함께 옮긴 조건은 normal 6/6, production 4/6, sanitizer 2/2 통과했다.
Production의 잔여 RX skip 3개는 그대로 FAIL이다. RX만 옮기면 출력 만료도 남아 전체 정상 계약을 보장하지 못했다.
후속 trace schema 4는 전체 cycle·CPU/sleep 기록과 RX 대응을 추가한 별도 workload다.
이번 IO 분리 조건은 normal 6/6·production 6/6·sanitizer 2/2 통과했으나 production 무부하 대조군에서도 RX·monitor·plant가 같은 기회를 1개씩 놓쳤다.
이 구간의 body는 짧고 두 owner의 요청 wake→시작은 약 2.49 ms 늦었다. Kernel/VM 원인을 식별한 것은 아니다.
Sanitizer RX 단독 분리의 기존 정상 계약은 2/2 PASS지만 monitor/plant 기회는 각각 244개 생략됐다.
현재 PASS에 새 owner deadline/skip 0 기준을 도입하지 않았다. 관측을 근거로 budget을 별도 검토한다.
RT priority 적용 probe는 EPERM·RLIMIT_RTPRIO=0으로 거부됐다. RT policy 실행 검증은 NOT RUN이며 현재 배치를 Target 보장으로 확대하지 않는다.
Wire 채택과 학습자의 직접 재현·이해 기록은 PENDING이다.

## 다음 작업

1. **Budget 채택·감시 독립성:** 기록한 body/CPU·요청 wake 지연·감시/취득 공백을 근거로 owner budget과 수용 조건을 검토한다. RT 실험은 적용 가능한 환경에서 기존 SCHED_OTHER와 비교한다. 관측만으로 기존 deadline을 완화하지 않는다.
2. **M3 수용 검토:** 취득/생성/송수신 시각·miss 분모·보호 응답과 미검증 범위를 대조한다.
3. **학습자 수용:** M2 [검토표](m2_acceptance_review.md)와 M3 trace를 직접 재현·설명한 기록을 남긴다. 실제 Central/Zone 통합은 M4다.

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
