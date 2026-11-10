# M10 resolution V1: unchanged pretrained D-FINE-M on development only

Declare before any resolution export/reference or development inference. Keep the
original official COCO D-FINE-M checkpoint SHA256
b44a7586bf490858c7b8bce9e44bd025cb88724df9a07a8deb3ae1c12e608195 and pinned
native source. No training, new weights, crops, ensembles, confidence search,
new RGB acquisition, holdout access, runtime promotion or board optimization.
The original 640x384 camera bytes stay fixed: larger model tensors interpolate
existing pixels and do not add sensor detail.

## Candidates and native contract

Compare square FP32/batch1 input640,960,1280, each a multiple of32. Reuse the
original640 ONNX SHA40097ba600ba21b94c673a76ff602ece600392fc1d9641576ff66bfa0300e1c2.
All use PIL RGB bilinear direct resize /255 and original[width,height]=[640,384],
full80-class native top300/noNMS then fixed target0/1/2/3/5/7 vector
[.60,.40,.70,.50,.50,.60]. Keep the0.35 decoder floor/capacity/error checks.

Load the unchanged checkpoint strictly at its native640 configuration using the
existing pinned inference-only builder. For960/1280 regenerate only native
encoder sine/cosine position caches and decoder anchors/valid masks for the
new spatial size. Verify every learned parameter and every other state tensor
is byte-identical. Vendor sources are unchanged. Compare each static cache path
against the native dynamic-shape evaluation path (eval_spatial_size=None) before
export. Record all state/cache/config/ONNX hashes, graph operators and shapes.

Use the first3 accepted V9 preparation-DEVELOPMENT frames as probes. Check
independent torchvision/PIL input bytes, native dynamic/static PyTorch, ORT CPU
and ORT CUDA full300 exact-class one-to-one unordered sets: box atol0.1pixel,
score atol1e-4; also fixed-vector complete detections. Nine resolution/probe
pairs are required. Preserve failures and do not relax tolerances. ORT1.23.2,
CUDA TF32 disabled, original2GiB arena limit, HEURISTIC and no CPU-node fallback.
No warmup/cold/init/error/late calls may be removed.

## Development split and selection

Use only allowlisted, already consumed DEVELOPMENT partitions. Selection is
V4/V5/V6/V7/V8 development81 each (405 unique frames/645 visible GT). After
sealing all selection scores and one nomination, evaluate every declared
resolution unchanged on the already consumed V9 development81 (129 GT) as a
regression, not an independent holdout. Never use any previous holdout RGB,
GT or prediction. Reject a non-development partition before reading RGB/GT.
The full486 development RGB and source seals must be distinct and unchanged.
Original S at confidence.35 uses its already archived development raw outputs;
re-decode all486 against the existing predictions and recompute strict scores.

Keep visible instance/Rider semantics and all original absolute quality limits:
P>=.85,R>=.8,every class R>=.7,near person R>=.9,negative FP/frame<=1/3 and no
model errors. Verify planned actor/Rider support per frame against sealed GT.
Use the full original S-relative rules: P gain>=.03, no overall/class/far/
occluded recall drop, near person TP drop or negative FP increase. Apply the
absolute gate to the combined405 and each of its five sites. A higher resolution
is eligible for a next fresh quality test only when it also has no precision,
class recall, near-person TP or negative-FP regression against the640 control.
These development gates do not qualify live20Hz or a board.

Nominate among960/1280 by: all eligibility gates, then combined absolute pass,
then macroF1, minimum class recall, microF1, and smaller input on a tie. Preserve
a descriptive nominee even if all fail, but mark fresh-test eligibility false.
The consumed V9 development check cannot reselect or change resolution/vector.
Require its absolute and full S-relative gates and the same640 nonregression
for final next-fresh-test eligibility. No automatic runtime adoption.

## Evidence and bounds

Cache every exported raw array and decoded prediction. Retain all errors and
full attempted/valid/<100ms admitted denominators; report initialization, stage
latency, cold-inclusive max/P95, peak RSS and input tensor bytes. Timing excludes
raw cache compression. Strict quality uses all valid calls and separately
reports admitted quality. Keep the full original S raw caches, RGB/seals,
references, candidate ONNX files and frozen sources in reproducible artifacts.
Audit every raw decode, score, selection and execution order from an isolated
archived source subprocess. Model-free preparation/future RGB exclusion remains
5449 because this experiment creates no new camera data.

Report per-size/per-person-kind and native top300 false-negative buckets as
diagnostics without changing GT, primary matching or selection. Each eventual
Thor/Orin deployment still runs the whole stack independently; no inference
cost, memory, TensorRT support or target quality is inferred from Host results.
