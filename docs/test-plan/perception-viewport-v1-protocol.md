# Separate off-screen main viewport cost, V1

Append to the595-file immutable frame-copy revision. Its two prefault runs reduce
copy time, but camera wall rate and capture-to-result latency remain limited. The
server still renders a separate856×640 main viewport while the camera sensor itself
renders3840×2304. Test whether reducing only this unused view reduces shared-GPU
work. Do not reduce the sensor image size or model input.

Run viewport-small-01 then viewport-small-02 in isolated servers. Add ResX=128,
ResY=128, ForceRes and windowed to the same RenderOffScreen/Epic invocation. Require
an actual128×128 initial render-target allocation before camera capture in the log.
The sensor must still read back3840×2304 BGRA/Epic/postprocessing/FOV90. Compare
against the frozen copy-prefault-01/02; all remaining controls are identical:
blocking-query GPU readback, largest-request scene targets2/1, finite120 independent
prefaulted immutable bytes, staged exact native/Pillow preprocessing and same
D-FINE-M960 FP32/thresholds. The main viewport may influence global rendering work;
no image-quality equivalence or new detection accuracy is assumed or scored.

Keep actual asynchronous state snapshots, fixed10ms physics, frame%5 camera,
original source+100ms AND original offer-receipt+100ms exclusive, state-age100ms,
active1/pendinglatest1/current1. Do not add a hidden FPS cap or alter simulation
clock to make deadlines pass. Report simulation/wall ratio even if greater than1.
The target is real-time1×, not deliberate slowdown or unconstrained faster playback.

Same500..504-frame windows,300ms silence tail,180/900/30s lifecycle budgets, exit130,
one attempt per condition and at most one prospectively recorded startup-only
recovery before any client. Keep all failed attempts and received raw images,
including rejected/boundary images. Source freeze and acceptance do not change after
observing results. No GT/old holdout, board optimization, ROS/vehicle integration or
runtime promotion. Archive all raw payloads, exact input hashes and cumulative
future exclusions after the prior frame-copy300 images; restore the original CARLA
module. Short trials distinguish component costs, not long-term qualification.
