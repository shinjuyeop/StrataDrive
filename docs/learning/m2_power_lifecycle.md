# M2 Power lifecycle: 프리차지와 컨택터 실제 응답

Date: 2026-10-15. Status: **Host functional SIL component 구현·시험 / 직접 재현·이해 review PENDING**.
[ADR-0026](../adr/ADR-0026-first-power-lifecycle.md)의 전원 제어기와 물리 모델이다.

## 전원을 켠다는 것

배터리 전압이 있다는 것과 모터 inverter에 전원을 연결할 준비가 끝났다는 것은 다르다.
**컨택터(contactor)**는 큰 전력을 연결/분리하는 스위치이며, 코일 요청과 실제 접점 상태가 다를 수 있다.
Inverter 입력에는 **DC-link capacitor**가 있어 전원이 끊겨도 전압이 남을 수 있다.

방전된 capacitor에 배터리를 바로 연결하면 전압 차이/경로 저항에 따라 큰 돌입 전류가 흐른다.
**Precharge**는 먼저 저항을 거쳐 capacitor 전압을 올린 후 main 접점을 닫는 절차다.
원리와 RC 식은 [MathWorks 공식 학습 예제](https://www.mathworks.com/help/stateflow/ug/learn-how-to-model-battery-management-system.html)를 참고한다.
현재는 passive resistor 모델을 쓴다. 실제 다른 구현 예로는
[TI active DC-link precharge](https://www.ti.com/tool/TIDA-050063)가 있다.

```text
Pack + ──┬── Main positive ─────────┬── Bus +
         └── Precharge ── Rpre ─────┘     │
                                    C / inverter load /
                                    switched discharge R
Pack − ───── Main negative ──────────── Bus −
```

Discharge resistor는 bus +/− 사이의 별도 방전 경로다. Cell balancing용 저항과 구분한다.
배터리 내부저항, precharge 저항, main link 저항도 서로 다른 parameter다.

## 코드가 나누어 맡는 일

| 위치 | 책임 |
| --- | --- |
| [PowerController](../../vecu/bms/power_controller.hpp) / [구현](../../vecu/bms/power_controller.cpp) | 요청/센서/BMS gate 검사, lifecycle 결정, 코일 요청·inhibit·status 생성 |
| [PowerModel](../../simulation/power/power_model.hpp) / [구현](../../simulation/power/power_model.cpp) | 코일 지연·실제 접점, DC-link 전압/전류, weld/stuck/관측 상실 |
| [로컬 port](../../interfaces/bms/power_sensor_snapshot.hpp) | 물리 acquisition과 BMS safety gate의 identity/원천 시각/unknown 계약 |
| 기존 PowerRequest/PowerStatus CAN | 상위 요청과 실제 status; P05/receiver/trusted parent 재사용 |

PowerController는 BMS leaf의 일부다. 별도 상위 VCU를 추가하지 않는다.
[BMS 판단](m2_bms_controller.md)은 원래 decision identity와 source/dependency를 가진 로컬
`BmsSafetyGate`를 제공한다. 이것은 같은 ECU 내부 연결이며 BMS→Drive 직접 CAN 우회가 아니다.
Central→담당 Zone→BMS 요청과 BMS→Zone→Central 상위 status 경로는 유지한다.

## 켜지는 순서

| Lifecycle | 실제 확인과 출력 |
| --- | --- |
| OFF | 접점 모두 open, bus 잔류 전압이 fixture 기준 이하; Enable 전까지 구동 금지 |
| CHECKS | trusted Enable·expiry, fresh sensors/BMS gate, LV/interlock/isolation/충전 연결·fault 확인 |
| PRECHARGE | negative close 확인 → precharge close → bus 전압 확인 → positive close 확인 → precharge open 확인 |
| HV_READY | main +/− 실제 closed, precharge open, bus/pack 전압 정합과 필요한 fresh 조건 모두 만족 |

Precharge 진행 중에는 main positive를 바로 닫지 않는다. 이번 fixture에서는 bus가 pack의
99% 이상이고 전압 차이가 5 V 이하인 fresh sample이 20 ms 유지돼야 positive close를 요청한다.
요청 뒤에도 실제 positive close와 precharge open feedback을 기다린다. Timeout은 성공 판정이 아니다.

**HV_READY는 실제 전원 준비 상태**다. 차량 NORMAL이나 DrivePermission과 다르다.
Common LocalState는 controller 초기 검사/health다. 검사 후 PRECHARGE·정상 종료 OFF에서도
LocalState=NORMAL일 수 있으며 이 값만 보고 torque를 허용하면 안 된다.

## 꺼지는 순서

```text
Drive inhibit 요청
  → 실제 전류 magnitude가 충분히 낮은지 확인
  → Main/Precharge open 요청
  → 실제 모든 접점 open 확인
  → Bus discharge 요청
  → 실제 잔류 전압 확인 후 OFF
```

Shutdown 요청이 들어와도 실제 전류가 즉시 줄어드는 것은 아니다.
이번에는 `|Ipack| ≤ 5 A`의 fresh sample 20 ms를 기다린다. 회생 중의 음수 전류도 magnitude로 본다.
전류가 계속 20 A이거나 current sensor가 unknown이면 접점을 열어도 된다고 판단하지 않는다.
300 ms가 지나면 `shutdown_blocked`와 fault를 남긴다. 이 timeout이 강제 개방 허가는 아니다.
나중에 실제 전류가 내려가면 안전 조건을 재확인하며 종료는 계속할 수 있지만 fault latch는 남는다.

Open을 요청했어도 접점이 붙어 있으면 아직 열린 것이 아니다. **Welded/stuck-closed**는 이 차이를
시험한다. 실제 open feedback 이후에만 discharge를 켠다. 잔류 전압이 30 V 이하가 돼야 OFF다.
Current/contactor/discharge timeout 때 OFF로 값을 바꾸어 정상화하지 않는다.

이것은 선택한 component fault에 대한 controlled-shutdown fixture다. 실차의 심각한 단락/열/절연
고장에 필요한 emergency disconnect/pyrofuse 반응을 이 순서 하나로 대체하지 않는다.
LV 상실 시 실제 코일이 떨어질 수 있고, 알 수 없는 피드백에는 새 coil write를 만들지 않는다.
Hardware driver/watchdog·정격/arc·고장별 차단 policy는 후속이다.

## 전압은 어떻게 계산하나

접점이 고정된 각 구간에서 다음 미분방정식의 constant-input 해석해를 사용한다.

```text
C × dVbus/dt = Gpack × (Vpack − Vbus) − Gdischarge × Vbus − Iload
Gpack = main/precharge의 실제 연결된 병렬 conductance (negative open이면 0)
```

Load/discharge 없이 precharge만 연결하면 `Vbus = Vpack × (1 − exp(−t/(Rpre×C)))`다.
Fixture의 `Rpre=50 Ω`, `C=0.002 F`이므로 시정수 τ는 100 ms다. 100 ms 후 약 63.2%,
약 460 ms 후 99%에 도달한다. BMS 초기 검사·접점 지연·dwell은 별도로 더해진다.
코일 요청이 interval begin에 적용되며 20 ms 뒤의 실제 접점 event 전후를 나누어 적분한다.
끝 시각에 닫힌 접점을 과거 interval 전체에 적용하지 않는다.

| 항목 | SIL 시험 설정 |
| --- | --- |
| Pack fixture / capacitor | 400 V / 2 mF |
| Rpre / main equivalent path / discharge | 50 Ω / 0.02 Ω / 100 Ω |
| Contactor response | close/open 각각 20 ms |
| Controller period / max gap | 10 / 30 ms |
| Source / dependency age | 50 / 70 ms |
| Pack 허용 범위 / OFF 잔류 기준 | 300..450 V / 30 V |
| Checks / contactor / precharge timeout | 500 / 100 / 2000 ms |
| Current wait / discharge timeout | 300 / 1000 ms |

모든 값은 시험 parameter다. 부품 정격·실차 calibration이나 법규/안전 전압 기준의 채택이 아니다.
전류는 actual bus load 입력으로 양수 소비/음수 반환이다. 부하가 capacitor를 음의 전압으로 만드는 등
이 모델에서 불가능한 입력은 step을 거부하고 관측을 unavailable로 만든다. Zero로 clip하지 않는다.

## 원천 시각과 재시작

Power sensor port는 하나의 atomic acquisition이며 pack/bus/current/contactors/conditions는 각각
unknown일 수 있다. Hold는 **전체 acquisition**의 source/batch/dependency/value를 보존한다.
오래된 sample 반복으로 precharge/current dwell을 채우지 않는다. Invalid bus라도 알려진 contactor
feedback을 wire에서 없애거나 closed 요청으로 대체하지 않는다. Stale/identity 오류는 current actual로 쓰지 않는다.

PowerStatus CausalSequence는 수용한 **Central PowerRequest의 Sequence**다. 그 요청의 upstream
parent sequence, model InputSequence와 다르다. InputTimeNs는 physical acquisition의 가장 오래된
원천 시각이다. BMS gate도 별도 freshness 검사를 통과해야 하며 나중에 Central은 limits/status를 함께 본다.

Application Epoch와 physical scenario Epoch를 분리한다. BMS/Power 재시작이 capacitor 전압이나
battery SOC를 초기화해서는 안 된다. 새 session은 첫 fresh 실제 접점이 닫혀 있으면
StartupEnergized fault/inhibit와 controlled shutdown으로 재확인한다. Fault/new Enable만으로 자동 복구하지 않는다.

## 실행과 읽을 로그

```sh
cmake -S . -B build/m1-angle
cmake --build build/m1-angle -j 4
ctest --test-dir build/m1-angle --output-on-failure
build/m1-angle/actuator_demo power-model normal
build/m1-angle/actuator_demo power-model bms-trip
build/m1-angle/actuator_demo power-model weld
build/m1-angle/actuator_demo power-model blocked
```

기존 CLI를 확장했다. 3초 수동 시계를 실행하며 실제 socket/HV hardware를 작동하지 않는다.
SOC 0.5/온도·cell spread와 pack 400 V는 알려진 fixture다. BMS에는 실제 PowerModel의
pack current/voltage와 이 fixture 센서를 전달한다. 정상 부하 20 A도 명시적 actual-load fixture이며
inhibit 요청 자체로 즉시 0 A가 되지 않는다. Normal은 1.2 s에 load가 내려가는 상황을 주입한다.

| 예제 | 확인할 결과 |
| --- | --- |
| normal | 약 700 ms READY, 1010 ms current wait, 전류 하강→접점 open→잔류 전압 하강 후 OFF |
| bms-trip | 1 s 이후 cell 60 °C 주입을 BmsController가 판단; 정상 Enable 중에도 로컬 inhibit/종료·fault 유지 |
| weld | positive 접점이 open 요청 뒤에도 closed; OPEN_CONTACTORS/blocked, OFF/READY 아님 |
| blocked | 실제 전류 20 A 유지; WAIT_CURRENT/blocked, main 접점 유지 |

`rx_ready`는 기존 PowerStatus/P05/receiver의 물리 readiness 판정이다. DrivePermission을 만들지 않는다.
시험은 [Power 37개](../../tests/unit/power_lifecycle_test.cpp)와 BMS local gate 1개를 추가했다.
Power 단계 시점 normal·ASan/UBSan 전체 unit 293개, 네 demo와 정적 분석/production build·문서 검사를
[품질 기록](../quality_policy.md)에 구분해 기록한다. Transport/vCAN case는 추가하지 않았고 이전 97개 증거를 유지한다.

현재는 DC-link 응답과 lifecycle component다. BatteryModel SOC 에너지와 이 RC load를 이중 적분하지 않는다.
[Drive local gate/capability](m2_drive_gate.md)도 후속 component로 구현·시험했다. 실제 speed와 BMS 한계,
Central permission, Drive 자체 HV 관측을 함께 검사해 목표를 제한하고 실제 응답을 별도로 보고한다.
[첫 actual DC/SOC 연결](m2_drive_energy.md)은 이상적 energized HV 경로로 구현·시험했다.
[후속 EvPowerModel](m2_ev_power_circuit.md)은 PowerModel의 dynamic capacitor/path 손실·구간 전류/발열과
BatteryModel의 단일 chemical energy owner를 연결했다. 이 문서의 `power-model` 예제는 계속 독립 fixture다.
다음은 M2 수용 검토와 M3 timing 준비이며 차량 motion 통합은 M6이다. Full vehicle TC는 NOT RUN이다.
