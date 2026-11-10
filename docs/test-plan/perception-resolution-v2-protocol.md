# M10 resolution V2: numerically valid640/960 subset, before quality inference

The original V1 three-size study remains FAIL: original640 regenerated-cache
reference was not its checkpoint-cached control, high-resolution full300 checks
failed, ORT_DISABLE_ALL cannot keep CPU-node fallback disabled, and BASIC still
fails1280 probe1. Preserve all original frozen sources, artifacts and failures.
No development quality inference/nomination has taken place in V1.

Start a separately frozen V2 comparison using ONLY original640 and existing960
ONNX artifacts. Both have already passed every declared probe with BASIC graph
optimization. Exclude1280 on numerical evidence alone; do not run1280 quality,
change its thresholds or relax any tolerance. Keep FP32/batch1, TF32off,2GiB,
HEURISTIC, no CPU fallback and full300 class/box0.1/score1e-4 checks.

The original640 reference must retain checkpoint-saved native anchor values.
The saved float32 anchor buffer differs from CPU-native regeneration by up to
0.00020182132720947266; this changes some low-confidence scores. The corrected
native checkpoint path agrees with all three archived V9 upstream references.
Do not claim cache regeneration is byte-identical to the stored640 cache.
960 uses the already exported native spatial960 position/anchor caches; learned
parameters and other state tensors remain unchanged. Independent native dynamic
960/static960 agreement and exact RGB/preprocessing checks are retained.

Create new versioned V2 backend/common/run/numeric/audit/test files and freeze
them plus this protocol, the existing models, all original numerical failures,
corrected references and the prior allowed development inputs before V2 quality
inference. Recheck all six size/probe pairs in the new backend. Both must pass.

Retain ALL V1 development, quality, per-site, full S-relative and640-control
nonregression rules unchanged. Use V4-V8 development405 for the single960
nomination and seal it before consumed V9 development81. Nomination is only
eligible when all original gates pass; report a descriptive failed nominee
otherwise. V9 regression cannot reselect. No prior holdout access, new camera
RGB, confidence search, training, runtime/vehicle publication, Jetson execution
or board optimization. The future RGB exclusion remains5449.

Publish the original V1 numerical FAIL alongside V2 results. Replay every V2
model raw (972), original S raw (486), GT/score/selection/order and all manifests
from archived fresh sources. V2 is consumed-development research, not fresh
quality acceptance or whole-wall20Hz qualification.
