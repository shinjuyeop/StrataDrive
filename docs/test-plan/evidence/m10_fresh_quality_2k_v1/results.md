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

## Development verdict

The development candidate failed absolute quality on all 81 selected original
exposures. The paired comparison with YOLOX-S passed every relative gate.
The candidate detected all 18 near, all 18 medium and all 18 far primary targets,
and 15 of 18 occluded primary targets. All included visible objects, including
parked background vehicles, enter the score. No holdout evaluation was acquired.
[Development comparison](runs/evaluation-development-01/comparison.json)

| Pipeline | True positives | False positives | Misses | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| D-FINE-M960 native 2K | 320 | 67 | 214 | 82.69% | 59.93% |
| YOLOX-S640 paired | 268 | 178 | 266 | 60.09% | 50.19% |

Three parked car instance IDs accounted for all 205 car misses. Two were missed
81 times each and the third 43 times. There were 63 truck false positives.
The map registry independently projects a Jeep Wrangler and a Nissan Patrol
into the overlapping group. Their registry class is Car. The registry and mask
IDs use different namespaces. [Static object geometry](development-static-registry-01/static-objects.json) · [Counts and original hashes](development-disposition.json)

The first holdout preparation acquired all 99 images. The walker fell below the
inclusion limit in all three occluded-person scenes. A 20 cm lateral adjustment
to their blocking vehicle was fixed from the preparation masks before detector
evaluation. The same change applies to the holdout evaluation plan. The
development partition is identical. Holdout preparation 02 then passed all 99
scenes and 18 occlusion pairs. The three walker/reference ratios were 72.58%.
[Original geometry](before-holdout-occluder/preparation.json) · [Corrected preparation](runs/preparation-holdout-02/visibility.json)

Replaying D-FINE's original numerical outputs at the existing confidence floor
of 0.35 yielded 392/534 true positives (73.41%). Raising any class threshold
discards lower-ranking detections and cannot reach the 80% recall gate.
Combining full-frame inference with four overlapping crops gave 74.90%
precision and 68.73% recall. The separately registered YOLOX-L, RT-DETRv2-R18,
RT-DETRv4-S and DAMO-S pipelines also failed absolute quality at the declared
screen configuration. [Development comparisons](development-disposition.json)

A fifth off-the-shelf alternative used instance masks to form visible boxes.
TorchVision Mask R-CNN ResNet50 FPN V2 produced 64.16% precision and 62.36%
recall. Its original object boxes produced 64.74% and 62.92%. These development
screens did not produce a replacement Reference. [Weights and inputs](development-mask-01/declaration.json) · [Mask and box scores](development-mask-01/scores.json)

A separate output replay checked the baseline and candidate tensors, regional
detector outputs, all four comparison models and the visible-mask outputs
against their stored predictions for the 81 development scenes. The original
development decision reproduced as FAIL. [Replay result](development-output-replay.json)
