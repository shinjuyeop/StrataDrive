# V1 diagnostic annex: three V4 development background regions

The first frozen geometric analysis found95 of D-FINE's98 calibration FP with
no positive IoU≥0.1 on V4. Visual RGB alone cannot distinguish a simulator label
gap from an appearance false positive. Before reading instance pixels, fix this
read-only annex to the three previously selected deterministic FP cases:
`dfine-car-no-positive`, `dfine-person-no-positive`,
`rtv4-person-no-positive` in the diagnostic `visual-cases.json`.

Use only `build/m10-quality-v4g/development-01/dataset/capture.json`, whose SHA256
is `e4cb5fbcc3e075582d0d252223f2872613223e9aa702089a19588b0630739667`,
and the matching three RGB/instance BGRA pairs. Require development partition,
evaluation phase, exact scene/frame/source time and manifest hashes; reconstruct
RGB bytes and match the already sealed development RGB hashes. Rebuild the
entire frame GT with the existing `visible_boxes_v2` and require exact equality
with sealed GT before interpreting the ROI.

Report semantic-tag pixel histograms inside the prediction rectangle using
floor(x1/y1), ceil(x2/y2), clipped to640×384. Bind the source SDK `ObjectLabel.h`
enum bytes and names to an annex freeze. Preserve all three raw pairs and ROI
identities for archived replay. Include the native and expected target tags;
the annotation still uses its existing semantic policy.

This annex neither relabels map objects nor removes FP. A non-target simulator
tag and a car-like or person-like RGB appearance may reveal an evaluation-scope
limitation; three visual examples do not prove the physical semantic identity
of every background FP. Keep geometric counts and V2 scores unchanged. No
holdout data, new capture, neural inference, training or board work is involved.
