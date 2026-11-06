# M9 simulation10ms sampled Actual

Base `3862ded`. The old whole-next10ms normal-command proof rejects silent
Front packet loss before native time reaches the real timeout. Keep that default
gate and its expected-refusal test. Do not turn refusal into physical-stop evidence.

The optional `--sampled-actual` / `sampled-actual-v1` profile uses the existing
10ms sample/hold physical model explicitly. At each completed physical barrier,
all native owners execute only through that original simulation timestamp, using
original acquired wheel history. Normal commands and their original parent/input
age and expiry must be valid **at that barrier**. Original CAN/P05 Actual, wheel,
capability, BMS permission and RunLease still cover the **whole next10ms**.
No timestamp, command expiry, native watchdog or diagnostic event is changed.
The server applies the decoded measured Actual for one10ms interval, as in the
existing model; the native command is causal evidence, not a new physics command.

A normal command can expire inside that held physical interval. Its original
expiry is retained, even when earlier than interval end; native authority does not
extend to that end. The next barrier must supply the real native result. In
protection, every previous strict condition remains: all8 selected, credits0,
immutable Release, fresh original LocalProtection/FailSafe Actual acquired after
selection, no normal re-entry. Missing/delayed protective Actual still fails.
There is no grace interval for an already-expired normal command at a barrier.

This is an explicit acceptance choice for M9 functional fault-chain verification:
the physical response has10ms sampling resolution. It does not claim continuous
subinterval response, Native4ms/wall timing or Target timing. The default original
prospective gate and wall admission stay unchanged. The new profile is selected
before INIT in the trusted local launch, restricted to simulation STOP30 with
solver work, and agreed by native/client/server. Independent raw-wire audit checks
that declaration, the checked horizon, unmodified original expiry, all physical
sources, real solver effort/work and durable DTC bytes. No alternate profile may
be selected after a failed admission.

The functional rig also drains the original two CommandGateway and three Leaf
expiry diagnostic adapters in the existing released session. Silent loss can be
detected there before Central sees a result timeout; preserve that native SD-2001
instead of requiring or synthesizing a Central DTC. A separate single-owner
observer (producer9) links fresh original torque, pressure and wheel acquisitions
to the first captured native CommandLoss occurrence. It grants no recovery,
clear or actuation. Independent audit joins the full run/producer/sequence and
occurrence, checks original CAN values, and rejects a foreign-producer link.

## Fixed validation before acceptance

- Keep exploratory component failure (expiry-only check) and successful
  current-command proof experiment separately; neither is CARLA evidence.
- Final native admission/functional tests in Debug, ASan+UBSan and TSan;
  current-expiry boundary, stale/missing Actual, CRC, wrong causal parent,
  missing credit and fabricated protection reject. Existing whole-interval and
  wall regression tests stay required. Same silent-loss recipe must fail in the
  old profile and reach original protection+DTC in the sampled profile.
- One new fixed actual CARLA cohort: default nominal1, sampled nominal1,
  sampled silent Front loss2. Each is a fresh owned server, original STOP30
  6000 intervals/6001 native barriers, original35s injection,320 solver substeps,
  full work/energy settlement, durable journal and orderly owned shutdown.
- Independently audit original raw wire/physics/work, event/response/DTC and
  byte-identical native replay. Mutations include wrong profile/horizon/expiry,
  missing original protection, wrong DTC and omitted physical stop.
- Retain every original failure and source/binary/build identity. Do not retry
  unchanged code until green. Builds, sanitizers and CARLA do not overlap native
  service wall cohorts. Acceptance applies only to the declared finite scope.
