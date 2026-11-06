# M9 finite Host and simulation follow-up

Base `3862ded`. Final acceptance: **ACCEPTED in the declared finite scope**.
This bundle closes only the declared finite Host service and simulation10ms
functional fault-chain scope. Native4ms, wall/Target guarantees, continuous
subinterval physical response, unlimited retention and learner review remain
separate. Earlier failures are retained, including the previous
[loaded soak6/7](../m9_remaining/README.md).

## Changes and evidence

The explicit `--sdk-fifo` profile initializes SDK/sender threads at FIFO1 on
existing dedicated CPUs4/5/6. Original Central/Zone owner priorities, OTHER0
auxiliary writers,20ms envelopes,10ms renewal/18ms support, original source times
and Front-before-Rear dependency remain unchanged. No SDK or native service C++
binary changed for this candidate. Independent snapshots check actual policies.
The [prospective protocol](../../sdk-fifo-protocol.md) fixes the seven-case soak
and eighteen-case service matrix before execution.

- Soak **7/7**: baseline500ms; quiet3 and loaded3, each with two60s normal
  Epoch2/3 windows followed by real stop, service and rejoin. Loaded demand is70%
  on CPUs1/2/7, with measured CPU/wall ratios about67.6–68.6% under owner preemption.
  Every case passed native service, ordering, placement and original packet/response
  audits with mutations. All404821 audited accepted requests retained positive
  original expiry margin. Observed maximum roundtrip2.295638ms and minimum
  margin17.704362ms are finite observations, not a universal latency bound.
- Service matrix **18/18**: normal and delayed marker6 successes, plus ACK,
  Actual, StopRequest and Stop ACK loss12 expected service refusals. Those12
  original runtime exits remain1/FAIL. Independent fault audits require actual
  omission/expiry, original protection/DTC and no unauthorized service commit;
  they do not relabel the failed service as successful.
- CARLA **4/4**: fixed default nominal1, sampled nominal1, sampled silent
  Front command loss2, with a fresh owned server per case. See `carla/results.json`,
  per-case work/diagnostic audit logs and replay results. Each accepted case requires
  6000 actual physics intervals and EV settlements,6001 exactly equal native JSON
  observations on replay (also checked as canonical JSON bytes), real30km/h precondition, final body/four-wheel stop and
  orderly server exit130.

The opt-in `sampled-actual-v1` profile makes the existing10ms sample/hold physical
model explicit. Original normal Command/parent/input authority is checked at the
current barrier. Actual, wheel, capability, permission and RunLease still cover
all of the next10ms. A command may expire inside the held physical interval;
its original expiry is preserved in receipts and native watchdogs still fire on
their original schedule. The next barrier needs the real native result. No
already-expired current command, missing protective Actual, credit re-entry or
fabricated protection is admitted. Default whole-interval and wall admission are
unchanged. In both silent-loss traces, the retained original command expiry is
9.999998ms before the held interval end (`min_command_expiry_margin_ns=-9999998`).
That value is not renewed or changed to a positive margin. This is10ms physical
sampling, not subinterval integration. The
[prospective acceptance contract](../../carla-sampled-actual-protocol.md) records
this bounded modeling choice.

Silent packet loss exposed a missing diagnostic composition: the real gateway/
Leaf watchdog can detect CommandLoss before Central. The rig now drains those
original adapters and records their SD-2001; it does not invent a Central fault.
A single-owner observer (producer9) links original fresh torque, pressure and
wheel acquisitions to the first captured CommandLoss root. It grants no control,
Passed or Clear. The audit joins full run/producer/sequence plus occurrence,
verifies original CAN/P05 values and checks journal bytes exactly. First captured
queue order is not claimed to be the earliest global detector.

## Validation and preserved failures

Release, Debug, ASan+UBSan and TSan each passed29 functional and23 admission tests
(**208 total**). The functional test includes ten recipes, preserving strict
silent-loss refusal and adding sampled-loss protection/DTC. Invalid original
sources, expiry-at-current-time, causal parents, CRC, unknown/untrusted roots and
foreign response links reject. Python SDK/service/pilot54 tests including the
four CARLA evidence tests passed; eight unsupported profile combinations reject.
A ninth launcher check rejects a Python environment without `carla` before any
server starts. Changed C++ translation units passed clang-tidy/cppcheck commands;
the UE server build succeeded with existing deprecated API warnings retained.
Exact commands, outcomes, caches, binary hashes and logs are in `acceptance.json`
and `validation.tar.gz`.

Component explorations remain separate: expiry-only admission failed1/1; the
current-command experiment passed1/1 before stronger DTC assertions; those
assertions then exposed the missing native diagnostic source (25/26). The logs
are retained, but original exploratory binary hashes were not captured. Final
source/binary identities and the later successful component profiles are recorded;
the exploratory passes are not physical CARLA evidence.

The first CARLA launcher incorrectly resolved the venv interpreter symlink to
system Python. Its first server failed read-only readiness (`carla` missing) and
needed forced shutdown; a second startup was interrupted, with no final supervisor
report. Neither reached driving, and the two remaining cases were not started.
`carla-launch-failure.tar.gz` retains the original four-case plan, one completed
failure, abort accounting, logs and original runner source. The fixed runner keeps
the venv path and checks its client import before launching. The final four-case
cohort uses a new directory and unchanged physical/fault recipes.

The native cohort controller was paused only between quiet runtimes to finish
component/server builds. No active owner or deadline was paused. Native wall runs
never overlapped builds, sanitizers, CARLA or compression. CARLA began only after
all18 later service runtimes; their offline audits could overlap startup. See
`scheduling-notes.json` inside `validation.tar.gz`.

## Artifacts and reproduction

`sources.json`/`sources.tar.gz` preserve final source and binary identities;
per-run manifests freeze prospective inputs. `sdk-soak-*.tar.gz` and
`sdk-service.tar.gz` retain all native raw packets, journals, traces and process
results. `carla/` retains gzip original traces, durable journals, route, receipts,
server reports/logs, audits and replay outcomes. Trace files use the repository's
Git LFS convention. Archives do not alter original evidence or reclaim journals.

After materializing LFS files, run `sha256sum -c SHA256SUMS` in this directory.
From the repository root, the independent CARLA checks can be repeated with:

```sh
python3 tests/integration/carla/audit_m9_diagnostics.py docs/test-plan/evidence/m9_followup/carla/sampled-silent-1 --mutations
python3 tests/integration/carla/audit_m7_1r_work.py docs/test-plan/evidence/m9_followup/carla/sampled-silent-1 --output /tmp/m9-sampled-work.json
```

Extract native archives into a separate directory and run the four original
`tests/integration/diagnostics/audit_*` readers with `--mutations` against each
`central-rejoin-1`. Recovery, explicit clear, Clock/Power lifecycle and offline
archive/restore retain their earlier [linked evidence](../m9_remaining/README.md);
this bundle does not extend their scope to automatic recovery or unlimited storage.
