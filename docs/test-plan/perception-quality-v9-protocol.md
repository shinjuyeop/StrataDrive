# M10 V9: fixed pretrained D-FINE-M class-v1 on fresh roads

Declare this protocol before the new map-only survey or any new RGB. Compare
the original S at confidence0.35 against the single already fixed
`dfine-m-class-v1` development nominee. D-FINE-M ONNX is77,949,424bytes, SHA256
`40097ba600ba21b94c673a76ff602ece600392fc1d9641576ff66bfa0300e1c2`.
Use the existing candidate profile and class0/1/2/3/5/7 confidence vector
`[0.60,0.40,0.70,0.50,0.50,0.60]` without fitting on V9. Keep all prior failures.
No training, new export, crop/ensemble, quantization, board engine or optimization.

S retains native RGB0–255 top-left640 letterbox114/objectness×argmax/class
NMS0.5. D-FINE retains native PIL RGB bilinear direct640 /255, original[width,
height], full80-class top300/noNMS, then target-class confidence filtering.
Both use FP32/batch1 on Host CUDA. These offline outputs do not publish to C++
or vehicles and cannot replace the default S runtime.

## New roads, model-free preparation and acquisition order

Query all372 installed Town04_Opt spawn points again without cameras or models.
Keep the original complete0–42m nonjunction/lane-width≥3.2m/turn≤15deg/frustum/
index≥7 eligibility. Exclude every route road ID and route origin used by V8
on this map, including both preparation/evaluation sites7/25. IDs on Town03
are a different namespace. Sort indices and select the first eligible route
whose entire road-ID set is unused and whose origin is≥50m from all prior and
selected route origins (camera reference points); repeat for the second route. Freeze the exclusion
descriptor, survey source and this protocol before launching the survey.
No site or model choice may depend on old holdout imagery/predictions.

Use the existing V8b recipe unchanged except new mapped poses and V9 identities:
640×384/FOV90/Epic/postprocess, world10ms, settle40/capture10/tick5; six classes,
three weathers, near/medium/far/occluded/negative/overlap; physics-off actors,
50m staging without tick before placement. Held person far26m and the existing
held-person occluder lateral−0.4m remain fixed. Preparation uses distance+1m and
camera height+0.05m,99 paired frames per site including18 occlusion references.

Before any model inference, require both preparation partitions to PASS every
planned actor and Rider25pixels/side4, pose2cm/0.1deg, projection2m/clearance15cm,
class×stratum coverage3/3 and occlusion ratio0<visible/reference<0.95. Retain all
failed/partial attempts. A necessary geometry-only recipe revision requires a
new annex/profile/source version before recapture and before any model inference;
it cannot relax a gate or use detection scores to select a site/pose.

Exclude all4,990 previously consumed RGB hashes and every V9 preparation,
failed/partial/rejected capture hash from later evaluation/future inventories.
Freeze final source, plans, model identities, protocol and complete exclusion
after successful preparation and numeric checks. Acquire fresh development81,
score only S and this candidate, then seal the original single nomination and
scores before starting a fresh holdout81 server. Thresholds/model remain fixed
even after a development failure; descriptive holdout is permitted and does not
erase any failure. Never retune or reselect after holdout.

## Numerical contract and execution bounds

Use the first3 accepted preparation-development frames as numerical probes.
For S compare ORT CPU/CUDA/OpenCV raw at atol1e-3/rtol1e-4, complete class/count,
box0.01px/score1e-4. For D-FINE compare unchanged upstream PyTorch FP32 and ORT
CPU/CUDA full300 one-to-one unordered sets: exact class, box0.1px/score1e-4;
also compare the complete fixed-vector detections. Preserve failed checks and
do not tune tolerances. Keep the source/checkpoint/export pins from the existing
pretrained/candidate registries. Numeric checks do not measure detection quality.

Every isolated UE server has startup180s/capture900s/shutdown30s and expected
exit130. One same-source/plan/budget retry is allowed only for a0-RGB readiness/
RPC failure. Retain the original failure. A shutdown failure with RGB is not
accepted or automatically retried; any further recovery needs a separately
declared bounded annex. Do not overlap heavy archive I/O with UE startup.
Record all attempts, cold/init/error/late calls with full denominators.

## Unchanged gates and audit

Keep tight visible-instance boxes, strict class/IoU≥0.5, Rider→person and
primary-ignore=false. Keep every V4/V8 absolute quality, relative promotion,
coverage, annotation and nomination rule unchanged. Absolute: P≥85%, R≥80%,
each class R≥70%, near-person R≥90%, negative FP/frame≤1/3 and no model errors.
Relative: P improvement≥3 percentage points, no overall/class/far/occluded
recall drop, no near-person TP drop and no negative FP increase versus S.
Both partitions must pass for a new runtime-profile/interface review; no
automatic adoption. The earlier calibration experiment's relative rule is not
a substitute for these full fresh-quality rules.

Retain original RGB/instance, actual poses/road observations, full exported raw
model arrays, predictions, source/config hashes and timestamps. Replay survey
selection, all preparation attempts/exclusions, RGB→GT/geometry, strict scores,
nomination and capture order. Re-decode every raw model output and audit from
an archived fresh-source subprocess. These finite stationary synthetic scenes
do not qualify live20Hz, dynamic ODD, vehicle integration or Jetson execution.
Each eventual Thor/Orin deployment runs the complete stack independently with
the common reference first; board optimization follows deployment/measurement.
