# Requirement → component → interface → scenario/test → future result

Status: **DEFINED / Reference Baseline v0.1 + RG-01 + EV-01 + ZON-01 v0.5**.
SYS-ARCH-003·SYS-CTRL-008·SYS-SAFE-005·SYS-EV-003은 v0.5다. SYS-SAFE-004·SYS-CTRL-009는 v0.2,
SYS-COM-003/004·SYS-PERF-002와 나머지 SYS-EV 요구는 v0.3, 그 외 기존 요구는 v0.1이다.
[ADR-0021](../adr/ADR-0021-central-coordination-and-parallel-zones.md)의 Central owner/독립 Zone 경로를 반영한다.

아래 system TC 전체 구현/검증은 PLANNED, runtime Result는 전부 **NOT RUN**이다.
[Brake 수신부](../learning/m1_brake_codec.md#application-수신부-추가)의 Host/vCAN 부분 증거도
전체 system TC의 PASS로 확대하지 않는다.
[Drive wire/receiver/vCAN](../learning/m1_drive_codec.md)의 capability/actual 유효성 부분 증거도
TC-COM-002/003/005, TC-REG-004에 연결하지만 전체 Result는 NOT RUN을 유지한다.
M0 문서 review는 [exit checklist](../m0_baseline.md)에 별도 기록하며 아래 TC를 PASS로 바꾸지 않는다.
[BMS codec/항목별 receiver](../learning/m1_bms_codec.md)의 DBC/C++·manual-clock 부분 증거는
TC-EV-001/002/004와 TC-COM-002/005에 연결한다. Parent/expiry/partial limit timeout은 Host 로직
범위다. EV 독립 TX/RX/relay vCAN 36개 case도 부분 증거에 연결한다.
모델 물리 출력, Front/Rear runtime과 전체 system Result는 NOT RUN이다.
[Session/queue 14개 unit·overflow/restart 26개 vCAN](../learning/m1_session_queue.md)은
TC-COM-002/003/005, TC-SAFE-002, TC-EV-002/004의 local 부분 증거다.
물리 보호·vehicle INIT·Central–Zone session까지 검증한 전체 TC Result로 확대하지 않는다.
Result ID는 실제 실행 후에만 `RES-<test-suffix>-<run-id>`로 부여한다.
[M2 첫 Steering 모델](../learning/m2_steering_model.md)의 정상 delay/rate/saturation 및
source-loss/continuity/deadline hold는 TC-COM-002/003/005, TC-SAFE-002의 local 부분 증거다.
Vehicle protection/plant/Target timing을 포함하는 전체 Result는 NOT RUN을 유지한다.
[Brake 압력 모델](../learning/m2_brake_model.md)의 unit 16개와 독립 process vCAN 3개는
TC-COM-002/003/005와 TC-SAFE-002의 local response 부분 증거다.
정상 release와 pressure-floor ramp가 차량 정지/ABS/회생 배분을 검증한 것은 아니다.
[M2 수용 검토](../m2_acceptance_review.md)는 Drive actual/gate, Battery/BMS/Power와 energy/circuit의
component 증거도 연결한다. 현재 unit 391개(normal·ASan/UBSan)와 model vCAN 8개 재검사로
위 COM/SAFE와 SYS-CTRL-009·SYS-EV-001–005·SYS-PERF-002/003의 local 부분 범위를 확인했다.
후속 [Steering response monitor](../learning/m2_steering_fault_monitor.md)의 물리/sensor·residual/dwell·local latch 시험은
TC-CTRL-001·TC-SAFE-001/002의 부분 증거를 더한다.
[Brake response monitor](../learning/m2_brake_fault_monitor.md)의 가압/감압 stuck·slow, fresh sensor/unknown·latch/새 epoch와
보호 요청/관측 시험도 같은 TC의 local 부분 증거다. 후속 [ECU/SIL 실행 경계](../learning/m2_execution_boundaries.md)는 core-only 18개와 외부 물리 진행 3개를 추가했다.
M2 구조 정리 시점 unit은 491개이며 학습자 수용은 PENDING이다.
[M3 첫 Steering 실행](../learning/m3_steering_timing.md)은 schedule/monitor/snapshot unit 14개를 더해 C++ 전체 505개,
Python 리포터 5개와 Host wall-time normal/overrun/stall 검사를 수행했다.
SYS-PERF-001/002/003·TC-PERF-001/002의 local 부분 근거다.
후속 [다중 주기·CAN 감시](../learning/m3_multirate_runtime.md)는 C++ 11개·Python 3개를 추가해 전체 **516/8개**를 검사했다.
Brake/Drive/Power 10 ms·BMS 20 ms와 RX worker, 독립 task/유효 RX 감시의 40 runs·Steering 회귀 8 runs는
위 PERF와 SYS-COM-002/003·TC-COM-002/003의 local 부분 증거다. 5개 실제 vCAN 입력의 정지/CRC 실패를 검사했으며
이 단계의 비동기 torque는 unavailable이었다. 전체 multirate·차량/Target/E2E는 후속이다.
후속 [고정 부하·CPU 배치](../learning/m3_cpu_placement.md)는 Python 리포터 8개를 더해 당시 C++ **516개**·Python **16개**였다.
SYS-PERF-001/002/003·TC-PERF-001/002의 Host 부분 실험이며 부하에서 관측한 deadline 위반도 FAIL과 분모에 남긴다.
Control 적용 검증과 기존 ECU 계약 충족을 구분한다. 조건별 실제 결과는 [품질 기록](../quality_policy.md)에 연결한다.
[Drive Actual CAN 연결](../learning/m3_drive_feedback.md)은 비동기 취득/보조 시각·같은 torque 재발행 거부와 payload 대응을 검사해
당시 C++ **521개**·Python **21개**다. SYS-COM-002/003/004·SYS-PERF-001/002/003과 TC-COM-002/003/005·TC-PERF-001/002의
Host 부분 증거이며 Actual replay와 CRC 손상/worker 정지를 포함한다. 실제 Zone/Host bridge와 전체 TC Result는 NOT RUN이다.
후속 [owner별 배치](../adr/ADR-0037-runtime-owner-cpu-placement.md)는 map/순서/실제 thread 대조에 Python 4개를 더해
당시 C++ **521개**·Python **25개**다. 위 PERF의 Host 부분 증거이며 배치·부하 control과 ECU 계약의 실패를 구분한다.
단독 RX/동반 IO 분리의 정상 비교와 고정 map의 기존 fault 회귀 결과는 [품질 기록](../quality_policy.md)에 남긴다.
후속 [전체 owner cycle](../learning/m3_owner_cycles.md)은 당시 Python 12개를 더해 C++ **521개**·Python **37개**였다.
다음 [교차 완료 guard](../adr/ADR-0039-owner-completion-guards.md)는 기존 리포터 파일에 guard 분모·tail·peer·수신 이중 감시·배치 6개를 추가해
현재 Python **43개**다. 4 ms Host 완료 계약과 정상 누락 0, monitor/plant 지연 보호를 별도 component 증거로 검사한다.
Schema 5 최종 고장 회귀 68/68 PASS와 배치 56 runs의 51 PASS/5 FAIL을 보존했다. 124 runs의 분모·peer 관측·원래 source와
보호 latch를 교차 검증했으며 system TC의 전체 PASS로 확대하지 않는다. 배치 실패·상세 로그는 [품질 기록](../quality_policy.md)에 있다.
위 PERF의 Host 부분 계측이며 whole-body/CPU·생략된 기회·RX 대응·fault expiry accounting을 검사한다.
새 owner deadline 채택이나 전체 system TC 수용을 뜻하지 않는다.
아래 system TC의 모든 required variant·차량/Zone/배포 환경을 검증한 결과는 아니며 Result는 NOT RUN을 유지한다.

| Requirement | Component | Interface | Scenario / variant | Test Case | Future verification | Future Result |
| --- | --- | --- | --- | --- | --- | --- |
| SYS-ARCH-001 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-CENTRAL-ALLOC | IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | Deployment | TC-ARCH-001 | M5/M12 | NOT RUN |
| SYS-ARCH-002 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-CENTRAL-ALLOC, ARCH-CENTRAL-BRIDGE | IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | S01–S03 | TC-CTRL-001 | M2/M6/M7 | NOT RUN |
| SYS-ARCH-003 | ARCH-CENTRAL, ARCH-ZONE-FRONT, ARCH-ZONE-REAR, ARCH-VECU, ARCH-BMS, ARCH-ADAPTER, ARCH-CENTRAL-VM, ARCH-CENTRAL-ALLOC, ARCH-CENTRAL-SESSION, ARCH-CENTRAL-BRIDGE | IF-CENTRAL-VEHICLE-REQUEST, IF-CENTRAL-POWER-REQUEST, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-CAN-BMS, IF-HOST-ACTUATOR, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | ZON-S01, ZON-F01, ZON-F02 | TC-ZON-001, TC-ZON-002, TC-ZON-003 | M4/M5/M6/M7/M9/M12 | NOT RUN |
| SYS-ODD-001 | ARCH-ORCH, ARCH-HOST, ARCH-CENTRAL | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY | S01, S02, S03 | TC-CTRL-002, TC-CTRL-003, TC-CTRL-004 | M7/M8 | NOT RUN |
| SYS-COM-001 | ARCH-ZONE, ARCH-VECU | IF-CAN-STEERING, IF-FAULT-EVENT | F01 | TC-COM-001 | M2/M4/M9 | NOT RUN |
| SYS-COM-002 | ARCH-ZONE, ARCH-VECU, ARCH-CENTRAL-ALLOC | IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | F02 | TC-COM-002 | M1/M2/M4/M5 | NOT RUN |
| SYS-COM-003 | ARCH-ZONE, ARCH-VECU, ARCH-BMS, ARCH-ADAPTER, ARCH-ZONE-FRONT, ARCH-ZONE-REAR, ARCH-CENTRAL-VM, ARCH-CENTRAL-ALLOC, ARCH-CENTRAL-BRIDGE, ARCH-CENTRAL-SESSION | IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | F01–F04; 각 stream loss, EV-F01/02 critical stream; ZON-F01/F02 | TC-COM-001, TC-COM-002, TC-COM-003, TC-COM-004, TC-COM-005, TC-SAFE-001, TC-EV-002, TC-EV-004, TC-ZON-002, TC-ZON-003 | M1/M2/M3/M4/M5/M6/M7/M9 | NOT RUN |
| SYS-COM-004 | ARCH-ZONE, ARCH-ADAPTER, ARCH-BMS, ARCH-VECU, ARCH-ZONE-FRONT, ARCH-ZONE-REAR, ARCH-CENTRAL-BRIDGE | IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-DDS-ZONE-STATUS, IF-HOST-ACTUATOR, IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-HOST-EV-STATUS, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | F01 cached replay; EV-F01 cached dependency; ZON-F01/F02 | TC-COM-005, TC-EV-002, TC-ZON-002, TC-ZON-003 | M1/M2/M3/M4/M5/M6/M7 | NOT RUN |
| SYS-CTRL-001 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-CENTRAL-ALLOC, ARCH-CENTRAL-BRIDGE | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | S01–S03; response perturbation | TC-CTRL-001 | M2/M6/M7 | NOT RUN |
| SYS-CTRL-002 | ARCH-ADAPTER, ARCH-CENTRAL-BRIDGE | IF-HOST-ACTUATOR | F01; missing/invalid/stale actual | TC-COM-001, TC-COM-005 | M4/M6/M7 | NOT RUN |
| SYS-CTRL-003 | ARCH-ADAPTER, ARCH-HOST, ARCH-ORCH | IF-HOST-ACTUATOR | S01–S03; writer audit | TC-CTRL-001 | M6/M7 | NOT RUN |
| SYS-CTRL-004 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU | IF-HOST-SENSOR, IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-DRIVE, IF-CAN-BRAKE, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | S01, S02, S03 | TC-CTRL-002, TC-CTRL-003, TC-CTRL-004 | M6 precursor; M7/M8 | NOT RUN |
| SYS-CTRL-005 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-CAN-STEERING | S01, S02, S03 | TC-CTRL-002, TC-CTRL-003, TC-CTRL-004 | M6 precursor; M7/M8 | NOT RUN |
| SYS-CTRL-006 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-CAN-STEERING | S01, S02, S03 | TC-CTRL-002, TC-CTRL-003, TC-CTRL-004 | M6 precursor; M7/M8 | NOT RUN |
| SYS-CTRL-007 | ARCH-CENTRAL, ARCH-SAFETY, ARCH-ZONE, ARCH-VECU | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-DRIVE, IF-CAN-BRAKE, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | S01, S02, S03 | TC-CTRL-002, TC-CTRL-003, TC-CTRL-004 | M6 precursor; M7/M8 | NOT RUN |
| SYS-CTRL-008 | ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-CENTRAL-ALLOC | IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-DRIVE, IF-CAN-BRAKE, IF-HOST-ACTUATOR, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | RG-01 정상/한계 변화/저속 | TC-REG-001, TC-REG-002, TC-REG-003 | M2/M4/M6/M7 | NOT RUN |
| SYS-CTRL-009 | ARCH-VECU, ARCH-ADAPTER | IF-CAN-DRIVE, IF-HOST-SENSOR, IF-HOST-ACTUATOR | RG-01 에너지/command≠actual/정지 | TC-REG-005 | M2/M6; M7 mapping review | NOT RUN |
| SYS-AI-001 | ARCH-CENTRAL, ARCH-SAFETY | IF-CENTRAL-TRAJECTORY, IF-FAULT-EVENT | AI invalid/timeout variants | TC-AI-001 | M11 | NOT RUN |
| SYS-SAFE-001 | ARCH-SAFETY, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-CENTRAL-VM | IF-DDS-ZONE-STATUS, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-FAULT-EVENT, IF-DDS-FRONT-STATUS, IF-DDS-REAR-STATUS | F01–F04; actuator/compound loss | TC-SAFE-001 | M2/M4/M6/M7/M9 | NOT RUN |
| SYS-SAFE-002 | ARCH-SAFETY, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-ZONE-FRONT, ARCH-ZONE-REAR, ARCH-CENTRAL-VM, ARCH-CENTRAL-SESSION | IF-CENTRAL-VEHICLE-REQUEST, IF-DDS-ZONE-STATUS, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | Startup/recovery; F01–F04 clear; ZON-F01/F02 | TC-SAFE-002, TC-ZON-003 | M1/M2/M4/M6/M7 | NOT RUN |
| SYS-SAFE-003 | ARCH-ZONE, ARCH-VECU, ARCH-ZONE-FRONT, ARCH-ZONE-REAR | IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-FAULT-EVENT, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | F02, F03, F04; ZON-F01/F02 | TC-COM-002, TC-COM-003, TC-COM-004, TC-SAFE-001, TC-ZON-002, TC-ZON-003 | M2/M4/M5/M9 | NOT RUN |
| SYS-SAFE-004 | ARCH-VECU, ARCH-ZONE | IF-CAN-DRIVE, IF-FAULT-EVENT | F03 양·음수 torque; F04; F02 Drive variant | TC-COM-003, TC-COM-004, TC-COM-002 | M2/M4/M6/M9 | NOT RUN |
| SYS-SAFE-005 | ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-CENTRAL-ALLOC | IF-CAN-DRIVE, IF-CAN-BRAKE, IF-DDS-ZONE-STATUS, IF-HOST-ACTUATOR, IF-FAULT-EVENT, IF-DDS-FRONT-STATUS, IF-DDS-REAR-STATUS | RG-01 cap unknown/stale/0 및 부족분 | TC-REG-002, TC-REG-004 | M1/M2/M4/M6/M7 | NOT RUN |
| SYS-DIAG-001 | ARCH-DIAG, ARCH-ZONE, ARCH-VECU | IF-FAULT-EVENT | F01–F04 event integration | TC-DIAG-001 | M9 | NOT RUN |
| SYS-PERF-001 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-ORCH, ARCH-ADAPTER | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | Timing/overload; S01–S03 | TC-PERF-001 | M3 partial; M5/M7/M12 E2E | NOT RUN |
| SYS-PERF-002 | ARCH-HOST, ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-BMS | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | Multirate; S01–S03, EV-F01 | TC-PERF-002, TC-EV-002 | M1 rate 결정; M2/M3/M6/M7 | NOT RUN |
| SYS-PERF-003 | ARCH-ORCH, ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER | IF-HOST-SENSOR, IF-CENTRAL-VEHICLE-REQUEST, IF-HOST-ACTUATOR, IF-FAULT-EVENT, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | Pause/reset/slow Target; F01–F04 | TC-PERF-001, TC-PERF-002 | M3/M5/M6/M7 | NOT RUN |
| SYS-EV-001 | ARCH-CENTRAL, ARCH-ZONE, ARCH-BMS, ARCH-VECU, ARCH-EV-PLANT, ARCH-ZONE-FRONT, ARCH-ZONE-REAR, ARCH-CENTRAL-VM | IF-CENTRAL-POWER-REQUEST, IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-MODEL-BMS, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-MODEL-DRIVE-POWER, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | EV-S01, EV-F02 startup/shutdown; ZON-F01/F02 | TC-EV-001, TC-EV-004, TC-ZON-003 | M1/M2/M4/M6/M7 | NOT RUN |
| SYS-EV-002 | ARCH-BMS, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-CENTRAL-BRIDGE | IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-DDS-ZONE-STATUS, IF-HOST-EV-STATUS, IF-DDS-FRONT-STATUS, IF-DDS-REAR-STATUS, IF-DDS-REAR-CMD | EV-S02, EV-F01 valid 0/unknown/cached source | TC-EV-002, TC-EV-003 | M1/M2/M3/M4/M5/M6/M7 | NOT RUN |
| SYS-EV-003 | ARCH-VECU, ARCH-ZONE, ARCH-BMS, ARCH-CENTRAL-VM, ARCH-CENTRAL-ALLOC | IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-CAN-DRIVE, IF-CAN-BRAKE, IF-MODEL-DRIVE-POWER, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS | EV-S02; RG-01 cap change/invalid | TC-EV-003, TC-REG-001, TC-REG-002, TC-REG-004 | M2/M4/M6/M7 | NOT RUN |
| SYS-EV-004 | ARCH-BMS, ARCH-ZONE, ARCH-VECU, ARCH-EV-PLANT, ARCH-DIAG, ARCH-ZONE-FRONT, ARCH-ZONE-REAR, ARCH-CENTRAL-VM | IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-MODEL-BMS, IF-FAULT-EVENT, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-MODEL-DRIVE-POWER, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | EV-F01/02 fault/clear/reinitialize; ZON-F01/F02 | TC-EV-002, TC-EV-004, TC-ZON-002, TC-ZON-003 | M1/M2/M3/M4/M6/M7/M9 | NOT RUN |
| SYS-EV-005 | ARCH-EV-PLANT, ARCH-BMS, ARCH-VECU, ARCH-ADAPTER | IF-MODEL-BMS, IF-CAN-DRIVE, IF-HOST-EV-STATUS | EV-S02 energy/full/empty/invalid | TC-EV-005, TC-REG-005 | M2/M6; M7 mapping review | NOT RUN |

정의: [requirements](../requirements/system_requirements.md),
[components](../architecture/system_architecture.md), [interfaces](../icd/interface_overview.md),
[scenarios](scenario_baseline.md), [cases/results](verification_strategy.md).

변경 절차: Requirement revision/rationale 기록 → component/interface 영향 확인 →
scenario/test oracle 갱신 → 해당 milestone에서 실행 → Result ID/artifact/verdict 연결.
같은 test의 component-only/plant/board별 run은 별도 결과로 보존한다. 미구현이나 TBD를
빈 결과나 0 ms로 대체하지 않는다. 모든 required variant와 환경 조건을 검증하기 전에는
일부 PASS만으로 requirement 전체를 VERIFIED로 변경하지 않는다.

## Hosted OS pilot evidence

[ADR-0040](../adr/ADR-0040-steering-rtos-pilot-and-delay-observation.md)의 Steering Trampoline OS 기능 12 runs와
native Linux 회귀 42 runs는 PASS다. Source/Actual·late/skipped·observer coverage·spawn 검사 5개를 추가한 당시 Python은 48개였다.
[ADR-0041](../adr/ADR-0041-arm64-rtos-build-and-host-preflight.md)의 native/ARM64 빌드와 native OS 신규 12 runs도 PASS다.
Architecture 혼용·CMake compiler·FIFO probe 검사 6개를 더해 현재 Python 54개다. ARM64 runtime·RT workload는 NOT RUN이다.
C++ unit은 normal/sanitizer 각각 521개 이력을 유지한다. 진단 6 runs의 정상 timing 실패 4개는 기능 PASS와 구분한다.
이는 local component 부분 증거이며 RTE/BSW·Target 및 전체 system TC의 Result는 NOT RUN을 유지한다.
