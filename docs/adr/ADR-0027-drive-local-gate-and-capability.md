# ADR-0027: 필수 EV Drive gate와 회생 가용량

Date: 2026-10-15. Status: **Host functional SIL component 구현·시험 / 학습자 review PENDING**.
TBD-02/03/12/13/14의 부분 구현이다. Full TC-REG/EV/ZON은 NOT RUN이다.

후속 구조 변경: [ADR-0032](ADR-0032-ecu-and-sil-execution-boundaries.md)에서 ECU의 plant 소유/호출을
외부 SIL 연결 코드로 옮겼다. 아래는 이 ADR 채택 당시의 설계·시험 이력이다.

## 결정과 책임

`vecu/drive/DriveController`는 Command, 원천 보존된 DriveBatteryLimits, 별도로 검증한 parent의
Central DrivePermission, Drive 자체 actual speed/HV를 요구한다. 허용을 우회하는 config는 없다.
기존 `DriveActuator`는 명시적인 isolated torque-response fixture로 남긴다. 기존 예제/vCAN의
성격을 갑자기 operational EV로 바꾸지 않는다. 물리 응답은 공통 `simulation/drive/TorqueResponse`다.

`interfaces/drive/drive_local_sensors.hpp`는 independent speed/HV acquisitions의 Epoch/sequence/
source/dependency를 정의한다. HV voltage·inverter-ready·local fault는 실제 로컬 센서 port다.
Central permission이나 참조한 CAN PowerStatus로 로컬 HV를 대체하지 않는다.
Model Epoch는 trusted startup 인자이고 application 재시작과 독립이다.

기존 P05/receiver를 재사용한다. Limits 입력은 **0x193 DriveBatteryLimits**만 받으며 0x284 BMS
원본 frame을 자동 변환/수용하지 않는다. Demo는 명시적인 relay fixture에서 기존 forward 함수를
사용한다. Central grant/trusted parent도 독립 fixture다. 실제 Central/Zone/DDS runtime은 후속이다.
Wire/DBC의 변경은 없다. 새 별도 실행 프로그램 대신 기존 CLI에 `drive-gated`를 추가한다.

## Gate와 복구

모든 필수 입력이 usable이고 BMS producer가 NormalPath NORMAL/DEGRADED, Central AllowNormal이
fresh/parent-bounded이며 actual HV/inverter health·speed가 정상일 때만 활성화한다.
초기에는 fresh zero Command/known Inhibit·센서를 먼저 보낼 수 있고 HV OFF는 정상 non-driving INIT다.
상위가 허가를 내렸어도 다른 첫 입력이 아직 도착하지 않았으면 활성화하지 않는다. 최초 수신 순서만으로
fault를 만들지는 않는다. 각 critical receiver/startup 80 ms monitoring 계약은 유지한다.

활성화 뒤 permission Inhibit/loss/expiry, 한계·로컬 센서 상실, BMS protection·HV fault·overspeed,
continuity/deadline은 zero-target과 latch다. Fresh frame이나 정상 센서로 자동 복구하지 않는다.
새 trusted application Epoch/INIT는 actual torque를 보존하고 pending goals를 취소한다.
Clock rollback은 physics를 진행하지 않고 publication을 중단한다. Missed interval은 hold/no catch-up이다.
수신 함수에서도 갱신 전에 기존 입력의 expiry를 확인하므로 tick 사이의 늦은 재발행으로 loss를 숨기지 않는다.

Valid zero charge는 soft constraint여서 새 regen target만 0이고 구동 가능성은 별도다.
Valid zero discharge는 launch도 막는다. 한쪽 limit unknown은 0이나 반대쪽 값으로 보충하지 않는다.
이번 conservative strategy는 양쪽 limits를 모두 요구한다. Known Inhibit/latched health와 충분한
관측이 있으면 capability valid zero/Disabled, 필수 관측 불명에는 unknown/InputsInvalid다.
Actual torque validity와 capability validity는 독립이다.

## Power와 torque envelope

모든 torque/speed는 aggregate driven-wheel 기준이다. Propulsion upper estimate는
`Pdraw = P_reserve + T×omega/eta + k×T²`다. Fixed reserve에는 공유 pack 한계에서 fixture의
auxiliary/idle load 몫을 포함한다. `eta=0.9`는 부하 비례 변환항의 가정 하한이며 모든 손실을
포함한 총 효율 하한은 아니다. `k=0.01 W/(Nm²)`의 torque-current 손실 근사는 정지 때도 유한한
launch 한계를 만든다. Positive quadratic root를 cancellation 없이 계산한다. BatteryState SOC만으로 재계산하지 않는다.

Regen은 `Preturn <= |T|×omega`의 보수적 energy bound로 `Tcharge <= Pcharge/omega`를 적용한다.
이는 실제 회수 효율을 100%로 적분한다는 뜻이 아니다. Actual charge power/loss integration은 없다.
정지/저속에서는 나누기 전에 regen taper를 적용한다. Motor torque/constant mechanical power와
BMS charge acceptance 중 작은 값을 쓰고 0.1 Nm 단위로 내린다.

Fixture: physical −200..300 Nm, motor mechanical propulsion 20 kW/regen 10 kW,
speed maximum 100 rad/s, regen ≤2 rad/s zero·≥5 rad/s full, reserve 200 W,
HV 300..450 V, normal/protection rate 1000/2000 Nm/s, normal delay 50 ms다.
차량 calibration, motor map/FOC/current sensor 모델이나 실차 안전 envelope의 채택이 아니다.
실제 부하/온도/효율 map과 auxiliary power allocation은 M6에 일관되게 연결해야 한다.

물리/제어 경계와 speed·battery 기반 회생 제한의 참고는
[MathWorks regenerative/friction control](https://www.mathworks.com/help/sdl/ug/regenerative-friction-braking-control.html),
torque-speed envelope/효율 map의 참고는
[Motor & Drive 공식 모델](https://www.mathworks.com/help/sps/ref/motordrivesystemlevel.html)이다.
위 식과 수치는 StrataDrive의 fixture 결정이다.

## 지연·양자화·원천 시각

TorqueResponse.constrain은 직전 interval을 기존 조건으로 진행한 뒤 active/queued/staged goal을
현재 envelope로 제한한다. 축소한 옛 goal을 한계 회복 시 되살리지 않는다. 새로운 큰 목표는 새 delay를
거친다. Bound 밖의 actual은 보호 rate로 수렴하고 즉시 clip하지 않는다. Controller는 residual을
별도 `actual_outside_envelope`로 보고한다. Fault zero는 검출 시각부터 적용하고 대기 goals를 취소한다.

**한계는 target envelope이며 actual response가 즉시 따라왔다는 보장이 아니다.** Full SOC에서
charge-zero가 된 동안에도 유한 시간의 음수 actual residual이 있을 수 있다. M6 energy coupling 전에
headroom/guard band·fault reaction·실제 power/제동 deficit budget을 검증해야 한다. Battery 충전량을
임의 clip하거나 그 residual을 command 0으로 대체해서 문제를 감추지 않는다.

Local source/dependency 30 ms, 두 local acquisition skew 20 ms, limits/permission source 50 ms/
dependency 70 ms를 검사한다. Control period/max gap은 10/30 ms다. Wheel source는 acquisition을
보존하고 capability source는 계산 시각, input은 local/limits/grant/사용한 parent의 oldest dependency다.
Inhibit의 사용하지 않는 zero-valued physical reference는 dependency로 해석하지 않는다.
Capability dependency가 직전 발행 값보다 뒤로 가면 timestamp를 올리지 않고 해당 publication을
unknown으로 생략한다. Receiver의 opt-in 70 ms capability input budget을 명시하며 기존 default 30 ms는 유지한다.

## 검증과 다음 단계

[학습·실행](../learning/m2_drive_gate.md), [37개 gate 시험](../../tests/unit/drive_controller_test.cpp)과
공유 physics의 4개 추가 시험으로 normal·ASan/UBSan 전체 unit은 334개다.
기존 CLI의 여섯 scenario는 BmsController→명시적 relay/독립 Central fixture→DriveController→
TorqueResponse→Actual/P05→receiver를 확인한다. RC bus는 PowerModel actual이며 wheel speed/
inverter-ready/SOC/thermal은 fixture다. 실제 battery DC energy coupling이 아니다.
기존 isolated Drive model vCAN 3개는 normal·sanitizer 각각 격리 네트워크에서 재실행해 통과했다.
이전 97개 전체 통과 이력을 이번 전체 재검사나 EV gate transport PASS로 바꾸지 않는다.
다음은 actual torque/speed·DC power·battery의 일관된 energy coupling과 모델 시간/부하·guard band 검토다.
Central allocation/마찰 보충·차량 motion/stop·Target timing/OS/RTE/BSW와 full TC는 후속이다.
