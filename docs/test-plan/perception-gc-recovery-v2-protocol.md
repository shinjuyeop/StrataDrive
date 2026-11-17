# M10 GC recovery V2 — pinned inference library startup I/O

[Recovery V1](evidence/m10_gc_recovery_v1/README.md) failed before native start.
Its first model preparation did not complete within the original10s budget.
There were0 physical receipts and0 camera frames, so the300us recovery preview
was not evaluated. Preserve the failed verdict, still-busy worker cleanup report
and client SIGSEGV exit. The original capture has no crash stack; do not assign
that exit a proven native root cause.

During the original10s preparation, the highest-fault thread was in D in20/20
samples, gained370 major faults and used227.756ms CPU. GPU activity was0% in
those samples. This supports file-backed startup I/O as a contributor. An
isolated100% Host diagnostic with private byte-identical library copies recorded
a2.925s first probe versus0.471s with previously resident original libraries.
Reading and hashing the cold private libraries first took11.921s, followed by
probes352.733 /34.048 /33.815ms and0 process major faults. These are startup
experiments without CARLA, not an exact reproduction of the70% paired failure.
The added read has a visible cost; it does not claim lower total startup time.

## Only new behavior

An explicit `--prefetch-inference-libraries` option enables recorded sequential
reads of the12 pinned CUDA/cuBLAS/cuDNN files before each model constructor.
The exact profile contains1,909,074,752 bytes, original relative paths and SHA256.
No file, loader path, library version, precision or numerical operation changes.
No model call, sensor observation or control write is performed by this stage.
It must finish below a separate30s I/O budget; missing/changed bytes, time reversal
or expiry reject startup. Every completed file and elapsed interval is retained.
The default path does no additional I/O. Reads do not pin pages or guarantee
later residency under memory pressure.

Both physical-client shadow setup and actual renderer inference setup must record
matching reads before their original model probes. Keep the original3 probes,
owner total10s, settled probes<100ms, renderer readiness30s and client deadlines.
No failed worker is promoted back to READY. The previous unclosed-worker failure
remains a limitation if another uninterruptible backend call occurs.

Reuse the exact recovery module
`1feab7bc7a1c6788ec50fa507226ac01c99393d7b420912bba2e3cc1411a8eff` and300us
extra preview. Native/model math, full physical5ms, HV30ms, native2/4ms, original
source clocks, held-expiry-before-replacement and prephysics guard remain unchanged.
Keep owner3/image3/native1/observer1 cores with separate SMT siblings, parallel
GC61.1s/12220 frames,100us incremental purge requests,2560×1536 D-FINE-M960 CUDA,
camera target10Hz, renderer20Hz/MaxFPS60 and CV/resize4 threads.

## Verification and prospective sequence

Verify library identities, unchanged module/native/model inputs, explicit opt-in
and both producer readbacks, then run Python and frozen regressions. Reuse C++29
and empty-renderer startup/shutdown validation only after exact input and module
identity checks; no new native module is built. Exercise both actual model setup
paths without CARLA at restored100%, recording all startup costs and failures.
This is preparation evidence, not physical acceptance.

Freeze all code, the new library profile and external library hashes. Preserve
V1 failure and its0-frame future-quality exclusion of34241. After preparation,
operator authentication starts a fresh bounded70% lease. Run30s→30s→300s,
stopping later cases at the first failed original verdict. The lease restores
100% on owner exit, Ctrl+C or30 minutes. Keep original physical/shadow/native,
clock, source, GC/purge, workspace, exact replay and frozen archive checks.
Preserve all raw images and failed outcomes; compact only verified duplicates.

GC recovery,5min stability, continuous routes, full visual scene, native perception
acceptance, independent quality, each Jetson deployment and M10 remain OPEN.
