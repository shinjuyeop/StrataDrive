# Project status

Updated: **2026-10-19**. **M3 — IN PROGRESS**를 유지하며 **M4 Central/Zone component 구현**을 진행한다.
[README](../README.md)는 프로젝트 소개와 실행 진입점이며, 이 문서는 현재 구현 범위·검증 결과·다음 작업을 정리한다.
단계별 일정은 [로드맵](roadmap.md), 날짜별 시험 이력·도구·로그 경로는 [품질 기록](quality_policy.md)에 둔다.

## Milestone 현황

| 단계 | 상태 | 남은 항목 |
| --- | --- | --- |
| M0 — 계약·아키텍처 | BASELINED | [종료 검토](m0_baseline.md)는 문서 계약의 검토 결과 |
| M1 — DBC·vCAN | TECHNICAL CHECKS PASS / REVIEW PENDING | Wire baseline 채택, 학습자 설명·직접 재현 |
| M2 — Actuator·EV 모델 | TECHNICAL CHECKS PASS / REVIEW PENDING | 학습자 직접 재현·수용 검토 |
| M3 — Timing·실행 | IN PROGRESS / HOST REVIEW COMPLETE | [실행 기준 선택](m3_acceptance_review.md); 일반 sanitizer 타이밍 실패 2건·학습자 수용 및 Target/E2E 후속 |
| M4 — Central/Zone | IN PROGRESS / COMPONENT IMPLEMENTATION | Central·scoped admission·CAN gateway/보호·Rear power/permission/limits·초기 구동 연결; Front startup·coordinated stop·Leaf lease·전체 ingress/status/runtime 후속 |
| M5–M13 | PLANNED | DDS → 차량/CARLA → control·diagnostics·AI·보드 비교 |

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
| Central 전원·허가 | 독립 입력 health/정상 준비, trusted lifecycle root·요청 ACK·expiry, actual OFF/READY와 FAIL_SAFE latch; 전원 요청·DrivePermission 산출 | [준비 조건](learning/m4_normal_drive_readiness.md), [상태 owner](learning/m4_vehicle_management.md) |
| Central 배분 | Acceleration/curvature/braking→angle·signed torque·pressure, 권한/BMS/capability gate·actual 잔여 회생 보정·저속 hold/release·deficit/excess와 보호 요청 | [첫 배분 component](learning/m4_control_allocation.md) |
| Zone 명령 수용 | Front atomic Steering/Brake·Rear Drive, 독립 trusted root 대조·scope/range/mode/age/expiry·연속성 latch·명시적 arm/INIT | [명령 수용 component](learning/m4_zone_command_admission.md) |
| Zone 전달·로컬 보호 | Bounded FIFO·최신 명령 선택·각 CAN write 전후 expiry guard·partial/failure latch; 별도 trusted port로 실제 Leaf의 Hold/Protect/Zero 선택 | [Gateway·보호 연결](learning/m4_zone_gateway.md) |
| Rear 전원·시동 연결 | 독립 lifecycle root·실제 송신 Enable ACK·limits/permission/status 감시, Drive NonDriving→trusted arm·정차/derating envelope, Drive/Power 로컬 보호 | [전원·초기 구동](learning/m4_rear_power_startup.md) |
| 에너지·회로 연결 | Actual torque/speed→motor DC·손실→Battery SOC, capacitor·경로 손실과 atomic commit; 정상/용착/센서 상실/지속 부하 | [이상적 HV 연결](learning/m2_drive_energy.md), [실제 회로 연결](learning/m2_ev_power_circuit.md) |
| 주기 실행·감시 | Steering 및 Brake/Drive/Power 10 ms·BMS 20 ms, 실제 RX·독립 감시, owner별 CPU 배치·전체 body/CPU/sleep·RX 시간 대조·4 ms 교차 guard와 수신 이중 감시 | [다중 주기](learning/m3_multirate_runtime.md), [CPU 부하](learning/m3_cpu_placement.md), [전체 cycle](learning/m3_owner_cycles.md) |

Receiver는 유효 0과 unknown, 원천 source/dependency age, 원래 요청에 묶인 expiry를 구분한다.
중계·재발행으로 오래된 측정이나 제한값을 fresh하게 만들지 않는다.
Isolated DriveActuator의 speed/capability는 unavailable이며, 필수 EV gate는 별도 DriveController가 담당한다.
Steering TrackingError와 Brake ResponseError는 정상 응답 계약 위반을 검출한다. 단일 센서로 기계 원인을 고유하게 진단하지 않는다.

## 검증 결과와 한계

| 검사 | 결과 / 범위 |
| --- | --- |
| 전체 unit | Normal·ASan/UBSan **각각 C++ 726개 PASS**; Python **63개 PASS 이력**, 이번 Python 변경·unit 재실행 없음 |
| M4 Central/Zone component | 기존 준비/상태/배분/admission/gateway와 새 startup7·readiness3·Rear19개 PASS. 실제 Rear 전원 준비→arm→배분 1.6 s 논리 시간 연결; Front/health/BMS limits/safety/speed는 fixture, 전체 coordinator/runtime·DDS/timing 후속 |
| M4 분리 vCAN | Normal·sanitizer 각각 4/4 PASS. 기존 Front/Rear 3개 + Rear power/limits/permission→실제 Leaf 수신·독립 발급 context 대조 1개. 실제 물리 반응은 별도 component 시험 |
| M3 수용 검토 | Host IO 동반/FIFO 기준 선택, 원본 96회 재분석·판정 동일. 전체 timing 수용은 PENDING |
| Build·정적 분석 | M4 native normal/sanitizer·BUILD_TESTING=OFF 빌드, 변경 C++ 11개 clang-tidy·production 7개 cppcheck 검사. 새 test helper 경고 수정; 확장 header 검사에서 기존 DriveSilPlant::begin 인자 경고 1종은 보존. 기존 RTOS host·ARM64 build 이력 유지; hosted OS sanitizer/fiber 연동 NOT RUN |
| Native 일반/FIFO 비교 | 같은 CPU map·workload·시한으로 4조건×2 trace×3회 **24/24 PASS**, 설정·부하 control 모두 PASS |
| Native 고장 회귀 | Normal OTHER/FIFO 각각 17/17, sanitizer OTHER 15/17·FIFO 17/17: **66/68 PASS**, 일반 sanitizer의 owner skip 두 실패 보존 |
| 이전 RTOS 파일럿 | 기존 12회 이력과 직전 4조건 **4/4 PASS**; 새 timer 비교와 별도 cohort |
| Hosted timer 비교 | 기능 **48/48 PASS**. 추가 Host timing은 absolute **24/24**, relative **0/24 PASS**; 대조군 실패 보존 |
| 후속 native FIFO 회귀 | 17조건×3회, normal/sanitizer 각각 **51/51 PASS**; 기존 OTHER 실패 2건 유지 |
| 후속 대기 진단 | Control **12/12 PASS**. Quiet 두 정책 각각 3/3, IO 부하 OTHER 0/3·FIFO 3/3 timing PASS; intrusive 진단 |
| Timer 정지·원본 호환 | ViPer 35.133 ms 정지의 누락 3개/정상 FAIL 확인; 나머지 3조건과 upstream 기능 4/4 확인, 48회 비교와 별도 |
| 이전 Linux 실행 회귀 | Multirate 17조건+Steering 4조건 normal/sanitizer **42/42 PASS 이력 유지** |
| 실행 대기 진단 | 무부하 3회·감시 CPU 부하 3회 수집; control **6/6 PASS**. 원래 정상 timing 계약은 각각 **2/3·0/3 PASS** |
| Wire·전체 시스템 | 기존 vCAN 97개 normal/sanitizer 각각 재통과 + gateway 4개씩 PASS. DBC 12 frame/36 payload 이력 유지. 32개 requirement/29개 system TC **NOT RUN** |

[RTOS 파일럿](learning/m3_rtos_pilot.md)은 기존 Steering ECU와 CAN을 유지하고 실제 OS Task/Event/Alarm/Resource를 연결한다.
별도 Linux plant process가 물리·센서 취득·Actual 수신을 맡는다. OIL 2.5 OSEK 기능 시험이며 R25-11 Classic stack 적합성,
ARXML/RTE/BSW 생성·ARM64 Jetson 배포는 NOT RUN이다. 기존 Linux 배포 계획과 2 ms/4 ms guard·RX 3 ms 기준은 유지한다.

최초 Trampoline POSIX의 가상 tick은 relative sleep 기반이었다. 첫 파일럿 12 runs의 첫 release 기준 wall drift는
약 **23.8–30.6 ms / 1.6 s**였다. 기능 PASS를 정시 실행이나 차량 전체 timing 충족으로 확대하지 않는다.
다음 hosted OS 12 runs에서도 약 **24.3–28.8 ms / 1.6 s**의 drift를 관측했다. 이 당시 Linux scheduling은 SCHED_OTHER였다.
[ARM64 빌드·RT 사전 점검](adr/ADR-0041-arm64-rtos-build-and-host-preflight.md)을 추가했다.
ARM64는 세 ELF의 CPU·loader/library ABI를 기록한 교차 빌드 결과이며 Jetson 실행 결과가 아니다.
Host는 PREEMPT_DYNAMIC이다. 관리자 설정 후 새 PAM 실행 세션의 RT priority limit **20/20**과
FIFO priority **1·20 AVAILABLE / 21 EPERM**을 확인했다. 기존 IDE 세션의 limit 0은 유지되지만 같은 사용자로
새 실행 세션을 만들면 시험할 수 있다. [실행 방법](learning/m3_rtos_pilot.md#권한-설정-후-기존-ide-세션에서-실행하기)을 참고한다.
Trace/perf 접근 제한은 남아 있다. [Native FIFO 실행](learning/m3_native_fifo.md)에서 owner별 실제 priority와
startup gate·실패 취소·호출 thread 복원을 연결했다. 추가 부하의 Drive release→완료 p99는 full trace에서
일반 **1.947 ms → FIFO 0.065 ms**, minimal에서 **2.450 ms → 0.073 ms**였다. 모든 작업의 지연 개선이나 WCET 보장은 아니다.
Sanitizer 일반 실행 2회는 예상하지 않은 owner skip을 동반해 실패했다. 같은 cohort에서 FIFO 고장 회귀는 모두 PASS다.
직전 실행은 총 **94/96 PASS**이며 실패를 제거하거나 기존 시한을 완화하지 않았다. PREEMPT_RT kernel·Target timing은 후속이다.

별도 observer가 기존 native multirate thread의 `/proc` 누적 카운터를 읽었다. 6회에서 monitor skip **486개**가 있었고,
이를 덮는 모든 관측 구간에서 runqueue 대기 증가를 확인했다. 무부하의 한 구간에서는 요청 wake 지연 약 3.565 ms와
대기 누적 증가 약 3.510 ms가 기록됐다. 앞뒤 sample 여유 약 2.494 ms가 포함되므로 개별 wakeup의 정확한 분해는 아니다.
경쟁 process/IRQ/VM 원인은 아직 특정하지 않았다. Perf(paranoid=4)·tracefs 권한이 막힌 상태를 그대로 기록했다.
이 observer는 추가 부하를 주는 진단 도구이며 기존 배치 성능 표본과 합치지 않는다.

앞선 schema 5 배치 시리즈 124 runs의 119 PASS/5 FAIL은 [품질 이력](quality_policy.md)에 보존했다.
IO 동반 map(ECU CPU B, RX/monitor/plant CPU A)과 owner별 FIFO를 다음 Host 통합의 기준으로 선택했다.
별도 observer 진단은 monitor를 CPU 2로 옮긴 실험 map이며 이전 5개 실패의 원인을 소급 확정하는 자료가 아니다.
M1/M2 학습자 수용·전체 M3 수용은 PENDING이다.

[M3 수용 검토](m3_acceptance_review.md)에서 계약·분모·실패·물리 적용을 대조했다.
Pooled guarded 주기 통계에 run 사이 대기 시간이 섞인 오류를 수정했고 Python 60개가 통과했다.
원본 96회를 재분석해 해당 16개 분포만 교정했고 개별 run 판정·Drive/RX 지연·miss/skip은 동일했다.
원본 로그를 보존했으며 새 workload 실행은 0회다. 기본 실행 정책은 기존 상속 방식이며 FIFO는 CLI로 명시한다.

후속 [ADR-0043](adr/ADR-0043-hosted-monotonic-timer-and-placement.md)에서 opt-in RTOS build의 timer 기본을
절대 monotonic timerfd로 바꿨다. 선택한 Host RTOS/FIFO profile의 normal drift는 3회 모두 절댓값 0.001 ms 미만,
원래 timer phase→Control 완료 max는 0.277 ms였다. 상대 타이머 대조군은 FIFO에서도 15–17 ms drift가 남았다.
OS Task/CAN·native 시한은 유지하고, 새 추가 Host timing 5 ms 판정과 source/실제 CPU·policy를 대조했다.
개발 probe의 12-tick 정지가 120 ms보다 짧아지는 문제는 13 ticks로 수정했고 최소 wall 120 ms 검사는 유지했다.
원래 native sanitizer 두 실패의 정확한 커널 원인과 전체 M3 수용은 계속 PENDING이다.

## 다음 작업

1. **M4 Front startup·정상 종료와 전체 경로:** Rear 시동 연결을 바탕으로 Front의 non-driving 대기/arm과 coordinated stop→전원 종료를 설계·시험한다. 기존 active Drive Inhibit의 fail-safe 정책과 정상 종료를 명시적으로 구분해야 한다. 기존 32-byte CAN의 remote Leaf composite lease/보호 계약도 결정한다. 실제 독립 ingress/status/feedback 감시·rejoin과 전체 coordinator를 통합한다. 기존 EV demo/runtime의 request/grant는 아직 fixture이며 교체한 전체 workload timing은 별도 검증한다. DDS는 M5다.
2. **M3 타이밍 예외 해소:** OPEN-M3-01/02의 원본 실패를 유지하고 kernel trace 접근을 준비해 timer→wakeup→switch를 분석한다. 추가 반복과 PREEMPT_RT 비교는 후속 실험이며 M4 준비가 M3 전체 수용을 뜻하지 않는다. 학습자 직접 재현·설명도 남아 있다.
3. **ARM64 배포 준비:** 보드 OS/BSP·ABI/stack/IPC·SocketCAN과 실제 실행을 확인한 뒤 다른 Leaf OS 확장을 검토한다. Target 검증은 배포 단계, RTE/BSW는 별도 pilot과 연결한다.

## 후속 통합 범위

Central의 단일 vehicle management/allocation/session/feedback bridge와 Front/Rear 독립 연결은
[채택한 아키텍처](adr/ADR-0021-central-coordination-and-parallel-zones.md)다.
Front는 Steering/Brake, Rear는 Drive/BMS를 담당하며 feedback도 담당 Zone→Central→Host를 거친다.
준비 조건·전원/허가·첫 배분 library를 구현하고 PowerController·RC/접점·torque/pressure 응답 모델과 component 시험했다.
Rear 전원/허가/limits와 explicit NonDriving→arm도 실제 controller·RC/torque component에 연결했다. 전체 coordinator·두 Zone runtime·DDS 통신은 M4/M5 후속이며 기존 demo/runtime의 request/grant·relay는 fixture다.

기존 통합 EV 예제와 배분 응답 시험의 speed는 외부 고정값 20 rad/s, 새 Rear 시동 연결은 0 rad/s다. 차량 관성·타이어·차량 제동/배분 통합·CARLA closed-loop는 M4/M6/M7,
Owner별 배치와 native FIFO 우선순위는 Host에서 비교했다. Target timing과 DTC 통합(M9), Classical control·AI·Target 배포는 후속 단계다.
Leaf는 [Classic 개발 체계](adr/ADR-0022-leaf-classic-development-methodology.md)를 따르는 방향을 채택했고,
실제 OS/RTE/BSW stack·toolchain은 pilot에서 검토한다.

설계 범위의 기준은 [RG-01 회생·마찰 배분](icd/regenerative_braking_design.md),
[EV-01 Battery/BMS·전원](icd/ev_power_bms_design.md), [개발·학습 계획](engineering_plan.md)이다.
