# Host Central ↔ Front real-owner SOME/IP adapter

Follow-up: [native execution watch](../m5_someip_native_watch/README.md) now connects
the actual owners and records new functional/48-run results, including failures.
This document preserves the earlier767d334 cohort and its then-current boundaries.

2026-10-21. **Conditional adoption for this Host functional SIL profile**;
unrestricted Host/native timing adoption remains pending. Implemented and executed
real session/control/protection/rejoin, not a grant-file pilot. See
[ADR-0061](../../../archive/design-decisions.md#adr-0061) and
[binding/ownership/limits](../../../interfaces/someip-front-adapter.md).
M4 Host native IO/FIFO limited acceptance / whole NOT CLOSED, DDS CLOSED and all
historical DDS FAIL/OPEN records remain unchanged. Rear network/Jetson are NOT RUN.

Started from clean HEAD and fetched origin/main **771cf869e263f41606016c385456834495b0b240**.
Implementation commit **2733d122176f6a6a8d31e57c6ee3ccc8db506a23**. Runtime plans were
written before that commit and correctly retain starting HEAD plus per-file hashes.
[Provenance](provenance.json) verifies that the completed campaign4 C++ source hashes
and all three binaries equal the committed implementation. The final runner-only
fault classification correction is separately tested; raw outcomes are never rewritten.

## Actual integration and fixtures

Central owns actual SessionCoordinator, RunLeaseIssuer, VehicleCoordinator and local
Rear/Drive/BMS/Power/CentralIngress. Front owns FrontZone/Steering/Brake using existing
SessionParticipant, RunLeaseGate, RemoteLeafEndpoint and actual owner logic. All eight
participants produce real Prepare/INIT/Release ACKs; release mask255 is required.
ControlAllocation→owner-wire→TCP→Front owner→existing CAN/P05→Leaf→physical models
and actual Feedback/TxResult→TCP→Central validators are connected. TxResult means
processing/CAN admission; physical achievement is checked separately through model IO.

The one persistent physical-model sidecar uses existing SteeringResponse,
BrakePressureResponse, DriveSilPlant and EvPowerModel. Its tmpfs sensor/actuation bus
is an explicit SIL IO fixture with unique writers, not a second control/session path.
Model state survives ECU restart. Fixed trusted Enable and accel0.2/curvature0.02
are scenario inputs; no fabricated normal Actual/health or Release ACK is used.
No chassis/CARLA, real CAN device or native Host IO is claimed.

Central's durable EpochStore issues1, then2 after explicit trusted local rejoin.
In restart-live, Central process and SDK application survive Front SIGKILL; old owner
graph is quiesced before replacement, all eight participants rejoin and old unchanged
packet bytes are rejected. The local operator request is a rejoin trigger, not a grant.

## Reproducible conditions

| Layer | Recorded condition |
| --- | --- |
| SDK | Official COVESA vSomeIP3.7.6, `4187431d2815bd351845a09d01aa85b2a3163cab`, unchanged default source |
| Dependencies | Boost1.85.0 archive SHA256 in provenance; filesystem/atomic built per instrumentation profile |
| Build | GCC11.4, CMake4.3.2, RelWithDebInfo; effective final `-O2 -g -DNDEBUG`; adapter C++20, shared product C++17; exact commands/cache preserved |
| Host | Ubuntu22.04.5, Linux6.8.0-138 PREEMPT_DYNAMIC, i7-11700 8physical/16SMT |
| Placement | CentralCPU1, FrontCPU2, plantCPU3; OTHER/0 inherited by SDK threads and checked in per-case runtime snapshots; SMT siblings9/10/11 not isolated |
| Scheduler | Central20ms allocation, existing10/20ms owner grids, local poll200µs, model500µs; no deadline extension or FIFO blanket setting |
| Queues | Ordinary/authority separate8-entry queues; SDK8192 bytes; payload512 remote/1024 local; nPDU aggregation times0 |
| Network | netns/veth10.88.0.1/30↔10.88.0.2/30; separate mount namespace `/tmp`/`/dev/shm`; TCP30501–30504, SD multicastUDP30490 |
| Readiness | Availability + both-direction nonce probes on both lanes,3s cap; never session authority |
| Observation | Bounded65536 transport records, one-shot transition markers, bounded40000 plant timing records, no per-message flush; overflow fails |
| Case budget |20s supervisor; fixed cases/repeats in [prospective protocol](protocol.md); no repeated run without recorded correction |

Packet reassembly in [analyze.py](analyze.py) observes all four TCP services. One
normal sample contains51 Front command packets,51 reverse results,387 reverse
Actual/health packets, actual Session ACK traffic and384 RunLease packets. PCAP,
`ss`, interface counters, `/proc` thread affinity/policy and loaded-library maps are
in each case. SDK local IPC cannot be the inter-ECU transport in these mount/netns.
User namespaces provide scoped test capabilities; no Host sudo/security changes.

ASan/UBSan and TSan compile the adapter, linked project code, all SDK shared libraries
(core/cfg/sd/e2e) and compiled Boost filesystem/atomic. Compile databases, dynamic
symbols and runtime maps are preserved. libc/libstdc++/loader/kernel remain system
components. TSan uses process-local `setarch x86_64 -R`, retains upstream compile
`-Wno-tsan`/atomic-fence modelling limitations and has **no runtime suppression**.
No SDK-wide safety claim follows. Deliberately killed processes have incomplete
shutdown/leak coverage, recorded separately from orderly exits.

## Results, with original denominators

All201 new runtime attempts: **188 raw PASS /13 raw FAIL**, including development,
legacy pilot and isolated SDK observation. Full cohort rows and individual exits
are in [results-summary.json](results-summary.json). They are not one qualification
denominator, and older pilot57/DDS42 records are not included or overwritten.

| Fixed completed C++ campaign4 | Normal | ASan/UBSan | TSan fixed layout |
| --- | --- | --- | --- |
| normal |3/3 |1/1 |1/1 |
| late, ready-timeout |2/2 |2/2 |2/2 |
| invalid, delay |2/2 |2/2 |2/2 |
| command/result/status/lease loss |4/4 |4/4 |4/4 |
| overflow, full-queue close/reopen |2/2 |2/2 |2/2 |
| Central survives Front crash/rejoin |1/1 |1/1 |**0/1 raw FAIL** |
| Front protection after Central crash |1/1 |1/1 |1/1 |
| Total |**15/15** |**13/13** |**12/13** |

TSan's remaining raw FAIL had no race warning and all actual processes/rejoin assertions
passed. It logged an outstanding RunLease send reset after the deliberately injected
Front SIGKILL. Final runner classification requires exact socket/service/method/101-byte
payload loss, declared crash, a live original credit, observed Central protection and
actual new-session recovery; every other SDK error still fails. Logs stay intact.
Affected restart-only regression on the **same C++ binaries**: Normal1/1, ASan1/1,
TSan1/1. ASan actually exercised this classification branch once; the other two did
not log the reset. The original TSan exit1 is retained, not retroactively passed.

Additional results:

- Corrected legacy pilot normal/binding-invalid/invalid:3/3 per build, **9/9**.
- Logging-only separate SDK normal/full-close comparison: **2/2**, excluded from
  unmodified-SDK qualification.
- Related common contracts, unmodified product code: Session/Coordinator/remote
  contract/remote Leaf+Zone integration/async owners/VehicleCoordinator/readiness,
  **145/145 Normal and145/145 ASan/UBSan**, seven executables each, XML and commands retained.
- **43/43 Python** in the working tree and fresh committed checkout without build/:
 14 SOME/IP bookkeeping/binding tests +29 DDS bookkeeping tests. The binding test
 compiles a standalone checker with4274 assertions; none of these43 is an SDK run.
 A real dummy-child forced-timeout test verifies failure/cleanup reporting.
- Whole973/native40/timing48 **NOT RUN again**. Shared owner/session/protection
 implementation is unchanged; affected contracts above were rebuilt/tested. Existing
 native timing campaign executes a different scheduler and would not qualify this one.

Normal Front-result acceptance minus original sent: **153 samples,0.264439–1.061657ms**.
Offline audit matches Epoch/token/operation and unchanged sent/deadline/original-source/
inner-deadline across request, Front reception and accepted result; all153 are inside
the original20ms envelope. Sanitizer observations are separate: ASan50 samples
0.284114–1.066452ms; TSan51 samples0.850558–1.969556ms. These are short-run observations,
not worst-case timing guarantees. Late fault-injected commands retain original deadlines
and are rejected; actual normal expiry/loss remains failure.

## Protection, full queue, cleanup and recovery

Every final invalid case rejects9 malformed pre-INIT messages with state_violations0;
subsequent real control proceeds, duplicate/future-Epoch diagnostic requests are negative.
Previous-Epoch rejection is separately demonstrated after actual restart. Legacy pilot
wrongmethod0x21 failed before correction and passes the exact binding tests afterwards.

Full-close, all profiles: Front RX highwater **8/8**, consumer held, eight unprocessed
requests explicitly rejected, actual Leaf protection selected before SDK stop. Central
stays alive through stop/join and accounts **16 diagnostic sends =8 rejected+8 expired**
(no pending remainder). This loss is intentional fault evidence, not delivery success.
Front stop-begin→dispatch-join return: Normal0.455429ms, ASan1.366454ms,
TSan2.445085ms. No runner forced cleanup. Both ECUs then restart on the same netns/veth,
same durable store and still-running physical model; Epoch2, mask255, arm and normal
control pass. This differs from older close-busy's only1/8 queue.

Lease-loss proof (monotonic ns; `last_lease_expiry` is not the only limit):

| Profile | Original last lease expiry | Local protection detected | Actual Leaf selection |
| --- | --- | --- | --- |
| Normal |527035545390729 |527035515606868 |527035515607582 |
| ASan |527064468022598 |527064438068647 |527064438070090 |
| TSan |527092647576364 |527092617824108 |527092617827829 |

RunLeaseGate also enforces original30ms source age, hence protection can precede60ms
credit expiry. Relative to `original_expiry−30ms`, detection was0.216139ms,
0.046049ms and0.247744ms later respectively. These observed values do not certify
worst-case scheduling latency. Ordinary queue saturation does not stop this monitor. In normal-build
Central-stop, crash527045156062533 precedes Front detection527045179766510 and actual
selection527045179767173. The interrupted Central cannot request this selection.
`leaf-events.csv`, transport and session events preserve original input/credit expiry,
actual valid-input/selection and physical traces; all profiles' timestamps are in the
machine summary. No old Epoch is reopened by receipt of a transport probe.

## Preserved failures and concrete corrections

| Raw cohort / failing cases | Finding and action; remaining uncertainty |
| --- | --- |
| binding-before:1 | Wrongmethod0x21 processed valid owner work. Exact header, payload-kind and complete readiness/status formats now checked before enqueue; worker still revalidates. |
| attempt-01:1 | New diagnostic unsigned elapsed calculation used pre-step time before newer arm. Sample after step; control deadlines unchanged. |
| attempt-03:3 loss/delay | Runner stopped Central once Front protected, before Central observed failure. Wait for both actual transitions inside existing diagnostic cap. |
| attempt-03:1 restart | Reused SDK client target collided; distinct per-boot client IDs plus later supported readiness change below. |
| asan-final:1 restart | Adapter reused observation time after lifecycle advanced coordinator checkpoint. Preserve original root times, sample fresh API observation time; fix ClockError. |
| clock-asan:1 restart | Physical model failed; approximately61.34ms since last sample, conversion uncertainty0.37ms, exact submodel/gap not logged. Workspace metadata search overlapped. **OPEN-SOMEIP-HOST-01**; tmpfs model IO and failure timing trace added, original cause not proven. |
| normal-final2:1 normal | Ordinary queue overflow after10 batches. Definite repeated per-poll marker-file writes fixed to one-shot. Marker overhead alone is not a proven cause of every Host pause. |
| normal-final2 + tsan-final2:2 restart | Delayed previous-session credit filled new Front authority queue before INIT. Prequeue stale/unbound filtering from actual positive INIT ACK cache; existing gates still authoritative. |
| tsan-final3:1 restart | Actual recovery passed but request/response readiness hit SDK target replacement. Exact pinned cache key omits Session ID; use two-way nonce-correlated NO_RETURN methods, avoiding that cache through supported API. |
| tsan-final4:1 restart | Intentional crash's RunLease reset misclassified as unexpected SDK error. Narrow evidence-based fault accounting, regression3/3; original raw exit1 unchanged. |

The [prospective amendments](protocol.md) precede their respective comparisons;
there was no retry of an unchanged unexplained case until success. No shared owner
deadline, queue bound, authority criterion or original assertion was relaxed. The
older pilot attempt-02 is now cohort-excluded in both README and machine metadata,
including its individually successful ready-timeout; raw per-case exits are unchanged.

## SDK send-warning interpretation

At pinned `tcp_server_endpoint_impl.cpp:996–1024`, the warning's else branch also runs
when sending is already false. A separate logging-only object/library records six
occurrences with **sending0,error125(operation_aborted),queue_bytes0,train_bytes0,
dispatched_trains0,reschedule0**. Thus these six are not demonstrated timer expirations.
Raw warning text, observation lines, SDK stop/join return times, peer reception and
application pending accounting are retained. Normal result coverage is complete;
full-close's rejected/expired requests are separately accounted, not called drained.
The observation patch changes no SDK algorithm and is not the installed default.
Its first compile failure (private member access) is also preserved.

Pinned request-target registration is in `tcp_server_endpoint_impl.cpp:688–698`;
`server_endpoint_impl.cpp:121–123` indexes service/method/client, not Session ID.
The completed adapter avoids that response cache; it does not claim to repair it.
[Unsent support draft](sdk-support-draft.md) records exact questions and source links.
No external issue/message was posted. No new Daybreak/content restriction appeared;
prior DDS restriction history remains untouched.

## Remaining adoption boundary and next step

The functional Host two-ECU objective is met: real authority, actual feedback, local
protection under fault and explicit new-session recovery are executable. Adopt this
**conditionally as the Host functional SIL integration route**. Do not enable a
general operational/native timing gate: this200µs polling scheduler has not integrated
the existing M4 native2ms opportunity/4ms independent execution watchdog. Earlier
61ms physical-model incident remains OPEN. Long-duration/load/CPU starvation, real
IO, fault tolerance against arbitrary SDK hangs, Rear network and Jetson are unverified.

Next one step: connect this adapter's bounded ingress/egress and lifecycle to the
existing native execution-watch owner runtime, then execute its prescribed Host-load
qualification with original deadlines. The current SOME/IP choice adds four service
bindings, application readiness/correlation/credit handling, separate authority lanes
and dependency/instrumentation maintenance; it does not provide DDS QoS equivalence
or erase DDS failures.

## Reproduction and archive

Run each command separately; output directories must be new. Build and SDK runners
share `build/.m4-exclusive.lock`, created without requiring existing build artifacts.
Do not run heavy builds/searches concurrently with timing observations.

```bash
python3 tests/integration/someip/build.py normal
python3 tests/integration/someip/build.py asan
python3 tests/integration/someip/build.py tsan
python3 tests/integration/someip/front_run.py build/repro-front-normal --profile normal --normal-repeats 3 --cases normal late ready-timeout invalid delay command-loss result-loss status-loss lease-loss overflow close-full restart-live central-stop
python3 tests/integration/someip/front_run.py build/repro-front-asan --profile asan --cases normal late ready-timeout invalid delay command-loss result-loss status-loss lease-loss overflow close-full restart-live central-stop
python3 tests/integration/someip/front_run.py build/repro-front-tsan --profile tsan --fixed-layout --cases normal late ready-timeout invalid delay command-loss result-loss status-loss lease-loss overflow close-full restart-live central-stop
python3 -m unittest discover -s tests/unit -p someip_pilot_test.py -v
python3 -m unittest discover -s tests/unit -p dds_lifecycle_test.py -v
python3 -m unittest discover -s tests/unit -p middleware_probe_test.py -v
```

[raw.tar.gz](raw.tar.gz) contains every201 attempt's original configs/plan/result,
stdout/stderr, PCAP, process commands/maps/settings, events/timing/model snapshots,
build logs and compile databases, final source snapshot, unit XML/logs and isolated
SDK observation patch. [raw-manifest.json](raw-manifest.json) hashes every member
and the archive. Extract to an empty directory and run
`python3 analyze.py /path/to/extracted /path/to/new-summary.json` to reproduce the
immutable cohort aggregation, original-time correlation and IP stream sample.
