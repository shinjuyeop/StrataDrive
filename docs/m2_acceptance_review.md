# M2 수용 검토: 응답 모델과 EV 전원·에너지

Review ID: **M2-REV-20261016** / Date: **2026-10-16**.
Status: **기존 component 기능 검사 PASS / M2 미완료 항목 OPEN / 학습자 직접 재현·이해 검토 PENDING**.
수행: Codex의 코드·설정·시험 증거 대조. M2 상태는 **IN PROGRESS**로 유지한다.

후속 2026-10-16: [Steering response monitor](learning/m2_steering_fault_monitor.md)를 구현·시험했다.
OPEN-M2-01은 **Host component 구현·검사 완료 / 학습자 수용 PENDING**이며 Brake OPEN-M2-02는 미구현이다.
전체 unit은 430개다. 아래 최초 검토의 391개 결과와 미구현 판정은 이후 `69a9614`로 커밋한 당시 snapshot의 이력이다.
최신 실행 증거와 수치는 위 학습 안내/품질 기록에 따로 연결한다.

## 검토 범위와 판정

수용 검토는 구현한 기능, 약속한 기능, 시험한 범위를 대조하는 작업이다.
이 기록의 PASS는 아래 명시한 Host component 기능에만 적용한다.
전체 requirement를 VERIFIED로 바꾸거나 차량 TC의 NOT RUN을 변경하지 않는다.
기존 [학습 절차](learning/README.md)와 [품질 정책](quality_policy.md)을 적용한다.

최초 검토에서 확인한 결과는 다음과 같다.

- Steering/Brake/Drive 응답, Battery/BMS/Power, Drive gate, 실제 회로·에너지 연결은 기존 기능 시험을 재통과했다.
- 주기는 외부 caller가 실행하는 논리 계약이다. `tick()`이 다시 호출될 때 gap을 검출하는 것과
  멈춘 task를 독립적으로 감시하는 것은 다르다. 실제 scheduler/watchdog·부하 측정은 M3에 남는다.
- **당시 Steering jam/tracking 및 Brake stuck/slow-response 검출은 미구현이었다.**
  [fault architecture](architecture/fault_diagnostics_architecture.md#detection-ownership)가 M2 검증 대상으로 둔 항목이므로
  통신 timeout 시험으로 대체하지 않고 M2 미완료로 남긴다.
- 설정값은 단위·부호·C++ fixture와 YAML 기록을 대조했다. 실차 calibration 채택이나 학습자 수용을 뜻하지 않는다.
- Central request/grant·relay·wheel speed는 fixture다. 실제 Central/Zone/DDS와 차량 운동·회생/마찰 배분은 후속 범위다.

## 주기·입출력·감시 경계

아래 시간은 ms다. `max gap`은 마지막 논리 실행과의 간격에 대한 guard이며 OS job deadline이 아니다.
Source/dependency age는 `>`에서 만료하고 receiver timeout은 `>=`에서 latch한다.
각 API의 clock 역행은 출력 중단/무효를 드러내며 실제 물리 상태를 과거로 돌리지 않는다.

| 모듈 / 코드 | 실행·입력 시간 | 입력 → 출력 | 상실·실행 누락 반응 |
| --- | --- | --- | --- |
| [SteeringActuator](../vecu/steering/steering_actuator.cpp) | tick 10 / max gap 30; command source 30, RX 80 | 검증된 Command → delay/rate/angle 제한 → Actual/P05 | pending 취소, 현재 angle hold, FAIL_SAFE latch; 누락 구간 catch-up 없음 |
| [BrakeActuator](../vecu/brake/brake_actuator.cpp) | tick 10 / max gap 30; command source 30, RX 80 | 검증된 압력 Command → delay/rise/fall 제한 → Actual/P05 | pending 취소, 최초 fault의 max(actual, floor)로 유한 ramp; gap interval은 hold |
| [DriveActuator](../vecu/drive/drive_actuator.cpp) | tick 10 / max gap 30; command source 30, RX 80 | signed Command → 별도 TorqueResponse → Actual/P05 | 양·음수 목표 취소, zero target/ramp/latch; speed/capability와 EV gate 없는 isolated fixture |
| [DriveController](../vecu/drive/drive_controller.cpp) | tick 10 / max gap 30; command 30/RX 80, limits·grant 50/70/RX 80, local age 30/skew 20 | Command + routed limits + trusted grant + local speed/HV → 제한 목표·capability·Actual | 활성화 뒤 입력/허가 상실 latch, zero target/유한 residual; gap interval backfill 없음 |
| [BmsController](../vecu/bms/bms_controller.cpp) | tick 20 / max gap 40; sensor source 50/dependency 70/skew 20 | 독립 local sensor group → 방향별 PowerLimits + local safety gate | active 중 무효 입력 latch/unknown; 보호 pending 즉시 inhibit, fresh acquisition dwell 뒤 확정 |
| [PowerController](../vecu/bms/power_controller.cpp) | tick 10 / max gap 30; sensor·gate 50/70, request RX 80/원래 expiry | actual sensor + BMS gate + trusted request → coil 요청·PowerStatus | inhibit 후 actual current dwell→접점 open→bus 방전; current unknown/high에서 강제 open하지 않음 |
| [BatteryModel](../simulation/battery/battery_model.cpp) | standalone demo step 20 / max step 40; oldest input age 50 | actual DC power 또는 회로 current 적분 → 단일 chemical energy/SOC·heat·sensor port | gap/무효/capacity 초과 latch, 0 대입·clip·나중 backfill 없음 |
| [PowerModel](../simulation/power/power_model.cpp) | demo step 10 / max step 20; input age 50 | begin coil·전기 입력 → 지연 접점·RC bus·sensor port | 입력/전기적 불가능성은 fault; 접점 event 시각으로 구간 분할 |
| [DriveEnergyModel](../simulation/drive/drive_energy_model.cpp) / [EvPowerModel](../simulation/power/ev_power_model.cpp) | demo step 10 / max step 20; end 기준 age 30/skew 10 | begin actual torque/speed·부하 → motor DC·손실·Battery; 후자는 실제 RC/접점 포함 | 구간 공백/old dependency/잘못된 identity를 거부; combined 모델은 Battery·회로·장부를 함께 commit |

Freshness는 처리 시각을 새로 붙여 연장하지 않는다. 초기 연결 획득/유효 0/unknown은 모듈별 의미가 다르다.
Steering/Brake의 수용 명령 없는 startup timeout은 unavailable 진단 Actual을 내고,
Drive는 fresh zero/Inhibit/known HV OFF일 때 non-driving INIT를 유지할 수 있다.
BMS의 missing startup sensors는 INIT/unknown으로 남으며 fresh release dwell을 완료하지 못한다.
Power는 확인 전 coil을 쓰지 않고 Inspect에서 실제 접점과 bus를 검사한다.

현재 caller와 component는 single owner다. [SocketCAN fixture](learning/m1_session_queue.md)의
application FIFO 32 / cycle당 ingress·dispatch 8과 물리 delay FIFO 128은 서로 다른 용도다.
모든 함수 호출에 queue를 붙이는 구조가 아니다. Thread 분리 시 snapshot 동기화·queue ownership·overflow 반응을
M3에서 설계하고, 전체 통신 task 정지 중 감시의 독립성을 따로 시험해야 한다.

Combined EV loop는 이전 tick의 actual/coil로 `[begin,end]` 물리를 계산하고 end sensor를 취득한 뒤
BMS/Power/Drive를 호출한다. 새 제어 출력은 다음 구간에 적용한다. BMS 실행 간격은 20 ms다.
Battery 물리는 이 loop에서 10 ms마다 진행하므로 BMS 발행 주기와 같다고 가정하지 않는다.
50 µs electrical substep은 solver 설정이며 ECU task period가 아니다.

## 설정값 대조와 적용 한계

원본은 [reference.yaml](../profiles/reference.yaml)의 `m2_*_fixture` 기록과 각 C++ config/demo다.
YAML loader는 없으므로 이 파일을 수정해도 실행 설정이 자동 변경되지 않는다.

| 대상 | 이번에 대조한 fixture | 판정 / 남은 검증 |
| --- | --- | --- |
| Steering | command ±0.5 rad, actual ±0.3 rad, 1 rad/s, delay 50 ms | 단위/range·거부와 포화 구분 일치; 정상 delay/rate를 고려한 jam detector는 OPEN |
| Brake | command 0..2 MPa, actual 0..1.5 MPa, rise/fall 5/10 MPa/s, delay 50 ms, fault floor 1 MPa | 압력 의미/0 해제·floor 정책 일치; 차량 정지·pressure→wheel torque calibration 및 response detector 미검증 |
| Drive | command −300..500 N·m, actual −200..300, normal/protection 1000/2000 N·m/s, delay 50 ms | gate와 isolated fixture 구분; BMS 한계 축소 시 목표를 제한해도 actual residual은 유한 시간 존재 |
| Drive envelope | forward speed ≤100 rad/s, regen taper 2..5 rad/s, propulsion/regen mechanical 20/10 kW | zero/low speed·방향별 제한 시험; 실제 motor map/차량 속도 매핑은 후속 |
| Battery/BMS | 50 kWh, constant OCV 400 V, Rint 0.05 Ω, SOC charge zero/full 0.95/0.80, discharge 0.05/0.10 | energy/SOC·센서 극값·derating/dwell 시험; chemistry·SOC 추정기·제조사 threshold 검증은 아님 |
| Power | C 2 mF, precharge/main/bleed 50/0.02/100 Ω, 접점 지연 20 ms, OFF bus ≤30 V | actual 전압/접점 기반 sequence·blocked 시험; 실제 접점 차단 능력/전압 안전 기준의 채택은 아님 |
| Combined 전용 설정 | opening current 0.5 A, Drive reserve 500 W, pack-side auxiliary 0.375 A | standalone 5 A / reserve 200 W와 의도적으로 다름; nominal steady 손실 예산이며 transient hard power 보장 아님 |
| 수치 장부 오차 | Battery 0.00018 J / ideal energy 0.00036 J / combined 0.00072 J | capacity에 비례한 numerical conservation tolerance; 실차 모델 정확도나 안전 여유와 다른 값 |

TBD-02/03/12/13/14는 이 fixture의 시험만으로 닫지 않는다.
고정 외부 speed에서 회생을 계속할 기계 에너지원은 fixture 경계 밖이다.
차량 운동 에너지와의 수지·마찰제동·저속 hold는 M4/M6/M7에서 연결한다.

## 고장·세션 검토표

아래 PASS는 관련 component unit와 명시한 demo 범위다. 상세 case는 연결한 test source에 있다.

| 수용 항목 | 실행 증거 | 검토 |
| --- | --- | --- |
| 정상 delay/rate/saturation, repeated demand가 delay를 미루지 않음, Actual≠echo | [Steering 13개](../tests/unit/steering_actuator_test.cpp), [Brake 16개](../tests/unit/brake_actuator_test.cpp), [TorqueResponse/isolated Drive 24개](../tests/unit/drive_actuator_test.cpp) | PASS |
| source expiry·CRC reject·continuity·gap에서 pending 취소/보호, late fresh 입력으로 복구하지 않음 | 위 actuator 시험, [Drive gate 37개](../tests/unit/drive_controller_test.cpp), model vCAN 8개 | PASS; task 자체 중단의 독립 검출은 M3 |
| 충전/방전 유효 0와 unknown 구분, cached acquisition·skew·old dependency 거부 | [BMS 34개](../tests/unit/bms_controller_test.cpp), Drive gate 시험 | PASS |
| READY와 주행 허가 구분, trusted parent 없으면 허가하지 않음, local HV 독립 확인 | Drive gate 및 [Power 37개](../tests/unit/power_lifecycle_test.cpp) | PASS; Central/Zone는 fixture |
| 부하 전류·unknown에서 종료 차단, 접점 용착/응답 실패·잔류 전압 확인 | Power 시험 + `ev-power` 네 scenario | PASS; OFF 성공과 shutdown blocked를 구분 |
| actual torque 기반 구동·충전, auxiliary/loss·capacitor 소유, atomic failure와 장시간 수지 | [Battery 35개](../tests/unit/battery_model_test.cpp), [ideal energy 28개](../tests/unit/drive_energy_model_test.cpp), [circuit 24개](../tests/unit/ev_power_model_test.cpp) | PASS |
| 새 application epoch에서 old input/pending 폐기, 물리 angle/pressure/torque·battery scenario 보존 | actuator/Drive gate/BMS/Power unit; explicit physical reset 시험 | PASS; 배포 환경의 trusted INIT/rejoin은 M4/M5 |
| fresh 통신 중 Steering jam, Brake stuck/slow response를 local detector가 구분 | 현재 독립 sensor/고장 모델과 residual/dwell detector 없음 | **OPEN-M2-01/02** |

Combined normal 종료의 `drive_fault=4`는 활성화 뒤 Inhibit를 latch하는 현재 정책이다.
`phase=OFF, power_fault=0, blocked=0`인 전원 종료 성공과 모순되지 않는다.
재구동에는 trusted INIT/새 application epoch와 모든 입력의 재검증이 필요하다.
Normal OFF 뒤에도 pack-side auxiliary는 소비하므로 SOC가 정지한다고 가정하지 않는다.

## 이번 실행 증거와 추적성

검사 대상은 기존 미커밋 구현을 포함한 working tree다. HEAD만으로 이 실행을 재현했다고 주장하지 않는다.
실행 source/DBC/profile의 SHA-256과 base commit은 `build/m1-angle/m2-review/evidence.json`에 보존한다.

| 이번 실행 | normal | ASan/UBSan | 기록 경로 |
| --- | --- | --- | --- |
| 기존 build + 전체 unit | 391 PASS | 391 PASS | 각 build의 `m2-review/build.txt`, `unit.txt`, `unit.xml`, `test-inventory.json` |
| model vCAN: Steering 2 / Brake 3 / isolated Drive 3 | 8 PASS | 8 PASS | 각 build의 `m2-review/vcan-model.txt`, `socketcan-results/*-model-*.log` |
| Steering/Brake/isolated Drive/Battery/BMS demo | 5 PASS | 5 PASS | 각 build의 `m2-review/<command>.txt`; 실행 smoke, unit와 별도 |
| combined `normal/weld/current-unknown/aux-blocked` | 4 PASS | 4 PASS | 각 build의 `m2-review/ev-power-<scenario>.txt`; 종료 phase/fault/접점·unknown·에너지 잔차를 별도 assertion으로 확인 |

391개는 기존 M1 143개와 M2 component 248개의 합이다. vCAN 기존 all 97개 이력을 유지하며,
이번에 재실행한 것은 model 8개다. EV gate/combined loop를 SocketCAN에 연결한 새 case는 없다.
새 runtime 코드·시험 모듈·외부 의존성은 추가하지 않았다. 정적 분석/production build의 앞선
[회로 연결 기록](quality_policy.md)은 같은 구현에 대한 이력으로 유지한다.

```sh
cmake --build build/m1-angle -j 4
ctest --test-dir build/m1-angle --output-on-failure
unshare --user --map-root-user --net python3 tests/integration/can/check_socketcan.py --build-dir build/m1-angle --family model
build/m1-angle/actuator_demo ev-power normal
build/m1-angle/actuator_demo ev-power weld
build/m1-angle/actuator_demo ev-power current-unknown
build/m1-angle/actuator_demo ev-power aux-blocked
```

Sanitizer는 `build/m1-angle-sanitized`의 기존 `STRATADRIVE_SANITIZERS=ON` build에서 동일 범위를 실행했다.
Unit/수동 시계 demo의 시간은 논리 시간이며, vCAN의 local monotonic wall-time 결과와 구분한다.
Sanitizer 실행 시간은 대표 성능 수치가 아니다.

[Traceability](test-plan/traceability.md)의 다음 요구에 **부분 증거**를 연결한다.

- SYS-ARCH-002, SYS-COM-002/003/004, SYS-SAFE-002/003/004: Command/Actual 구분, 수신·보호·세션.
- SYS-CTRL-009, SYS-EV-003/005: actual 기반 회생·한계·단일 energy owner.
- SYS-EV-001/002/004: local power readiness, source/dependency/validity, 고장별 local reaction.
- SYS-PERF-002/003: 논리 주기·명시적 clock/gap 처리의 부분 증거. 실제 task/E2E 측정은 후속이다.

32개 system requirement와 29개 system TC의 전체 Result는 모두 **NOT RUN**을 유지한다.
학습자의 wire 채택·설명·직접 실행 기록도 **PENDING**이다.

## 미완료 항목과 다음 작업

| 항목 | 닫기 위해 필요한 것 | 단계 / 담당 |
| --- | --- | --- |
| OPEN-M2-01 Steering response fault | 후속 sensor/물리 경계와 rate-band predictor·residual/dwell·latch, 정상/고장/새 epoch를 구현·시험; [상세 증거](learning/m2_steering_fault_monitor.md) | **M2 component 검사 완료 / 학습자 수용 PENDING** / vECU·model 담당 |
| OPEN-M2-02 Brake response fault | pressure actual/sensor 경계와 stuck/slow-response 주입, 가압·감압·보호 floor를 고려한 판정·반응·재시작 시험 | **M2**, Steering 뒤 / vECU·model 담당 |
| OPEN-M2-03 학습자 수용 | 기존 M1 wire와 M2 정상/고장/복구를 직접 재현하고 설정·로그의 의미를 본인 설명으로 기록 | **M1/M2 PENDING** / project owner |
| M3 준비: 실제 task/monitor | release owner·clock·period와 deadline 구분, RX/monitor/control 배치·bounded queue/snapshot, task 정지 감시 독립성과 gap/overload 처리 | **M3** / runtime·timing 담당 |
| M3 준비: trace와 원인 연결 | run/epoch/clock, release/start/end, raw RX/accept/reject, queue/drop, 보호 검출·동작 시각, 사용 입력과 actual의 identity | **M3** / instrumentation 담당 |
| M3 준비: 측정 protocol | 사전 workload/warmup/duration/repetitions·deadline/budget, Mean/P95/P99/Max와 eligible/missed/dropped jobs, trace overhead | **M3**, TBD-04 / timing 담당 |
| 실제 coordinator·Zone·배분·차량 | fixture 교체, 원천 metadata 보존, 독립 loss/rejoin, pressure/torque mapping과 실제 차량 에너지·정지 검증 | **M4–M7** / architecture·plant 담당 |

Actual.CausalSequence는 현재 마지막 수용 Command 문맥이다. Delay 동안 더 최근 명령으로 바뀔 수 있으므로
그 값만으로 실제 운동을 만든 delayed target이나 command→응답 latency를 확정할 수 없다.
M3 trace는 사용 snapshot/목표 적용 시각을 별도로 연결해야 한다.
통합 demo의 100 ms/상태 변화 콘솔 출력도 모든 10 ms job의 trace를 대신하지 않는다.

**최초 검토의 다음 항목인 Steering local monitor는 후속 구현·시험했다. 현재 다음은 Brake response detector다.**
Brake도 독립 sensor/fault 경계를 정하고 기존 delay/rise/fall·floor 시험을 정상 oracle로 유지한다.
Brake response 검토와 학습자 수용을 건너뛰어 M2를 완료 표시하지 않는다.
M3 계측 설계는 병행 준비할 수 있지만 M2 미완료 항목의 해결 결과와 별도로 기록한다.
