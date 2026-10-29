# M6 vehicle / EV energy boundary

2026-10-22. Revision `vehicle-energy-v1`; first implementation on the existing
Host three-vECU functional SIL. [Prospective protocol](../test-plan/evidence/m6_vehicle_energy/protocol.md)
fixes numerical budgets, cases and observation lengths before execution.

## Ownership and time

`VehicleEvModel` is owned only by the persistent SIL physical process. It composes
`SimpleVehicle` and `EvPowerModel` using copies as candidates. Motion, circuit,
Battery state and the combined ledger commit together after validation. An input,
numerical or model error latches the composition fault; it cannot leave a moved
vehicle paired with an old battery. Rejoining an ECU does not initialize this model.

Inputs are the actual torque, friction pressure and steering angle from the prior
completed actuator interval, plus actual electrical environment/coil outputs.
The model does not consume VehicleRequest, CAN demands, grants or a RunLease.
ECUs keep their single ownership and the existing network/session/protection paths.

All scalar acquisitions preserve model identity, source and oldest dependency.
`IntegratedMotorWork` is a whole-interval result: begin/end, physical model identity,
source=end, oldest dependency and signed mechanical joules. It is not a wheel-speed
acquisition. The original beginning wheel speed remains in `EvPowerInputs` for its
independent validation. The integrated mean speed is used only inside the
motor/inverter energy conversion; no command/sensor source is restamped.
The work dependency includes pressure/steering dependencies affecting distance and
is carried through circuit flow into Battery, even when older than the torque sample.

Legacy `EvPowerModel::step` retains its declared beginning-speed ZOH behavior.
`step_integrated_motion` explicitly validates the new result port. It rejects
wrong interval/model sequence/source, a dependency newer than a used input, stale
motion, nonfinite work, work opposite to the actual torque sign and infeasible mean
wheel speed. The generic Drive receiver defaults remain unchanged.

## Work and energy accounting

SimpleVehicle retains its flat-road, forward-only force equation, geometry and
ZOH actual forces. Distance uses the exact stop crossing for that frozen force.
For each interval: `Wmotor = Tactual * distance / radius`. The same signed work is
used by vehicle inertia and the electrical conversion. Existing efficiency,
copper/inverter idle loss, RC/contact losses, auxiliary current and battery
resistance remain owned by their existing models.

The independent balances are:

```
Δkinetic = Wmotor − Wfriction − Wroad
Welectrical_mechanical = Wmotor
Echemical_draw = Δcapacitor + Δkinetic + Wfriction + Wroad
                 + Emotor_loss + Eohmic + Eauxiliary + Ecircuit_loss
```

Runtime/trace budgets are respectively1e-5J,1e-6J and0.001J. The existing electrical
capacity-based guard also remains active. The offline oracle recomputes all three
from the raw energy columns; an encoded zero residual cannot hide a broken balance.
Scalar energy accumulations are not control feedback and do not issue permissions.

Positive torque/wheel speed consumes mechanical energy. Negative torque with
positive speed removes kinetic energy, but returned pack DC is reduced by motor
losses, RC/contact dynamics and auxiliary load. Received DC alone does not prove
regeneration: initial capacitor exchange can also flow back through the pack branch.
A nominal regen verdict requires actual negative torque/positive speed, mechanical
recovery, received DC and simultaneous actual friction pressure. A net SOC increase
is not required; auxiliary/copper/idle loss may exceed a short recovered interval.

## Receiver configuration correction

The EV architecture already grants capability dependencies70ms, while torque,
wheel speed and capability generation stay30ms. `AsyncCoordinatorPort` and
`AsyncZoneOwner` had inherited DriveReceiver's generic30ms dependency default.
Fresh source capability with a30–70ms-old dependency was therefore removed before
the allocator could use it. Both EV receivers now explicitly select the existing
70ms option. Generic receiver defaults, source30ms,80ms RX timeout, allocator
20ms optional support check and original derived command expiry remain unchanged.
The observed20ms-support hypothesis was rejected by the actual Unavailable branch.

## Test fixture and observability

`--three --simple-vehicle --native-watch --energy-cycle nominal|no-charge` selects
`energy-cycle-v1`. It uses the real session/8 participant ACKs/credit/arm and existing
SOME/IP owner-wire/CAN/P05 paths. Phase inputs live only in the test layer:
actual arm→2s acceleration2m/s²→0.6s coast→1.9s brake−1m/s²/hold→standing hold.
Demand saturation and actual response are retained. NormalStop and measured HV-off
follow the scenario. `no-charge` starts the physical Battery at SOC0.96 so the actual
BMS charge-SOC ramp publishes0W. No capability/feedback is manufactured in Central.

Observation is8s from readiness plus the existing2.5s shutdown tail; rejoined
sessions also need5s from their real new arm.2ms opportunities/4ms deadlines,
20ms envelopes and original authority ages/expiry are unchanged. All active energy
profile owners must quiesce within their declared guard window. CPU/FIFO settings
are the existing three-vECU Host profile. This is a new finite quiet workload,
not a requalification of every prior loaded profile.

Physical `energy.csv` is bounded4000 records, sampled with the existing10ms physical
trace; guards evaluate every actual model step. Central's received feedback and
wire capability/allocator transitions have separate bounded records. Data is dumped
after guarded execution. Longer transport trace storage is explicitly reserved
before execution for the longer scenario; control RX/TX capacities remain8.

Results and failure originals are in [the evidence](../test-plan/evidence/m6_vehicle_energy/README.md).
M7's20Hz external sensor boundary, M8 C++ speed controller/equivalence, Jetson,
OEM calibration and complete vehicle validation are subsequent scopes.

## Physical response contract

M6 Host quiet의 [단일 실행 설정](../../profiles/m6_sil_response_v1.json)과
[실측/실패 원본](../test-plan/evidence/m6_physical_response/README.md)을 따른다.
M6 종료 범위와 TBD 분할은 [종료 검토](../archive/milestone-reviews.md#m6)에 있다.

| 시간/조건 | 적용값 | 실제 근거 |
| --- | --- | --- |
| 마지막 유효 수신→상실 검출 | <=100ms | matching Leaf valid-input/command-expired, 원래 source/expiry |
| 로컬 검출 회차→보호 선택 ACK | <=4ms | owner service 진입~fault 관측 구간/실제 선택 ACK |
| 최초 로컬 목표 선택→양쪽 출력 적용 | <=4ms | 실제 Actuation.issued_time/applied-source/physical step 전후 |
| 최초 로컬 목표 선택→실제 완료 관측 | <=230ms | abs(T)<=1Nm 및 실제 압력>=1MPa 동시 만족 |
| 모델 실행 간격 | <=4ms | 기존 native2ms opportunity/4ms guard와 bounded model samples |

Drive 모델의 −200..+300Nm/zero rate2000Nm/s는 tolerance1Nm까지 각각99.5/149.5ms다.
Brake physical max1.5MPa/초기0.2MPa, 최저0Pa, 보호floor1MPa/rise5MPa/s는200ms 최악이다.
정상50ms 지연은 보호가 pending normal과 함께 취소하며 보호 지연은0이다.
병렬 물리200 + 양쪽 인계4 + 모델4 + 기존 CSV관측10 + 명시 여유12 =230ms.
초기0.2MPa만 고려하면160ms지만 정상 해제 후0Pa도 포함해 산정했다.
보호는 더 높은 압력을 낮추지 않는다. 동작 범위 밖 OEM/Target calibration 보장은 아니다.

Runner/oracle는 JSON을 읽고 plan/result/per-case contract에 저장한다. C++ fixture는
JSON에서 전달받은 완료 threshold만 사용하며 물리 모델/ECU target을 바꾸지 않는다.
compiled model 설정 readback과 JSON이 다르면 FAIL이다. reference.yaml은 loader가 아니다.
활성화는 M6 energy normal/command-loss에 한정하며 M5/다른 profile의 판정을 바꾸지 않는다.

Bounded1024개의 약500us step 기록은 torque/pressure·Epoch·원래 output/issued/applied source를
보존한다. 완료 모델 sample과 연속 crossing 시각을 같게 쓰지 않고 직전 미완료~최초 완료로
bracket한다. 실제 적용은 성공한 physical step의 전후 구간이며 요청 시각으로 소급하지 않는다.
기존10ms CSV의 첫 완료 관측은 따로 보고한다. 누락/비유한/미응답/시한 초과는 FAIL이다.
기존 command/permission expiry·source age·20ms envelope·2ms/4ms watch·queue·CAN/P05·
실제8참여자 Release ACK/RunLease/arm·독립 보호는 변경하지 않는다.
