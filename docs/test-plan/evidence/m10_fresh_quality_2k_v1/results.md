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

The full map commandlet stopped at its 30-minute limit after building 375 mesh
distance fields. In the dedicated game-mode warmer, 429 outstanding distance
fields and 339 shader jobs drained to zero. Its first actor pass stopped at an
occupied preparation spawn. The next pass loaded all 11 declared blueprints and
verified both queues empty before and after. These offline loads created no
sensors. Formal captures then used the original renderer with annotation tags.
[Commandlet outcome](map-ddc-01/disposition.json) · [Game resources](game-resource-preparation-03/game-resources.json)

Development preparation 03 ended on a weather readback before the first selected
exposure. The acquisition now checks the requested and observed weather after
the original 40 settling ticks and before selecting the image. The plan,
exposure rule, weights and score thresholds were retained. Development
preparation 04 passed all 99 scenes, including all 18 occlusion pairs and the
rider checks. No RGB image matched the 46,698 prior hashes.
[Previous freeze](freeze-before-settled-weather.json) · [Development preparation](runs/preparation-development-04/visibility.json)
