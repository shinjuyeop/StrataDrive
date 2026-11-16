# M10 owner GC V1

Owner wait V2 retained two 30s PASS cases and one 300s FAIL. First Drive HV expiry
occurred 60.2320147s after native start: dependency age 30.924896ms at the unchanged 30ms
gate. Its held sample inherited 11.786031ms and then aged 19.138865ms. Expiry lies
inside a 22.427146ms outside-pump pause after completed frame 12346: thread CPU
3.702669ms, 3 voluntary and 0 involuntary switches; max RPC 0.361146ms. Four large
pauses recur every 12220 model frames (61.1s), matching the engine's configured GC
period. That is strong correlation, not original direct GC-tagged proof.

The original later 18 native missing jobs at 259.321/259.323s and 90°C maximum remain
separate unresolved observations. All 301140 native slots before the first fault
had zero missing/late jobs. Do not use protected samples as normal performance,
infer a particular IRQ cause from 50ms counters, or call the 70% cap a complete solution.

This separate candidate adds opt-in fixed-size GC delegate timing to the physical
owner. Store at most 64 pre/trim/post GC triples with original monotonic/thread CPU,
context-switch/page-fault counters and the preceding completed physical frame.
The memory-trim delegate separates work before allocator trimming from the
remaining trim-to-post-GC interval; earlier trim delegates are outside that final
bracket. Callbacks must not allocate, output, request or defer GC. Register at explicit
profiled bind and remove on shutdown/episode end. Reject overflow, nested/invalid
pairs, changed counters or non-owner CPU observations. Retrieve the journal once
after measured work and before bulk trace export. The journal is under 16KiB;
OwnerPath and native path layouts are unchanged. GC policy readback records both
parallel choice and original 61.1s collection period.

Enable `--profile-owner-gc --owner-serial-gc` only with explicit endurance/state
profiling. The owner process alone receives `gc.AllowParallelGC 0`; renderer and
GC interval stay unchanged. No collection suppression, deferred collection,
forced live collection, freshness relaxation or altered source stamps. At least
four naturally occurring GC cycles must be directly recorded during 300s. A
physical FAIL stays FAIL even if GC observations are complete.

Keep the explicit byte-exact tensor workspace from owner wait V2, whose three
live preparations had settled calls of 31.97–36.87ms. Preserve the 10s/three-call/last-two<100ms
preparation gate. Keep HV 30ms, original check order, physics 5ms/320 steps, native
2/4ms, 2K 2560x1536/Epic/D-FINE-M960/CUDA, camera 100ms and renderer/query 20Hz;
selected Host V1 placement, passive ORT/CUDA blocking, parked preparation,
renderer MaxFPS 60, CV4/resize4 and raw NVMe recording remain.

Build one isolated module and verify unchanged physical computation/layout.
Run all 508 Python and 96 focused frozen tests, including real fixed-size C++
journal bounds/regression and invalid GC evidence mutations. Reuse the unchanged
native binary's 207 tests and 30s/300s allocation checks, and the unchanged owner
stamp cost measurement. Freeze source, protocol, runners, helper and candidate
module before live work. Record every post-V2 source change separately.

Use the existing bounded 70% helper bound to the new sequence PID; minimum 16%,
turbo enabled, original maximum 100% restored on owner exit, handled signal or
1800s. Verify measured intervals precede restoration if the limit expires during
archive work. Keep original preflight CPU<=70°C/180s, RAM>=4GiB, horizon storage
plus 4GiB, startup 180s, shutdown 30s and live reserve 2GiB. Run 30s then 30s then 300s,
only advancing after all original audits/replay/frozen reproductions pass; stop
on the first failure without same-candidate retries. No independent build, test
or archive jobs during measured concurrent work. Preserve every raw frame and
failure; future quality exclusions begin at 19991. Diagnose GC and later native/heat
observations separately. No global scheduler, IRQ, fan or permanent power change.

Finite diagnostics do not close long-term stability, continuous-route driving,
native perception acceptance, complete scene/independent quality, each Jetson
deployment or M10. Recommended next engineering model: GPT-6 Astra / xhigh.
