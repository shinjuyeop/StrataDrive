# 2K quality acquisition results

Development preparation 01 ended before any exposure. An additional empty-map
preparation ended during startup. The SDK now waits for the selected map's load
completion before its first connection. The previous source freeze is retained.
The evaluation scenes, camera settings, selected sensor phase, models, thresholds
and labels are unchanged. [Previous freeze](freeze-before-passive-start.json)

Development preparation 02 confirmed the selected map after 51.10 s plus 1.97 s
for a single SDK request. It stored 18 of the planned 99 paired exposures before
the renderer exited with SIGSEGV. All 18 RGB and instance originals could be
decoded with the original hashes. Every planned actor and rider in those 18
scenes met the annotation inclusion rule. The attempt failed. No detector or
holdout evaluation ran. [Original server verdict](runs/preparation-development-02/server.json)
· [Partial image and visibility inventory](runs/preparation-development-02/partial-originals.json)

The top frame was `FDistanceFieldVolumeTexture::IsValidDistanceFieldVolume`,
called from the primitive shader-data update. The engine was completing deferred
distance-field builds during the run. This identifies the failing render path;
the trace does not identify the owning mesh. The selected twelve Town04 map
packages were submitted to Unreal's derived-data commandlet before the next
acquisition. [Original map bytes and command](map-ddc-01/invocation.json)
