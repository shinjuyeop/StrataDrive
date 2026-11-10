# M10 resolution car-confidence V1: one development-informed revision

Declare before rescoring any revised vector. Preserve resolution V1 numerical
FAIL and resolution V2 final rejection:960 passed the original S-relative and
absolute gates on405 and81 but regressed car recall32/33->31/33 versus640 on
consumed V9 development. Its original decision must not be changed.

Use the same pinned960 ONNX/native FP32/BASIC/no-fallback backend and original
RGB. Make exactly one already-in-grid change: class2 confidence.70->.60. Keep
person/bicycle/motorcycle/bus/truck at.60/.40/.50/.50/.60, native top300/noNMS,
0.35 floor and all original overflow/output checks. No search, new weights,
training, new RGB, previous holdout access, runtime or board work.

The change is informed by V9 DEVELOPMENT false-negative analysis. All486 old
development frames are now design data, including V9's81: do not describe the
V9 check as blind, independent or held out for this revision. Re-score405,
V9 development81 and combined486. Require the original absolute and full
S-relative gates, every site's absolute gate, and640 precision/class/near-person/
negative nonregression separately for405 and81. Do not relax a gate after results.

Before quality rescoring, freeze source/policy/parent reports and all native
raw inputs. Verify3 preparation-development probes of the960 model against
native PyTorch and ORT CPU/CUDA, full300 exact-class box.1pixel/score1e-4 and
complete revised-vector detections. Preserve all old numeric failures.

Re-decode all486960 raw outputs, first prove exact equality with the original
V2 vector/JSON, then derive the one revised vector. Reuse sealed GT/primary
matching unchanged. Report original model run timing as context only; replayed
confidence filtering does not qualify a new deadline or live performance.

Only when all gates pass may a derived offline profile be fixed for a NEXT
fresh development AND holdout acquisition. Current old development scores do
not replace that fresh test or authorize runtime promotion. No previous
holdout may guide the revision or serve as its acceptance. Future RGB exclusion
remains5449. Recheck all parent raw/score/order and the derived scores from a
fresh archived source subprocess, including original failures and source freezes.
