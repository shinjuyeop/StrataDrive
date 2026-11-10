# M10 pretrained model screen v2

This protocol is fixed before candidate quality inference. It is consumed-development
screening, not fresh acceptance, runtime promotion, training, or Jetson optimization.

## Candidates and provenance

Compare the existing pinned YOLOX-S, YOLOX-L and RT-DETRv2-R18 references with
official COCO pretrained D-FINE-M, RT-DETRv4-S and DAMO-YOLO TinyNAS-L25-S.
Pin upstream revisions, checkpoint bytes, inference configuration and exported
FP32 ONNX bytes in a new v2 registry. Use hash-checked `weights_only=True` loads,
strict complete state loading and upstream inference/deploy conversion. No local
training, teacher inference, checkpoint substitutions, quantization or ensembles.
Acquisition/export failures remain visible and exclude a candidate until resolved
with a recorded, reproducible correction. Never call a different checkpoint the
original published variant. Preserve upstream source and license bytes.

## Development partitions and selection

The only quality inputs are the sealed **development** datasets from V4g, V5b,
V6 and V7 (81 frames each, 324 calibration frames), followed by V8 Town04
development (81 check frames). No holdout manifest, image, GT or prediction is
an input. Validate development partition, seals, frame lineage and disjoint RGB
hashes. Existing preparation-development probes supply three numerical probes.
These 405 frames are already consumed development; no new RGB is acquired and
the future fresh-capture exclusion inventory remains 4,990 hashes.

For every candidate report the common score threshold **0.35**, and select one
global candidate-specific threshold from **[0.10, 0.20, 0.30, 0.35, 0.40, 0.50,
0.60, 0.70]** using the 324 calibration frames only. Rank thresholds by:

1. all existing absolute development quality gates passing;
2. higher six-class macro F1;
3. higher minimum class recall;
4. higher micro F1;
5. higher threshold for an exact tie.

Seal all candidates' selected thresholds, calibration score hashes and source
freeze hash **before** scoring Town04 development. Do not change settings after
that check. Report per-dataset, per-class, near-person, negative-scene and Rider
diagnostics. A threshold grid is calibration, not eight independent acceptance
attempts. Any later model/configuration choice requires a newly declared fresh
quality protocol and fresh holdout; prior holdouts remain consumed.

## Inference and numeric contract

Use FP32, batch one, each model's native 640 input preparation and postprocessing.
DETR models use the upstream RGB PIL bilinear direct resize / 255 and the full
300-query output, without NMS. YOLOX keeps its native RGB 0–255 top-left
letterbox, objectness-times-argmax confidence and class NMS IoU 0.5. DAMO uses
the pinned official GitHub still-image demo PIL RGB direct 640×640 OpenCV linear resize,
mean0/std1 (no letterbox with `keep_ratio=False`) and native class NMS IoU 0.7;
verify the recipe against the upstream implementation before admitting it.
Keep all 80 native classes through NMS before filtering six target classes
(COCO contiguous IDs 0, 1, 2, 3, 5, 7). Only confidence varies in the grid.

Retain complete exported raw arrays for numerical probes and compressed raw
outputs for each quality frame. Derive all thresholds from those same raw arrays.
Validate dtype, shape, finite values, confidence range and ordered decoded boxes;
clip publication boxes to 640×384, and fail above 100 final detections rather
than truncate. A failure counts against the full denominator, never as a valid
empty scene. The unchanged strict class/IoU 0.5 scorer counts all positive GT,
including supported Riders; excluded-overlap diagnostics do not remove primary FP.
The native DAMO NMS retains its official top500 before the target class filter.
Below0.35 calibration values use a separate offline detection type. The runtime
envelope's frozen0.35 floor is unchanged; adopting a lower threshold would require
an explicitly versioned runtime contract and fresh acceptance.

Check new exports against independent upstream PyTorch FP32 and ORT CPU/CUDA
on three fixed development probes. Compare DETR's complete 300-query unordered
set one-to-one: exact classes, box absolute error ≤0.1 px and score ≤1e-4.
For dense heads use raw atol/rtol 0.003/0.003 and final box ≤0.1 px / score ≤1e-4.
Check every confidence-grid final set. No numeric tolerance is tuned on quality
results. Preserve any failed check and its correction before source freeze.

Use pinned ORT 1.23.2 CUDA, TF32 off, explicit provider settings and no CPU node
fallback. Include cold inference and initialization separately. Raw-cache I/O
is outside inference timing; threshold-specific postprocessing is timed and
reported separately. These are offline Host measurements, not live 20 Hz or
Jetson measurements. Freeze source, registry, numerical checks and dataset seals
before the complete quality run; audit archived source replay and all raw hashes.

## Unchanged interpretation

Absolute quality gates remain precision ≥85%, recall ≥80%, every class recall
≥70%, near-person recall ≥90%, negative FP/frame ≤1/3 and no model errors.
Relative reporting uses the pinned S at the same common threshold, requires
precision and recall improvement ≥3 percentage points and no class recall drop.
Calibration results cannot close M10 or promote a model. Preserve the default
YOLOX-S runtime. Each eventual AGX Thor and Orin NX deployment must run the
complete Central–Zone–Leaf stack independently, first with the selected common
reference. Board engines, FP16/INT8 and tuning remain deferred until deployment
and measurement are explicitly in scope.
