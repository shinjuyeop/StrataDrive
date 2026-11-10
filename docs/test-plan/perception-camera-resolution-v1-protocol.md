# M10 camera-source resolution V1: highest validated source, fixed960 detector

Before new RGB, freeze source/config/model and this protocol. The user requests
high native camera resolution. Compare camera640x384,1280x768,1920x1152,
2560x1536,3840x2304 (scales1,2,3,4,6) with unchanged horizontalFOV90/aspect5:3,
Epic/postprocess, camera pose, actors/weather and world10ms. This is a bounded
4K-width investigation, not a claim that4K is CARLA's maximum supported size.
Keep original runtime640 contracts and all prior frozen evidence unchanged.

Use ONLY the consumed V9 DEVELOPMENT road45/site38 plan, never previous holdout
RGB/GT/prediction. New images of these development poses remain development,
not an independent acceptance set. No model/threshold search, new weights,
training, export, crop/ensemble, board optimization or runtime publication.
Keep the pinned D-FINE-M960 FP32/BASIC ONNX and vector[.60,.40,.60,.50,.50,.60].

## Model-free pilot, numeric checks and largest-source selection

Run isolated pilot servers at all five source scales, in increasing order,
with fixed far person/bicycle/car cases2/6/10 from ClearNoon development. Three
paired RGB/instance frames each. Same physics-off/staging/settle40/capture10/
selectedtick5 as prior capture. Use one source resolution per server, never
multiple high-resolution cameras simultaneously. Bounds180/900/30seconds and
expected exit130 remain unchanged. A0-frame readiness failure allows one same
source/budget retry. A shutdown failure with RGB is retained and unaccepted;
the separately declared recovery annex permits one unchanged replacement only.

Before any model inference validate actual dimensions, raw/stored hashes,
paired timestamps, geometry/actor readback, no overflow/cleanup and image health.
Retain original BGRA bytes losslessly with zlib(level1), raw SHA256/byte length
and stored SHA256. Decode on demand; never replace original RGB by a640 image.

The offline variable-size frame is distinct from the original runtime frame.
PIL RGB bilinear direct960 /255, original target size[width,height] uses the
ACTUAL native camera dimensions. Preserve native full300 model raw arrays.
For comparison only, divide native boxes by source scale into canonical640x384
coordinates. This invertible coordinate conversion does not downsample pixels
before inference. Independent native PyTorch and ORT CPU/CUDA must match full300
exact class, canonical box0.1pixel/score1e-4, and complete fixed-vector detections.
Use all3 pilot frames for each scale; report all failures, never relax tolerance,
drop a low-score query or change confidence. CUDA TF32off, HEURISTIC,2GiB arena,
CPU fallback forbidden. Preserve cold/init/error/late calls.

The640 control pilot must pass before any full comparison.
Select the LARGEST source scale for which normal pilot lifecycle, all planned
actors/Riders, health and all3 numeric probes pass. Seal selection/probe scores
BEFORE comparison acquisition. Pixel preference is technical feasibility only,
not based on development detector accuracy. If a larger source fails, retain
it and use the largest passing source. No source is declared accepted if none pass.

## Full matched development comparison

Capture all81 fixed development cases for640 and the sealed largest passing
source (only once when largest=640). Same blueprints/poses/weathers/world/render
and different isolated servers. Full GT comes from each actual instance image,
not from rescaling old640 GT. Decode tags/instance IDs exactly as prior Rider-aware
policy. Canonical tight boxes are native half-open boxes divided by scale.
Minimum native area=25*scale^2, minimum native side=4*scale preserve original
angular support. Record native support plus max(1,floor(native_pixels/scale^2))
for the legacy canonical GT reader. Preserve all excluded objects; compare
planned actor/Rider visibility and report any changed GT denominator.

Run only the fixed960 detector at both source sizes after UE shutdown and
model-free raw/GT acceptance. Read GT only in scoring. Re-decode every native
raw and recompute strict class/IoU.5 counts, full original absolute gates,
per-class/near/far/occluded/Rider/size and deadlines. Compare quality against
newly captured640, not previously consumed holdout. Report regressions explicitly;
a larger technically selected source is not automatically quality-accepted.

Record full sensor capture time, raw/stored bytes, compression, RSS and observed
world tick wall cost separately from offline RGB decode/health/resize/inference/
postprocess. Simulation-time capture is not a live20Hz qualification. Source
recommendation needs normal lifecycle, geometry, numeric and absolute quality;
final model/runtime/vehicle acceptance still needs new independent development/
holdout and whole-stack timing. No board-specific performance is inferred.

## Audit and future exclusion

Retain all failed/partial attempts. Union old5449 hashes with RGB hashes of all
new pilot/comparison attempts, including rejected captures; never reuse them as
fresh holdout. Audit zlib->exact raw/RGB/native GT/canonical GT, lineage, all
native model raw/score and selection-before-comparison order. Re-execute archived
source in an isolated subprocess. Keep pretrained/license/source pins and each
future independent Thor/Orin whole-stack deployment requirement.
