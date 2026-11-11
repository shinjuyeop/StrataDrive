# Source comparison V2: admit both declared sensor dimensions

The first V1 source-4k-01 completed100 raw frames at15.556Hz. V1 source-2k-01
failed before any image delivery: the instrumented CARLA readback rejected every
2560×1536 request with unexpected_dimensions. Its raw count is0 and no camera rate
can be inferred. Preserve both original reports, source621 and all100 received RGB;
source-2k-02 V1 is NOT RUN because its module has the same known incompatibility.
This is a new implementation revision, not a retry under V1 or a changed verdict.

Preserve all621 parent files. tools/carla/m10_readback_source_v2/readback.inc changes
only the explicit dimension guard from3840×2304 to the set {3840×2304,2560×1536}.
Allocation, original frame/time, stream ownership, query/poll, buffer copy, task and
resource caps remain byte-identical. Build in isolation from the pinned original
CARLA module; no external source edits. A distinct server profile pins the new module.

Run a new matched source-4k-01, source-2k-01, source-2k-02 in the V2 evidence scope.
All three use the same newly built module and unchanged V1 client/native kernels,
normal bytes copy, Epic/FOV90/postprocess, main viewport, blocking query and targets2/1.
Same fixed10ms asynchronous world/frame%5 source, original exclusive dual100ms and
state100ms,500..504-frame windows,300ms silence,3-call preparation and latest1 owner.
V1 observed15.556Hz is historical only; use the NEW V2 baseline for matched claims.
Full gates/rates/tails and all failures remain recorded. No source clock/FPS cap change.

Then restore the original module and capture quality-4k-01 and quality-2k-01 as in
V1: each81 already-consumed DEVELOPMENT cases, same3 weather, actor poses, FOV/aspect
and fixed D-FINE-M960/vector. No held data or new quality qualification. Keep every
selected RGB/instance pair and full model outputs. Replay model inputs with bit-exact
native/Pillow tensors; quality scoring uses all predictions including cold/late.
The offline scorer's elapsed timings include verification/unpacking work and are
NOT live pipeline performance; only live trials answer the Hz/latency comparison.
Do not silently accept any additional small/far/person miss or P/R regression.

V1 lifecycle180/900/30s, no client retries, declared startup-only recovery, original
failure preservation and immutable parent rules continue. Prior exclusions are now8213
(V1's100 new RGB plus8113), with0 received2K RGB from the rejected run. Union all new
live and selected quality RGB without assuming every hash is novel. Restore external
module and original GameUserSettings exactly. Actual20Hz in both short2K observations
is a measured-rate result, not long-term/full-stack/Jetson acceptance or automatic
runtime promotion. Real-time1× remains a target, not deliberate slow simulation.
