# ADR-0023: 첫 Drive torque 응답과 ECU·물리 모델 분리

Date: 2026-10-15. Status: **Host functional SIL component 구현 / 학습자 review PENDING**.
TBD-02/03/04/13, IF-CAN-DRIVE와 DRIVE_COMMAND_LOSS의 부분 검증에 연결한다.

## 결정과 범위

[ADR-0022](ADR-0022-leaf-classic-development-methodology.md)에 따라 두 책임을 별도 모듈로 둔다.

- `vecu/drive/DriveActuator`: 기존 DriveReceiver, trusted session, 명령 수용·freshness·local fault,
  정상/zero target 선택, Actual metadata/P05를 맡는 ECU 소프트웨어의 부분 구현.
- `simulation/drive/TorqueResponse`: 목표 torque의 delay, signed rate/물리 한계와 zero-target 응답.
  CAN/Epoch/permission/OS에 의존하지 않는 SIL 물리 모델이다.

이 adapter는 **독립 torque 응답 fixture 전용**이다. 차량 운행용 Drive runtime이 아니다.
BMS charge/discharge power limit, drive permission, 실제 local HV, wheel speed와 효율을
아직 연결하지 않았다. Command 수용이나 `NORMAL` stream 상태로 전원 준비·정상 주행 허가를
선언하지 않는다. Wheel speed와 regen capability는 unavailable / InputsInvalid로 보낸다.
고정 음수 torque 한계는 시험용 물리 envelope이며 배터리가 충전을 수용한다는 근거가 아니다.
실제 Drive 통합에서는 [EV-01의 local gate](../icd/ev_power_bms_design.md#한계-freshness와-보호)가 필수다.

수신 command와 실제 torque는 aggregate driven-wheel 기준이다. 전진 구동 양수·회생 음수이며
후진, motor 전류/전압, 인버터 PWM, 회수 에너지와 차량 감속을 이번 모델에서 계산하지 않는다.
현재 control 경로의 rate/saturation은 응답 근사이며 PID/PI/FOC 제어기의 구현이 아니다.
차량 속도 제어는 M8의 Central Controller, 회생/마찰 배분은 M4의 Central allocation이다.
상세 motor current loop는 현재 확정 범위가 아닌 별도 확장이다.

## 응답과 보호

Fixture: command -300..500 Nm, physical -200..300 Nm, 초기 0 Nm,
normal rate 1000 Nm/s, 보호 zero rate 2000 Nm/s, delay 50 ms.
Control 최소 간격 10 ms, 허용 gap 30 ms, source age 30 ms, valid-RX timeout 80 ms다.
이 값은 경계를 관측하기 위한 시험 설정이며 OEM calibration/차량 보호 deadline이 아니다.

같은 목표의 반복 수신은 source freshness만 갱신한다. 변경 목표는 고유 due를 가진다.
고정 128-entry FIFO에 보관하며 adapter의 delay<=100 periods 제한으로 정상 tick에서
최대 101개를 보관한다. Due 사이를 나누어 실제 경과 시간에 rate를 적용한다.

Source expiry/timeout, continuity loss 또는 control gap 위반에서 대기 목표를 취소하고
zero target을 선택한다. Normal delay를 우회하지만 actual은 zero rate로만 0에 접근한다.
부호 반전·overshoot 없이 0에서 멈추고 반복 fault 관측으로 ramp 시작을 미루지 않는다.
유효한 정상 0 command는 normal delay/rate를 사용하므로 이 보호 동작과 구분한다.
보호 검출 이전의 미관측 interval은 hold하며 보호 운동을 검출 시각 이전으로 소급하지 않는다.
Missed tick 구간도 hold하고 다음 정상 간격부터 zero ramp를 진행한다.
Clock 역행은 물리 갱신·publication을 중단한다. 회복에는 새 trusted Epoch가 필요하다.
재시작은 physical torque를 유지하고 INIT에서 zero target을 사용한다.

Actual은 독립 control source/sequence/P05와 마지막 수용 Command의 CausalSequence를 갖는다.
Startup에서 수용 Command가 없는 timeout은 torque unavailable이며 causal=0은 진단용이다.
통신 검출 상한과 actual torque 해소 시간을 구분한다. Fixture에서 300 Nm는 보호 시작 후
150 ms, -200 Nm는 100 ms의 정상 tick 경과가 필요하지만 이 값을 system deadline으로 채택하지 않는다.

## 검증과 후속

[실행·학습 안내](../learning/m2_drive_model.md)에 정상 양·음 saturation/전환/0 command,
두 부호의 loss zero ramp, late frame/restart/clock/deadline, bounded history의 시험을 기록한다.
기존 TX/RX/model runner와 `actuator_demo drive-model`을 확장하고 별도 실행 프로그램은 추가하지 않는다.
CAN ID/layout/P05와 기존 requirement/TC의 수용 기준은 유지한다.
Actual 값은 물리 모델의 결과이며 command echo가 아니다.
Classic SWC/Runnable/Task 대응은 설계 후보이고 ARXML/RTE/BSW pilot은 NOT RUN이다.
BMS/Power 모델·원천 검증→실제 local gate·capability 계산→Central 배분/차량 closed-loop 순으로 연결한다.
