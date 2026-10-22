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
