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
| M3 — Timing·실행 | IN PROGRESS | 비동기 Actual·교차 guard·Host RTOS 파일럿·실행 대기 관측; RT/Target 및 수용 검토 |
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
| 전체 unit | Normal·ASan/UBSan **각각 C++ 521개 PASS 이력 유지**, 이번 Python **54개 PASS** |
| Build·정적 분석 | Native RTOS·ARM64 Linux RTOS/ViPer/plant 빌드 PASS. 직전 native normal/sanitizer·C++ 정적 분석 이력 유지; hosted OS sanitizer/fiber 연동은 NOT RUN |
| RTOS 파일럿 | 분리한 native build로 4조건×3회 신규 **12/12 PASS**: 정상·명령 중단·CRC 오류·Control WaitEvent 정지 |
| 기존 Linux 실행 회귀 | Multirate 17조건+Steering 4조건을 normal/sanitizer에서 **42/42 PASS** |
| 실행 대기 진단 | 무부하 3회·감시 CPU 부하 3회 수집; control **6/6 PASS**. 원래 정상 timing 계약은 각각 **2/3·0/3 PASS** |
| Wire·전체 시스템 | 직전 vCAN 97개·DBC 12 frame/36 payload 이력 유지, 이번 재실행 없음. 32개 requirement/29개 system TC **NOT RUN** |

[RTOS 파일럿](learning/m3_rtos_pilot.md)은 기존 Steering ECU와 CAN을 유지하고 실제 OS Task/Event/Alarm/Resource를 연결한다.
별도 Linux plant process가 물리·센서 취득·Actual 수신을 맡는다. OIL 2.5 OSEK 기능 시험이며 R25-11 Classic stack 적합성,
ARXML/RTE/BSW 생성·ARM64 Jetson 배포는 NOT RUN이다. 기존 Linux 배포 계획과 2 ms/4 ms guard·RX 3 ms 기준은 유지한다.

Trampoline POSIX의 가상 tick은 relative sleep 기반이다. 첫 파일럿 12 runs의 첫 release 기준 wall drift는
약 **23.8–30.6 ms / 1.6 s**였다. 기능 PASS를 정시 실행이나 차량 전체 timing 충족으로 확대하지 않는다.
신규 native 12 runs에서도 약 **24.3–28.8 ms / 1.6 s**의 drift를 관측했다. Linux scheduling은 여전히 SCHED_OTHER다.
[ARM64 빌드·RT 사전 점검](adr/ADR-0041-arm64-rtos-build-and-host-preflight.md)을 추가했다.
ARM64는 세 ELF의 CPU·loader/library ABI를 기록한 교차 빌드 결과이며 Jetson 실행 결과가 아니다.
Host는 PREEMPT_DYNAMIC이며 FIFO priority 1은 EPERM, RT priority limit은 0, trace/perf 접근도 제한된다.
RT workload·지연 개선 비교는 NOT RUN이다. PREEMPT_RT와 실행 계정의 RT 권한은 별도로 준비·검증해야 한다.

별도 observer가 기존 native multirate thread의 `/proc` 누적 카운터를 읽었다. 6회에서 monitor skip **486개**가 있었고,
이를 덮는 모든 관측 구간에서 runqueue 대기 증가를 확인했다. 무부하의 한 구간에서는 요청 wake 지연 약 3.565 ms와
대기 누적 증가 약 3.510 ms가 기록됐다. 앞뒤 sample 여유 약 2.494 ms가 포함되므로 개별 wakeup의 정확한 분해는 아니다.
경쟁 process/IRQ/VM 원인은 아직 특정하지 않았다. Perf(paranoid=4)·tracefs 권한이 막힌 상태를 그대로 기록했다.
이 observer는 추가 부하를 주는 진단 도구이며 기존 배치 성능 표본과 합치지 않는다.

앞선 schema 5 배치 시리즈 124 runs의 119 PASS/5 FAIL은 [품질 이력](quality_policy.md)에 보존했다.
기존 IO 동반 map(ECU CPU B, RX/monitor/plant CPU A)은 다음 Host 시험의 기준이다.
이번 진단은 monitor를 CPU 2로 옮긴 실험 map이며 이전 5개 실패의 원인을 소급 확정하는 자료가 아니다.
M1/M2 학습자 수용·전체 M3 수용은 PENDING이다.

## 다음 작업

1. **ARM64 실행 검증:** 선택한 보드의 OS/BSP·sysroot/ABI와 POSIX stack·ViPer IPC·SocketCAN 지원을 확인하고 기능 4조건을 실행한다. 교차 빌드 PASS를 runtime 지원으로 확대하지 않는다.
2. **Host timing 검증:** 사전 점검이 가능한 도구를 준비했다. 다음은 RT 권한이 있는 환경과 native owner별 policy/priority 적용·실제값 검증 경로다. 같은 M3 workload/시한과 kernel trace로 일반/RT 실행을 비교한다.
3. **M3 수용·후속 통합:** 기능/clock/budget·누락 분모·보호 요청과 실제 적용·미검증 범위를 검토한다. RTE/BSW·Central/두 Zone 통합은 후속이다.

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
