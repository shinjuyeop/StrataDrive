# M10 class confidence calibration V1

Predeclare this development experiment after the frozen diagnostic V1 and before
computing any mixed class-threshold result. It tests a concrete hypothesis:
RT-DETRv4's person/bicycle recall and D-FINE's background FP require different
class operating points. Keep official pretrained weights, native RGB preparation,
FP32/batch1/640, full80-class native top300 and noNMS unchanged. No training,
new RGB, holdout, crop/ensemble, engine, Jetson execution or runtime promotion.

## Selection

For D-FINE-M and RT-DETRv4-S independently enumerate all5⁶=15,625 vectors using
class order0/1/2/3/5/7 and thresholds0.35/0.40/0.50/0.60/0.70. Fit on the same
sealed V2 development324 frames only. Never lower the existing runtime floor0.35.
Retain all scorecards, counts and gate results, including every failure.

Sort by the following descending key: all absolute AND relative gates pass;
all absolute gates pass; macro F1; minimum class recall; micro F1; higher
threshold vector lexicographically in the fixed class order. Relative comparison
uses the original S at common0.35, not its recalibrated0.40 setting. No gate is
relaxed: P≥85%, R≥80%, class R≥70%, near-person R≥90%, negative FP/frame≤1/3,
no model errors; P/R improvement≥3 percentage points and no class recall drop.

DETR's existing class-exact matching and lack of inter-class NMS permit exact
class-wise composition of per-threshold TP/FP/FN, negative FP and near-person
counts. Verify this separability against direct raw decoding and the original
scorer on every selected calibration frame. All mixed outputs are subsets of
the original valid0.35 target list; verify the native list capacity first.

Seal both winners and the complete search results before running the Town04
development regression. That81-frame set was already consumed in V2 and the
diagnostic V1, so this is descriptive regression, not an unseen check or fresh
acceptance. Do not retune after it. Report absolute and relative failures.

## Provenance and numerical checks

Bind the V2 freeze/registry/selection/run/raw/data seals, diagnostic report, this
protocol, grid profile and new source/tests before fitting. Add new derived
candidate profile identities with checkpoint/ONNX/preprocess hash, class vector,
selection hash and runtime_promotion=false; never overwrite a prior profile.

Use the same3 V7 preparation-development probes and admitted upstream PyTorch
raw references as V2. Check ORT CPU/CUDA native full300 sets (exact class,
box≤0.1px, score≤1e-4), all5 scalar operating points and the chosen mixed vector.
Preprocessing must match the V2 reference. Record6 model/probe outcomes before
Town04 regression. No tolerance change is permitted based on results.

Validate finite/shape/probability/box/capacity failures even for low-score rows.
Replay all selected calibration/regression predictions and primary scores from
raw caches in an archived fresh-source subprocess, and recompute all31,250
scorecards and both selections. Tests must exercise class independence despite
Rider overlap, floor/vector validation, ranking priority and failure counting.

The resulting configuration is a provisional development candidate. Retain
V2 scalar results, all previous holdout failures and original S runtime. A new
quality protocol and newly acquired holdout remain mandatory for final adoption.
Each eventual Thor/Orin deployment still runs the complete stack independently;
board optimization follows deployment and measurement.
