# ADR-0025: 첫 BMS 충방전 한계·보호 판단

Date: 2026-10-15. Status: **Host functional SIL component 구현·시험 / 학습자 review PENDING**.
TBD-12/13/14와 SYS-EV-001/002/005의 부분 검증이다. System TC는 NOT RUN을 유지한다.

## 결정과 책임 경계

`vecu/bms/BmsController`는 별도 local sensor port를 소비하는 20 ms runnable이다.
`interfaces/bms/battery_sensor_snapshot.hpp`에 model identity·개별 acquisition·dependency 계약을
분리했다. BatteryModel의 진단 truth나 simulation 전용 fault enum을 참조하지 않는다.
물리 모델은 같은 port를 제공하며 기존 simulation type 이름은 alias로 유지한다.
SOC/electrical/pack temperature/cell voltage extrema/cell temperature extrema 다섯 group이 모두
유효하고 fresh하며 시간적으로 정합할 때만 한계를 계산한다. 일부 입력의 상실에도 정상 한계를
유지하는 degraded strategy는 이번에 추정해서 넣지 않았다.

실제 BMS의 전압·전류·온도 기반 current limitation과 protection의 책임 구분은
[MathWorks 공식 예제](https://www.mathworks.com/help/simscape-battery/ug/protect-battery-charge-discharge-for-electric-vehicle.html)를 참고한다.
계측과 battery disconnect hardware의 책임은
[Bosch BMS/BDU 설명](https://www.bosch-mobility.com/en/solutions/powertrain/fuel-cell-electric/battery-management-system/)을 참고한다.
아래 수치/회복 정책은 이 프로젝트의 SIL fixture 결정이다. 해당 예제/제품의 동작이나 OEM
calibration을 재현한다고 주장하지 않는다. 실제 cell data sheet·chemistry·fault reaction analysis가 우선한다.

## 한계와 보호

충전과 방전 각각 SOC·cell voltage·온도 ramp의 **최솟값**으로 base current를 줄인다.
Cell voltage는 충전 시 max, 방전 시 min을 사용하고 온도는 pack 및 cell 극값을 모두 고려한다.
`P_allowed = min(P_cap, V_measured × I_base × min(factors))`를 기존 wire의 10 W 단위로
**내림**한다. Generic codec의 nearest rounding은 유지한다. 표시하는 허용 전류는
내림한 power/V이며 값은 nonnegative magnitude다. 실제 전류의 부호(+방전/−충전)와 구분한다.
Reason은 가장 제한적인 factor 하나이며 동률은 SOC→온도→전압 순이다. 모든 factor가 1이면
고정 max-power cap도 정상 설계 한계이므로 Nominal이다.

Operating boundary의 valid zero는 해당 방향만 차단할 수 있다. 별도 hard threshold의
cell/pack OV·UV, 고·저온, 충·방전 overcurrent는 발견 즉시 양방향 valid zero와 inhibit request를
만들고, 항목별 fresh acquisition 40 ms 지속 후 latch한다. 서로 다른 fault의 시간을 합치지 않는다.
이는 software supervisor fixture다. 단락/심각한 고장용 독립 hardware protection의 반응 시간이나
안전성을 40 ms로 정의한 것이 아니다.

Startup은 release band 안의 fresh acquisitions 100 ms를 확인한다. 정상화한 센서·온도만으로
latch를 자동 해제하지 않는다. Recovery-ready는 진단일 뿐이며 새 trusted application Epoch와
INIT/release dwell을 다시 통과해야 한다. Hard threshold와 release threshold를 분리해
경계 근처 반복 복구를 막는다. Pending hard trip이 사라지면 latch 전에는 다시 제한 계산이 가능하다.

Missing/invalid/stale/skew/identity 오류에는 unknown/InputsInvalid를 보고한다. Active 중 입력
상실은 latch한다. 초기 센서 미도착은 InitialChecks/unknown으로 대기하며 허용을 만들지 않는다.
유효 센서가 복원돼도 latch 중이면 valid zero/Disabled만 보고한다. Gap >40 ms는 limits를
unknown으로 latch하고, clock rollback/sequence 소진은 publication을 중단한다. Catch-up은 하지 않는다.

## 시간·identity와 CAN

Source age 50 ms, oldest dependency 70 ms, sensor skew 20 ms를 검사한다. Cached group의
identity/time/dependency/value는 불변이다. 새 envelope만으로 old acquisition이 갱신되지 않는다.
Dwell은 관련 acquisition source가 전진할 때만 진행하며 freshness gap이 크면 다시 시작한다.
Pack voltage가 `N×min_cell .. N×max_cell`에 tolerance 2 V를 더한 범위에 있는지도 검사한다.
이는 cell-sum/open-wire/중복 센서 진단이 아니다. Broad wire/finite 범위와 실제 operating
threshold를 구분한다. 모델 energy나 SOC를 BMS가 직접 갱신하지 않는다.

Trusted local startup은 `{application_epoch, model_epoch, enable_ns}`를 명시한다. CAN Epoch는
application session, CausalSequence는 이 mapping에 속한 model batch다. 같은 model Epoch를
유지한 BMS application restart가 가능하며 BatteryModel.initialize를 호출하지 않는다.
새 세션의 dependency는 enable 이전일 수 없으므로 실제 관측/입력을 다시 받아야 한다.
이것은 local component contract이며 실제 Central/Zone startup protocol, model placement/clock과
cross-process session 교환(TBD-12/14/15)을 완료한 것이 아니다.

기존 BmsPowerLimits message/codec/P05/receiver에 연결한다. Schema/DBC 변경은 없다.
State/Origin은 BMS runnable의 상태이며 vehicle NORMAL·HV_READY·DrivePermission이 아니다.
초기 센서 미도착은 INIT/NoAcceptedInput, 유효 센서를 받은 초기 dwell은 INIT/NormalPath다.
Pending hard trip은 DEGRADED/LocalProtection, latch는 FAIL_SAFE/LocalProtection으로 보고한다.
기존 `actuator_demo bms-control`은 plant→port→controller→codec→receiver를 수동 시계로 실행한다.
새 transport executable이나 vCAN case는 추가하지 않았다.

## 검증과 남은 일

[33개 단위 시험](../../tests/unit/bms_controller_test.cpp)은 방향별 derating, 단일 cell 이상,
trip/release dwell, stale/skew/cache/clock/deadline, valid zero/unknown, P05/receiver와
physical energy를 유지하는 application restart를 검사한다. 정상·sanitizer 전체 unit은 255개다.
실행/parameter와 배터리 개념은 [학습 안내](../learning/m2_bms_controller.md)에 있다.

Power lifecycle·precharge·contactor weld/actual HV·Drive local gate 및 실제 limit 추종 동작은
후속이다. 현재 OC protection은 고정 absolute-current band이며 derated dynamic limit의
tracking error/settling fault detector는 미구현이다. 정밀 SOP의 시간 horizon·전압 sag 예측,
SOC 추정/신뢰도·열 제어·balancing·SOH·절연/HVIL·hardware protector·DTC는 별도 단계다.
이 결과로 실차 safety/ISO 26262/AUTOSAR BSW 적합성을 선언하지 않는다.
