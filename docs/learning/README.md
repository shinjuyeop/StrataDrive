# 학습 원칙

이 프로젝트에서는 Codex가 코드를 빠르게 생성하는 것보다 작성된 코드와
architecture를 내가 직접 이해하는 것을 우선한다. M0 문서 baseline과 개인의 이해 기록은 구분한다.
생성된 파일이나 문서 review PASS만으로 내가 설계를 설명할 수 있다고 간주하지 않는다.
이번 M0 계약은 사용자 요청의 범위/판정 기준을 반영하며 종료 검토는
[M0 baseline summary](../m0_baseline.md)에 기록한다.

각 milestone은 다음 순서로 진행한다.

1. 현재 작은 작업에 필요한 개념 공부
2. 요구사항 확인
3. 설계 작성
4. 작은 단위 구현
5. diff/code review
6. 직접 실행
7. fault/edge case test
8. 학습 내용 기록
9. Acceptance 기준 확인
10. 다음 milestone

**Codex가 작성한 코드를 내가 설명할 수 없다면 완료로 간주하지 않는다.**

선행 공부의 범위는 바로 구현할 작은 작업까지다. 필요한 개념을 짧게 설명한 뒤
구현·실행·결과 해석으로 이어간다. 조향 dynamics/jam 판정은 M2, 상세 안전 분석과
AUTOSAR 실습은 관련 설계·구현과 함께 진행한다. 전체 이론 학습을 M1 시작 조건으로 두지 않는다.
첫 실행은 [M1 SocketCAN/vCAN 송수신](m1_vcan_start.md)이며,
첫 C++은 [Steering angle field codec](m1_steering_codec.md)이며,
[Steering frame codec·DBC parser 검증](m1_steering_frame_codec.md)을 거쳐
[AUTOSAR E2E Profile 5 Protect/Check](m1_autosar_e2e_profile5.md)를 적용했다.
[Steering 수신부의 수용/시간/Epoch/timeout](m1_steering_receiver.md)을 구현하고
[SocketCAN/vCAN 연결](m1_steering_socketcan.md)로 독립 TX/RX와 wall-time fault를 시험했다.
[Brake 압력/frame·DBC·vCAN wire 검사](m1_brake_codec.md)까지 확장했다.
[Brake 수신 수용/timeout](m1_brake_codec.md#application-수신부-추가)도 구현·시험했다.
[Drive 구동·회생 토크와 피드백 wire/receiver](m1_drive_codec.md)도 기존 도구에서 구현·시험했다.
현재 이해 확인/직접 재현은 PENDING이며 M1 통신 검사 이후 M2 응답 모델로 진행한다.
[M1 마무리 session/queue](m1_session_queue.md)에서 영속 Epoch와 실제 application/kernel overflow,
이전 Epoch의 P05 counter 오염 방지와 기술 exit checklist를 구현·검사했다.
[M2 첫 조향 모델](m2_steering_model.md)의 delay/rate/saturation과 local hold를
기존 Command TX → model → Actual RX에 연결했다. Unit 13개와 model vCAN 2개를 추가했다.
[첫 Brake 모델](m2_brake_model.md)은 가압/감압과 0/unavailable·loss protection을 설명하고
unit 16개와 vCAN 3개를 추가했다.
[Drive 응답과 제어기 구분](m2_drive_model.md)은 ECU/물리 모델 모듈 분리, signed torque·zero ramp와
unit 20개/vCAN 3개를 추가했다.
[Battery 에너지·관측](m2_battery_model.md)은 actual DC 입력, energy balance와 등가 전기·온도,
센서 group의 독립 identity/age 시험 30개를 추가했다. Battery 단계 시점 전체 unit 222개였으며 기존 vCAN all 97개 증거를 유지한다.
후속 BMS/Power/Drive gate의 시험과 isolated torque 응답 시험을 구분한다.

후속 [EV-01 범위/역할](../icd/ev_power_bms_design.md)을 정리했다. BMS와 battery model,
power READY와 system NORMAL, 원천 status와 Zone 전달의 차이를 복습한다.
2026-10-14 [BMS wire 초안](../icd/bms_frame_draft.md)과 DBC/CRC 검사를 추가했다.
[BMS 물리값·frame codec과 항목별 receiver](m1_bms_codec.md)도 구현·시험했다.
50/100 Hz critical 경로와 10 Hz 관측, valid 0/unknown, power request/actual/permission,
원천 전달/expiry를 복습한다. 기존 vCAN fixture도 EV 36개 case로 확장했다.
기존 actuator 27 + EV 36에 queue 24/restart 2를 더한 M1 89개 독립 process 시험에 M2 Steering 2개·Brake 3개·Drive 3개를 더한 all 97개 이력을 유지한다.
Battery는 로컬 모델의 셀 전압·온도 극값 관측까지 구현·시험했다.
[BMS 판단](m2_bms_controller.md)은 그 관측의 유효성·시간을 검사하고 충방전 한계·보호 latch를 만든다.
[Power lifecycle](m2_power_lifecycle.md)은 BMS gate와 실제 RC/접점/current로 프리차지·종료를 확인한다.
[Drive local gate·capability](m2_drive_gate.md)는 원천 limits·Central permission·로컬 HV/속도를 확인하고
valid zero/unknown과 actual 잔여 응답을 구분한다. Gate 단계 시점은 전체 unit 334개였다.
Gate 단계에는 normal·sanitizer 각각 기존 Drive model vCAN 3개를 격리 네트워크에서 재검사해 통과했다.
[실제 토크에서 배터리 충전까지](m2_drive_energy.md)는 이상적 HV/외부 speed에서 actual DC·손실·auxiliary·SOC와
BMS/Drive loop를 연결하고 28개를 더해 당시 전체 unit은 362개였다.
[실제 전원 회로 연결](m2_ev_power_circuit.md)은 구간 current/heat·capacitor·경로 손실과 Battery의 atomic commit을 추가해
당시 전체 unit 391개였다. [M2 수용 검토](../m2_acceptance_review.md)에서 normal·sanitizer 각각 전체 unit과
model vCAN 8개를 재검사하고 설정·고장·세션 경계를 대조했다.
후속 [Steering response monitor](m2_steering_fault_monitor.md)는 물리 9개·monitor 21개·adapter 9개를 추가해
당시 전체 unit은 **430개**였다. 정상 rate 범위·residual/dwell과 sensor health·fresh Actual/latch를 시험했다.
[Brake response monitor](m2_brake_fault_monitor.md)는 plant 10개·monitor 16개·adapter 14개를 더해 당시 전체 **470개**였다.
가압/감압 이상과 보호 요청/압력 관측을 구분한다.
[ECU/SIL 실행 경계](m2_execution_boundaries.md)를 분리하고 core 18개·외부 물리 진행 3개를 더해 M2 시점 전체 **491개**였다.
[M3 첫 주기 실행·독립 감시](m3_steering_timing.md)에서 schedule/monitor/snapshot 14개를 추가해 당시 C++ **505개**,
Python 리포터 5개였다. Steering의 실제 thread·deadline·CSV trace를 읽고 정상/overrun/stall에서 누락 job과 물리 보호를 비교한다.
후속 [다중 주기·CAN 감시](m3_multirate_runtime.md)는 valid RX/trusted context 11개와 리포터 3개를 추가해
당시 C++ **516개**, Python **8개**였다. Brake/Drive/Power 10 ms·BMS 20 ms와 RX의 정지/CRC 손상을 비교한다.
[고정 부하·CPU 배치](m3_cpu_placement.md)는 리포터 8개를 더해 당시 C++ **516개**, Python **16개**였다.
Requested duty와 실제 CPU 시간, task elapsed/response·miss를 구분하고 실패 run도 비교한다.
후속 [Drive Actual CAN 송수신](m3_drive_feedback.md)은 취득 시각·독립 보조 시간·replay 검사 5개와 Python 5개를 더해
현재 C++ **521개**, Python **21개**다. 배치/우선순위·Target 확장은 후속이며 학습자 수용 기록은 별도로 남긴다.
[ZON-01](../architecture/zonal_partition.md)의 Front/Rear 두 Zone을 채택했다. Central의 별도 VCU가 차량 전체
관리·배분/session/feedback 집계를 맡고 Front는 Steering/Brake, Rear는 Drive/BMS gateway를 맡는다. 단일 Zone component 확인 후
M4/M5에 분리하며 Central–Zone protocol(TBD-15)/runtime/TC-ZON은 미구현·NOT RUN이다.

실행 프로그램은 `actuator_demo` 하나다. `tools/actuator_demo.cpp`는 명령 분기와 도움말을 맡고,
예제 구현은 `tools/demo/`의 Steering·Brake·Drive·EV 파일로 나눈다.
Linux `steering-runtime`과 `multirate-runtime`은 `simulation/runtime/`의 실행 연결을 호출하며 같은 executable을 사용한다.
다중 주기의 [owner별 CPU 배치](m3_cpu_placement.md#owner별로-cpu를-나누기)는 같은 부하에서
RX 단독 이동과 감시·plant 동반 이동을 비교한다. 요청/실제 배치와 모든 task의 miss·출력 만료를 함께 확인한다.
다음 [전체 owner cycle](m3_owner_cycles.md)은 sleep 요청부터 실제 실행까지의 지연과 전체 body/CPU 시간을 나누고,
RX 누락과 두 owner를 같은 시간축에서 대조한다. 이후 [ADR-0039](../adr/ADR-0039-owner-completion-guards.md)에서
Host 4 ms 완료 budget·교차 guard와 별도 수신 감시를 연결했다. Python 검사는 기존 파일에 6개를 추가해 **43개**다.
`angle`, `frame`, `e2e`, `receiver`, `brake-pressure`, `brake-frame`, `brake-receiver`,
`drive-frame`, `drive-feedback`, `bms-value`, `bms-frame`, `bms-receiver`, Linux `epoch`, `steering-model`, `brake-model`, `drive-model`, `battery-model`, `bms-control`, `power-model`, `drive-gated`, `drive-energy`, `ev-power` 중 필요한 명령을 실행한다.
자동 단위 시험은 모듈별 기존 파일에 case를 추가하며 SocketCAN 통합 시험은
`tests/integration/can/`에 모았다. 배치/추가 기준은 [품질 정책](../quality_policy.md#코드예제시험-배치)에 있다.

M0에서는 4~7단계의 실행 기능 작업을 시작하지 않는다. 대신 문서 diff, 구조,
계약의 정상/오류 경로를 검토하고 configure-only 확인의 한계를 기록한다.
M1 이후 구현은 별도의 milestone 작업으로 진행한다.

## Standards learning cycle

[개발·학습 계획](../engineering_plan.md)에 따라 한 번에 작은 기능이나 fault 하나를
다룬다. 첫 대상은 Steering 경로이며, [concept study](../safety/concept_study.md)의
Item 경계와 차량 수준 위험을 먼저 이해한 뒤 interface와 AUTOSAR 개념에 연결한다.

- 개념: Item/HARA, SWC/Port/Runnable/Task 중 이번 작업에 필요한 용어와 책임을 설명한다.
- 대입: 기존 Requirement/ICD/Component에 연결하고 현재 가정과 미결정 사항을 표시한다.
- 실습: 작게 설정·생성·구현하고 diff를 검토한 뒤 직접 실행한다. 문서 작업에는 해당하지
  않는 runtime 단계를 완료했다고 표시하지 않는다.
- 해석: 예상과 실제 결과의 차이, 검증하지 못한 범위와 다음 질문을 기록한다.

표준 개념을 참고한 설계, 실제 구현체를 사용한 실행, SIL에서 관측한 결과를 구분한다.
AUTOSAR OS 예제 실행은 RTE/BSW 통합 완료가 아니며 HARA 초안 작성은 ASIL 평가나
안전 요구사항 도출 완료가 아니다. 설명하지 못한 개념은 다음 학습 항목으로 남긴다.

첫 실습 자료는 [조향 fault 비교](../safety/concept_study.md#first-exercise-steering-fault-comparison)다.
Command loss, feedback loss, actuator jam의 관측값과 검출 주체를 각각 설명한다.
특히 fresh feedback이 계속 도착해도 actuator가 고장일 수 있는 이유를 자신의 말로 남긴다.
이 자료는 Codex가 준비한 분석 메모이며 학습자가 작성한 이해 기록을 대신하지 않는다.

다음 자료는 [정상 Steering 응답](steering_response.md)과
[Interactive graph](steering_response.html)다. Dead time, Rate limit, Angle saturation을
구분하고 한 번에 한 parameter만 바꿔 설명한다. 그래프의 설명용 값은 실제 vECU
parameter가 아니며 M1/M2 runtime 구현이나 차량 시험의 완료로 표시하지 않는다.

## 학습 기록 template

- 날짜 / milestone / 관련 commit: TBD
- 공부한 개념과 직접 확인한 공식 자료: TBD
- Requirement / Component / Interface / Test ID: TBD
- 내 말로 설명한 설계와 대안의 trade-off: TBD
- 참고 표준/판과 프로젝트 적용 범위, 확인하지 못한 가정: TBD
- AUTOSAR 실습 시 입력 설정 / generator·toolchain 버전 / 생성 결과: 해당 시 기록
- 작은 변경의 diff와 내가 설명하지 못한 부분: TBD
- 직접 실행한 명령 / 환경 / 결과 경로: TBD (미실행은 NOT RUN)
- fault / edge case와 예상 및 관측 결과: TBD
- 해결하지 못한 질문 / 다음 실험: TBD
- Acceptance 기준 확인 / 학습자 검토: PENDING

기록은 필요한 시점에 작은 Markdown 파일로 추가한다. 모델 답변을 그대로
붙여넣는 대신 이해한 내용, 재현 조건과 틀렸던 가정을 함께 남긴다.

## Hosted RTOS pilot and scheduling diagnosis

다음 [Steering RTOS 파일럿](m3_rtos_pilot.md)은 실제 Trampoline Task/Event/Alarm/Resource를 사용한다.
기존 ECU와 CAN·외부 물리 모델을 연결하고, 별도 sampler로 Host runqueue 대기를 관측한다.
기존 Python 리포터 파일에 source/late/skipped·counter coverage·spawn 검사 5개를 추가해 당시 **48개**였다.
OS 기능, 가상 tick, Host wall timing, Target 검증은 각각 구분한다.

후속 [native Linux FIFO 비교](m3_native_fifo.md)는 같은 M3 workload에 owner별 RT 우선순위를 적용한다.
모든 owner의 startup 준비·실제값 확인과 실패 시 취소, 호출 thread 복원을 검사한다.
ARM64/권한 사전 점검과 해당 검사를 포함한 당시 Python은 **59개**, C++은 normal/sanitizer 각각 **523개**였다.

[M3 수용 검토](../m3_acceptance_review.md)에서 IO 동반/FIFO Host 실행 기준을 선택했다.
Guarded 주기 집계의 run 사이 gap을 수정하고 Python **60개**를 검사했다. 원본 96회 재분석의 판정은 **94 PASS/2 FAIL**로 동일하다.
타이밍 예외와 직접 재현·설명은 PENDING이며, M4 coordinator 입출력·상태 계약부터 준비한다.

[Hosted timer 지연 수정](m3_rtos_pilot.md#절대-타이머로-누적-지연-줄이기)은 relative sleep의 누적 drift와
FIFO 효과를 48회 비교했다. Absolute timer의 추가 Host timing 24/24, native FIFO 후속 102/102를 확인했다.
Python 63개와 C++ normal/sanitizer 각각 523개를 검사했다. 상대 대조군 timing 실패·원래 native 실패 2건은 보존한다.

[M4 Central 정상 주행 준비 조건](m4_normal_drive_readiness.md)은 두 Zone의 health와 개별 Actual·BMS 입력을
각각 검사한다. 준비됨과 실제 허가를 구분하며 INIT Actual·known zero와 원천 age를 보존한다.
새 unit 16개를 더해 C++ normal/sanitizer 각각 539개 PASS다. 다음은 lifecycle/허가 상태 owner다.
