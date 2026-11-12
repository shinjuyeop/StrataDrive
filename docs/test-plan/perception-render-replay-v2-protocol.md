# M10 renderer clone preparation correction V2

Declared after the single V1 `renderer-01` failure. CARLA rejected creating a clone
directly at the already-settled original body pose with `Spawn failed because of
collision at spawn position`. No camera was created; no new image or inference.
Keep that failed run, source freeze and clean exit130 unchanged.

TC-PER-105: create the clone at the map's declared spawn point0, disable its physics,
then apply the unmodified original body pose before camera creation or another
tick. The preparation location never becomes the authoritative source pose.
Add a regression for the creation rejection and cleanup after failed application.
Retain actual post-tick clone matrices for independent source-pose comparison,
and test rejection of a changed clone pose.

TC-PER-106: one newly declared `renderer-02` after corrected-source freeze and
separate archive checks. All V1 camera, clock,20-tick/32-packet limits, original
receipt indices, actual pose checks, expired-scene rejection and evidence rules
remain unchanged. Second overall attempt, first with the clone preparation fix.
This remains a renderer-only kinematic diagnostic; no complete-scene, concurrent
owner/render, inference, quality or20Hz acceptance. No retry under this protocol.
