# SOME/IP native watch prospective protocol

Start 2026-10-21 clean HEAD/origin/main767d334, no local changes, fetched0/0.
Preserve previous201 runtime188/13, final TSan12/13 plus restart3/3; DDS historical OPEN.
No sudo/security changes, external messages or broad SDK redesign.

## Stage A, genuine overflow

One pre-fix normal overflow run with an offline strict oracle requiring rx overflow.
Then unchanged capacity8, paused consumer, observed full8, ONE extra test-only message,
exact rejection/FIFO preservation/latch/local protection before any remote protection.
Normal, ASan/UBSan, TSan fixed-layout once each;20s supervisor. Full-close remains a
separate non-overflow purpose. Record all pending8 plus extra1 accounting and new-Epoch
restart. Existing failures/assertions remain; extra traffic bypass is test-only, not
an expanded normal producer window.

## Stage B, native integration

Reuse TaskSchedule/DeadlineMonitor/M4ExecutionWatch and existing atomic RunGate/
Protection/physical override. Actual request timer slot, not delayed wake time, selects
completion identity. Per-ECU controller execution stays single-owner; independent
monitor never calls mutable owner/controller methods. Separate process-local monitor
records its own completion for the persistent physical process to check. SDK sender,
callback, probes and shutdown are outside guarded owner work. Callback only validates
and bounded-enqueues. Period2ms/deadline4ms represent service opportunities; existing
Leaf10/20ms runnable periods/budgets and Central20ms allocation remain independent.
Guarded run2540ms, lead100ms,20ms tail,1211 slots. Model runs500us; owner service200us;
monitor2ms. No loss/expiry/deadline/queue widening. Nonexecuted/late slots stay missing/late.
Model IO and step failure observations bounded; add exact first failed submodel,
return site, last success/current calls, input time/dt, Epoch/output/protection and
lock attempts/busy/error counters. Controlled61ms model pause once validates evidence,
not the original incident's cause; OPEN-SOMEIP-HOST-01 remains OPEN.

Preflight records actual allowed CPUs/RT limit/policy and TIDs. Default CPU1 Central,
CPU2 Front,CPU3 physical,CPU0 independent monitor threads. OTHER0; FIFO only selected
owner/physical/monitor threads with existing priorities (Central11,Front18,physical19,
monitor20); SDK stays OTHER0. Local grouped Leaf/Rear ownership and shared failure
fate are explicit. No blanket FIFO. Actual RT refusal=>NOT RUN, no fallback.

First one normal/one FIFO native setup smoke. Specific implementation corrections
permit one targeted regression then a separately identified final cohort.
Final adapted48 requests: Normal/ASan x OTHER/FIFO x(normal quiet, normal loaded,
owner pause200ms, monitor overrun6ms) x3. Rotate conditions per repetition. Load is
separate OTHER process on Central/Front CPUs,7ms busy per10ms, verify CPU time>=100ms,
affinity/alive/busy windows. This is a NEW remote grouped-owner profile, not a replay
of old separate-thread scheduler acceptance. Normal duration2540ms, fault at1200ms.
Normal requires all guarded slots complete on time and real control/feedback/model
coverage. Fault requires no pre-injection fault, detected within10ms after original
4ms deadline and physical protection within10ms when physical worker runs; no stopped
owner ACK. Normal timing FAIL and successful later protection are separate.

Functional final boundary per Normal/ASan/TSan: normal,command/result/status/lease loss,
actual overflow, full-close/reopen, invalid, delay, restart-live, central-stop plus
owner pause and monitor overrun once (20s cap). TSan fixed-layout condition remains.
One controlled model-delay case Normal/ASan; original model failure is NOT retroclosed.
All unexpected SDK/sanitizer/missing/timeouts=>saved exit1; injected peer reset only
under existing exact loss/protection/rejoin predicate. Forced cleanup != orderly stop.

Shared runtime/model observability changes require complete existing Normal and
ASan/UBSan CTest regression, retaining all973 names/assertions plus new tests. Native
watch tests and old native smoke/fault boundary run based on changed shared watch.
No build/heavy search concurrent with measurement. Each plan saves source/binary/SDK
identity before workload. No unchanged failure repeated until success.

### Stage A correction before second normal comparison

Pre-fix raw runner PASS but strict overflow oracle FAIL (queue8,overflow=false).
First corrected run directly proved ninth rejection/latch/FIFO unchanged/local
selection, but runner timed out waiting Central protection: freeze_normal also
stopped core.tick and credit issuance. Restrict freeze to scenario root/allocation
inputs; core expiry/feedback monitoring and live credit issuance continue. No forced
Central protection for overflow. One normal rerun, then ASan/TSan once.

### Guard ownership mapping (before native implementation)

Central group7 executes Central/Rear/Drive/BMS/Power/Ingress serially on its one
existing controller thread; Front group0 executes FrontZone/Steering/Brake serially.
The guard covers the whole actual group body including ingress/egress, not fabricated
separate completion records for its local members. Leaf10/20ms runnable guards stay
in existing owners. Each process has independent monitor9 atCPU0; plant group8 is a
separate process with monitor9. Physical checks process monitor completion slots via
a bounded Linux shared-memory observation channel and applies existing physical
override. It is model/output-driver protection, never an ACK from a stopped owner.

Stage A: normal2 and ASan overflow passed all direct assertions and restart. TSan
all actual overflow/protection/restart assertions passed, no race report, but raw FAIL
on Front's85-byte Feedback send reset after runner closed Central first. This is NOT
the explicitly injected Front crash lease-reset exception. Fix runner shutdown order:
keep Central receiving until Front final evidence/SDK stop/join return, then stop
Central. Repeat affected TSan overflow once, same C++ binary; preserve original FAIL.

Native setup smoke: OTHER raw FAIL on actual Front missing slot102 and physical
missing slot149 (no synthetic injection, no sanitizer); retain normal failure and
successful detected protection separately. FIFO smoke PASS, Central/Front each1211
owner +1211 monitor slots,0miss. Actual RT limit20 and FIFO thread readback succeeded.
No attempt to heal OTHER timing by increasing deadlines.

Before final cases, extend the observed reverse-order shutdown correction to healthy
runs: after actual protection/quiescence retain Central receive endpoint until Front
stop/join, bounded1s peer handshake inside original20s case cap. It is not normal
command lifetime or an API success substitute. Keep original source timestamps and
record any handshake timeout as FAIL. Guard actual cleanup service until quiescence.

Final functional SDK matrix uses the observed working FIFO profile, with SDK threads
still OTHER0; sanitizer performance is separate. Native48 retains both policies and
all planned quiet/loaded requests, including OTHER failures. Model-delay expected
fault keeps raw plant exit1 and exact energy.step/dt/original input context; only
that declared injected model failure can satisfy its observability case. Any unrelated
model failure, premature miss, SDK error or sanitizer report fails the runner.

### Physical override priority correction before final qualification

First native FIFO normal-build functional13:12PASS/1FAIL. central-stop fails in
PhysicalOwner brake.target-output at531341511550569, input531341511268054,
last successful531341511047599, dt502970ns, IO errors0. Existing independent override
was selected at531341504536485; still-live Front produced a fresh nominal Target
before its own authority/source-age monitor tripped. The model tried to apply this
normal Target to the latched protected brake and returned false. This is a confirmed
common physical-output arbitration defect, not the prior61ms incident.

Add a specific same-Epoch fresh-output regression (pre-fix expected FAIL), preserve
normal command bytes/timestamps, give the already-selected physical override priority
before nominal output application, permit only actual higher-Epoch release to recover.
Run full Normal/ASan regression again because shared protection/model code changes,
then final same-source13 functional cases each Normal/ASan/TSan and the planned48.
No criteria/queue/deadline change. Historical61ms cause remains OPEN.

### TSan native FIFO investigation (before additional execution)

Final functional cohorts: Normal13/13, ASan13/13, TSan0/13. No sanitizer warning;
TSan owner bodies consume about1.2s thread CPU while independent monitors protect.
This is an executed timing FAIL, not a clean sanitizer qualification. One diagnostic
normal case under GDB will sample Front threads200ms after readiness (same binary,
TSan fixed layout/FIFO). It is intrusive, excluded from acceptance,20s cap/no retry.
Hypotheses: our queue mutex vs sanitizer/runtime internal lock/priority inversion.
No scheduler/security setting change. Preserve all stacks and raw exits.
Also fix observed finite-window requested-slot alias: a request after the last2ms
opportunity must not complete the final slot. Add a unit before further qualification.

GDB sampled Front owner in libtsan `Mutex::ReadLock`/`MetaMap::GetAndLock`/
`MutexPreLock` before Transport::pop's pthread mutex; sender in same meta mutex's
write-lock path, SDK dispatcher waiting application mutex. Repeated sched_yield from
FIFO owner cannot yield to OTHER tasks on its CPU. This is concrete instrumented
scheduler interaction, NOT an SDK race-warning false-positive determination.
Next one-case comparison keeps C++binary/deadlines/priority unchanged; move initial
Central SDK/sender/background threads to CPU4, Front toCPU5, plant aux toCPU6.
Owners remainCPU1/2/3, monitorsCPU0. No blanket FIFO or SDK patch. All inherited and
subsequent thread readbacks retained. This placement becomes a separately named
candidate only if the comparison supports it. Original TSan0/13 remains FAIL.

Placement comparison: TSan normal still FAIL (normal protection after21batches), but
all observed native slots completed within4ms, maximum Front poll0.352ms/Central0.604ms,
no1s CPU stall and no sanitizer report. This supports removal of the observed shared-
CPU inversion, not full acceptance. Keep the raw normal transport/control failure.
Final source includes finite-window alias regression; use split SDK candidate for
one final13-case cohort perprofile and the fixed48. No retry if remaining timing/
normal failures; analyze original expiry/feedback evidence. Run model-delay again
only because placement and final shared guard changed;1perNormal/ASan.
Existing native impact: one FIFO quiet normal/drive-stop/monitor-overrun each
Normal/ASan (6requests),2540ms, existing original oracle/no retry; not replacement
for the new adapter48. Full existing regression again after shared guard fix.

Final split-placement cohorts completed: Normal12/13, ASan13/13, TSan10/13;
adapted48=31PASS/17FAIL; old native6/6. No unchanged runtime reruns are planned.
Several faults never reached injection because normal local protection happened
before10completed batches. The runner waited for control-established until timeout,
causing a secondary bounded trace-capacity error. Correct only failure bookkeeping:
reject pre-injection protection/exit immediately (also during the1200ms wait), and
explicitly mark absent injection as a failed native fault oracle. Unit fixtures
exercise both marker roles and child-exit branches; offline raw re-adjudication
preserves every original exit. C++/SDK binaries unchanged; no new normal PASS claimed.
