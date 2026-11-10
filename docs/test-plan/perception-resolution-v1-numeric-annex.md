# Resolution V1 numeric investigation: cached640 control and two bounded ORT profiles

The original467-source freeze, exports, references, numeric FAIL and diagnostic
remain unchanged. No development quality inference or selection has started.
The9-probe diagnostic found the original640 ONNX still agrees with its earlier
V9 upstream reference, while regenerated640 native caches differ in some low
scores. Investigate the checkpoint-cached native640 path separately; the640
control must preserve that path because its ONNX is unchanged. The original
regenerated reference must not be presented as that control's valid reference.

For960/1280 the static exports agree with the native dynamic evaluation path,
but a few full300 low-confidence boxes exceed the existing0.1pixel bound across
CPU/CUDA. Do not remove any proposal, raise confidence or relax box/score limits.

Before further inference, freeze this annex and its helper with all original
inputs/results. Recompute only the correct original cached640 reference from
unchanged strict checkpoint/native source and compare against all3 frozen V9
preparation-development upstream probes. Record checkpoint/cache dtypes, shapes
and differences from native regeneration plus complete nongeometric state hashes.

Test at most two ONNX Runtime graph settings in this order: ORT_DISABLE_ALL,
ORT_ENABLE_BASIC. Everything else stays fixed (FP32, TF32off,2GiB arena, no CPU
fallback, HEURISTIC, exact RGB/probe bytes). Run all9 size/probe pairs per profile,
including failures, against cached640/native-dynamic960/1280 and CPU/CUDA.
Require exact class/full300 bijection, box0.1pixel/score1e-4 and complete fixed
vector detections. Choose the first fully passing profile without using GT or
quality scores. Preserve all failed settings. This is numeric correctness work,
not board optimization or accuracy-driven selection.

A passing profile requires new versioned backend/run/common sources and a new
pre-quality source freeze; the original V1 source must remain byte-identical.
A failed investigation cannot authorize development quality runs. No holdout,
training, new RGB, model score/weights tuning or runtime promotion is permitted.
