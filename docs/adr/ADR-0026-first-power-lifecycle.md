# ADR-0026: 첫 Power lifecycle과 DC-link/contactor 모델

Date: 2026-10-15. Status: **Host functional SIL component 구현·시험 / 학습자 review PENDING**.
TBD-12/13/14의 부분 구현이다. 전체 SYS-EV system TC는 NOT RUN이다.

## 결정과 경계

`vecu/bms/PowerController`는 BMS leaf 내부의 전원 lifecycle runnable이다. 별도 ECU/VCU 계층을
추가하지 않는다. `simulation/power/PowerModel`은 지연 있는 실제 접점과 DC-link RC 응답을 소유한다.
코일 명령/실제 접점/실제 bus 전압을 구분한다. Local sensor port는
`interfaces/bms/power_sensor_snapshot.hpp`다. Controller는 simulation header를 참조하지 않는다.

기존 BMS 한계 runnable은 동일 decision identity/source/dependency를 가진 typed `BmsSafetyGate`를
내보낸다. 초기 검사·전체 금지는 true, 정상 방향별 사용 가능은 false, 입력 상실은 unknown이다.
PowerController는 별도로 이 gate의 Epoch/age/sequence/cache를 검사한다. 같은 leaf의 로컬 연결이며
BMS→Drive application 우회나 Central DrivePermission 생성이 아니다.

기존 PowerRequest codec/P05/receiver와 **별도로 신뢰한 parent context**를 사용한다.
PowerStatus의 CausalSequence/AcceptedRequestSourceTime은 마지막 수용한 Central 결정의
Sequence/Source를 보존한다. Upstream parent sequence, physical model batch와 혼동하지 않는다.
PowerStatus InputSequence/InputTime은 **실제 physical acquisition**의 batch/oldest dependency다.
BMS gate freshness는 로컬에서 검사하며 Central은 이후 PowerLimits/PowerStatus를 함께 검증해야 한다.
Wire/DBC 변경은 없다. 실제 Central/Zone/session protocol은 후속이다.

## 정상 sequence와 protection

OFF→CHECKS→PRECHARGE→HV_READY→SHUTDOWN→OFF를 사용하되 내부 phase를 세분한다.
Negative close→실제 negative 확인→precharge close→버스 ratio/delta의 fresh dwell→positive close→
실제 positive 확인→precharge open→실제 precharge open을 확인해야 READY다.
시간만으로 준비 완료를 선언하지 않는다. LV/interlock/isolation/charger/power-fault의 unknown은 정상과 다르다.
Common LocalState는 controller 초기 검사/health이고 PowerState와 별개다. 검사 통과 뒤 PRECHARGE나
정상 종료한 OFF에서도 LocalState=NORMAL일 수 있다. HV_READY는 차량 NORMAL/Drive 허가가 아니다.

종료는 즉시 drive inhibit request→전류 magnitude가 낮은 fresh acquisition의 dwell→접점 open
요청→실제 세 접점 open 확인→bus discharge→잔류 전압 확인 순이다. 회생의 음수 전류도 magnitude로
검사한다. Current unknown/high/timeout은 0으로 바꾸지 않는다. 종료 timeout은 blocked/latch이며
강제 개방 권한이 아니다. Weld/stuck feedback이나 고전압 잔류에는 OFF를 보고하지 않는다.
Fault 후 Enable/new frame/정상 센서로 자동 재시작하지 않는다. 새 trusted Epoch/INIT가 필요하다.

이번 fault fixture는 request loss/expiry, BMS inhibit, 조건 불충족, sensor/deadline/continuity,
응답/프리차지 timeout에 **controlled shutdown**을 요청한다. 모든 실차 고장의 보편적 반응이 아니다.
심각한 단락/열/절연 고장의 즉시 차단·pyrofuse 등은 별도 fault matrix와 hardware protection 분석 대상이다.
LV loss는 모델 코일의 실제 deenergization을 일으킬 수 있어 software hold로 막는다고 주장하지 않는다.
Actual feedback이 없으면 추가 coil write를 생성하지 않는다. 기존 driver/watchdog 정책은 미구현이며
불명 상태에서 물리 회로가 안전하게 정지했다고 선언하지 않는다.

## 물리 근사와 시간

Positive main과 precharge 저항 branch를 병렬로, negative main을 공통 return으로 둔다.
DC-link capacitor와 명시적 switched discharge resistor, 실제 signed DC load current를 계산한다.
접점 event 전후를 나눠 `C dV/dt = Gpack(Vpack−V) − Gdischarge V − Iload`의 constant-input 해석해를
적분한다. Begin의 명령을 전체 과거 interval에 소급하지 않는다. Opening/closing delay는 20 ms다.
실제 전력의 누락을 zero load로 추정하지 않으며 불가능한 전압은 clip하지 않고 step을 거부한다.

RC precharge/ratio/timeout 원리는
[MathWorks 공식 모델 설명](https://www.mathworks.com/help/stateflow/ug/learn-how-to-model-battery-management-system.html)을 참고한다.
[TI DC-link precharge 예](https://www.ti.com/tool/TIDA-050063)는 active topology도 제시한다.
이번 passive-R functional fixture가 그 제품 회로나 calibration을 복제한 것은 아니다.

Fixture는 C 2 mF, precharge 50 Ω, main equivalent link 0.02 Ω, discharge 100 Ω다.
모델 voltage/load 표현 상한은 1000 V/±500 A다. Controller pack 300..450 V,
precharge ratio ≥0.99와 |Vpack−Vbus|≤5 V를 20 ms 확인한다. OFF 잔류 기준 30 V,
opening |I|≤5 A/20 ms다. 이 값은 부품 정격·안전 전압·실차 calibration의 채택이 아니다.
Checks 500 ms, contactor 100 ms, precharge 2 s, current wait 300 ms, discharge 1 s의 timeout을 쓴다.
Controller period 10 ms/max gap 30 ms, physical source age 50 ms/dependency 70 ms다.

Physical port는 하나의 atomic acquisition이고 내부 optional의 unknown을 보존한다.
Hold는 전체 identity/time/value를 유지한다. Cached observation을 반복 읽어 dwell을 채우지 않는다.
Time gap/clock/invalid physical interval은 plant를 latch/unavailable로 하고 backfill하지 않는다.
Controller clock rollback은 publication/coil write를 중단한다. Deadline은 controlled shutdown을 latch한다.

Application INIT와 physical scenario reset을 분리한다. 재시작은 코일 초기화나 bus voltage reset을
수행하지 않는다. 첫 fresh feedback에 접점이 닫혀 있으면 StartupEnergized를 latch하고 inhibit/
controlled shutdown한다. 물리 OFF 이후 새 Epoch로 다시 검사해야 한다.

## 검증과 다음 단계

[학습·실행](../learning/m2_power_lifecycle.md), [37개 component 시험](../../tests/unit/power_lifecycle_test.cpp),
기존 BMS 시험에 추가한 local gate 1개를 포함해 normal·ASan/UBSan 전체 unit은 293개다.
RC 해석해/접점 지연/부하와 회생 부호, LV·weld/stuck·부분 관측·cached dwell, 정상/blocked 종료,
trusted parent/expiry/restart/deadline/codec·receiver를 검사한다. 기존 CLI의 `power-model` 네 scenario는
실제 BmsController gate→PowerController→PowerModel→PowerStatus/P05→receiver를 연결한다.
새 transport executable이나 vCAN case를 추가하지 않았다. 이전 97개 vCAN 증거는 별도 이력이다.

Demo의 400 V/SOC 0.5/온도와 cell spread는 명시적 fixture이며 전류·bus·접점은 power plant의 actual이다.
Actual load도 별도 fixture다. BatteryModel SOC/energy를 동시에 실행하거나 DC-link 충방전 에너지를
pack capacity에서 적분하지 않는다. **차량·배터리 에너지 통합의 PASS가 아니다.** M6에서 단일
battery energy owner와 capacitor/path losses/actual inverter power의 일관된 coupling이 필요하다.
Arc/bounce, resistor 정격/발열, LV 회로, 절연/HVIL 물리 검출, pyrofuse와 hardware watchdog은 미구현이다.
다음은 actual speed·BMS limits·Central permission·Drive 자체 HV feedback을 묶는 Drive local gate/capability다.
