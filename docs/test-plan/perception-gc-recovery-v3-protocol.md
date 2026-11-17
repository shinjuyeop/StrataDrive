# M10 GC recovery V3 — standalone auditor repair

V2 completed its first 30s case with 6000 physical receipts, no native fault,
no missed/late native slots and a PASS physical audit. Its additional library
auditor exited before writing output: direct script execution did not add the
repository root to Python's import path. The runner then stopped during frozen
reproduction. Preserve that original failed sequence and both unrun cases.
The lease and all six shared runtime files were restored.

The original frozen auditor, given its own explicit root through PYTHONPATH,
and the corrected standalone auditor produce identical PASS results on the
original archived 6000 receipts. This is posthoc repair evidence, not a completed
prospective sequence and not a GC recovery result: no live GC occurred in 30s.

V3 adds the script's own repository root before importing the shared library
constant. Audit logic is byte-identical after removing those bootstrap lines.
Add regression subprocesses outside the repository with PYTHONPATH absent:
CLI help must work, and missing input must produce a structured FAIL result.
Run all eight supplemental auditor entrypoints standalone before source freeze.
Frozen tests must exercise the same subprocess path in their extracted tree.

All runtime code, native binaries, model, library files and startup reads are
unchanged from V2. Reuse C++29 and prior actual model setup/empty renderer checks
only after their source, module and argv identities match. The new launcher still
prepares assets on every actual attempt before requesting operator authentication.

Freeze fresh sources and retain V2 raw images and quality exclusions (34522).
Run 30s → 30s → 300s under the unchanged temporary70% lease; stop subsequent
cases on the first original failure. Restore100% on owner exit, Ctrl+C or30min.
Keep physics5ms, HV30ms, native2/4ms, original source clocks, held expiry before
replacement, final physical guard and300us extra admission preview unchanged.
Keep owner3/image3/native1/observer1 physical cores with separated SMT siblings,
parallel GC61.1s/12220frames, incremental purge100us,2560×1536 D-FINE-M960 CUDA,
camera target10Hz and renderer20Hz/MaxFPS60. Preserve exact replay, all original
audits, raw archives and failures. Remove only byte-verified duplicate data.

GC recovery and5min stability remain unmeasured for this recovery preview.
Continuous driving, complete visual scenes, native perception acceptance,
independent quality, each Jetson deployment and M10 completion remain OPEN.
