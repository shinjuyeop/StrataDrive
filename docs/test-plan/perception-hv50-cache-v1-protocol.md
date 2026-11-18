# Explicit ADR-0066 and closed recording cache: prospective comparison

The existing ADR-0066 (2026-10-29) authorizes a CARLA-only wall5-hv50-v1 profile:
HV acquisition/source remains30ms; oldest computation dependency is50ms. Its
extra20ms represents one controller publication cycle. M6/default30 and original
wheel, Actual, command, 5ms physics and2/4ms monitor deadlines remain unchanged.
Earlier M10 trials did not select that profile. Their failures remain failures.

Asset-cache V1 started successfully, but its first HV30 fault at8.947006599s
preceded GC: held duration20.560192ms plus inherited age10.318659ms was30.878851ms.
Its later GC took1.631945392s with7.831694ms CPU and22 major faults. No exact
faulted mapping is known. Recorder page-cache displacement is a hypothesis;
memory exhaustion has not been demonstrated. Expired physical receipts caused
the original replay converter to reject the capture; retain that failure.

Select wall5-hv50-v1 explicitly in runner, capture and native metadata. Extend
the native endurance CLI and exact replay to carry the same already supported
policy. Preserve the default30 path and verify its retained original replay.
Keep existing boundary tests for HV source/wheel30, dependency30/50, inclusive
limits, stale replacement protection and unchanged source identity.

In this new opt-in only, close each immutable raw shard, then a separate worker
fdatasyncs it and requests POSIX_FADV_DONTNEED. Queue capacity2, one worker,
original total30s shutdown budget. Retain all original bytes and frame hashes.
Measure resident pages before/after using mincore without touching file pages;
do not promise permanent residency or exact live GC causation. Queue/sync/hint
failure fails the run without deleting evidence. Verify real file byte/inode
identity, full frame roundtrip, failure retention and bounded shutdown first.

Keep the asset-cache V1 verified NVMe placement and restoration, visual-tag
candidate module, stock renderer, pre-START code read, 4-owner/2-image placement,
70% automatic lease,2560x1536/D-FINE-M960, target10Hz, render20Hz, GC61.1s,
preview300us/purge100us. Startup180s/model10s/shutdown30s remain. Only the explicit
HV policy and closed raw-cache hints change. This combined repair tests distinct
observed problems; it cannot attribute any improvement to one change alone.

Run one30s integration check, then one300s only if every original physical,
replay and supplementary audit passes. Fresh preparation before the first run;
do not overlap build/archive I/O with preparation or physical work. Stop on the
first failure, preserve all original frames and reproduce audits from the source
archive. Chain asset-cache V1 exclusions; no holdout access. Neither the cache
hint audit nor finite performance acceptance closes full scene provenance,
native perception, quality or M10.
