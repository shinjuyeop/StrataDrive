# Exact CUDA resize prospective comparison

This follows the 500us native service candidate. Keep its native binaries,
physical owner, source editor renderer, GC/cache policy, source clocks and all
expiry/watch checks. Change only the explicit inference preprocessing backend:
the original two integer bilinear passes run on CUDA, then return identical RGB
bytes to the existing CPU tensor conversion, image-health checks and D-FINE-M960.

- Freeze the CUDA source, compiler command, shared library and runtime hashes.
  Host SM86/PTX86 is an explicit RTX3090 build; each Jetson requires its own build
  and validation in M12. No CPU fallback on GPU failure.
- Retain 2560x1536 input, 960 model input, CV threads4, camera target10Hz,
  renderer target20Hz/MaxFPS60, owner4/image2 cores and bounded70% host lease.
  CUDA resize uses no CPU resize workers. One inference owner holds persistent
  buffers and waits on a blocking CUDA event. The borrowed RGB output is consumed
  before the next call. Shutdown waits for the owner before releasing buffers.
- Before live execution, require exact Pillow11.3.0 and original CPU RGB/tensor
  equality, CUDA memory/leak checks, and both actual model preparation paths.
  Keep original10s owner preparation and100ms settled-call limits. The initial
  preparation attempt that overlapped HDD archive reads failed its30s library
  read budget and remains retained; do not reinterpret it as a GPU failure/pass.
- Run30s, then300s only after the original short verdict passes. Preserve the
  first failure. Compare full measured scene-to-result latency, preprocessing,
  inference, CPU time, supply gaps and temperatures; offline speed is not live
  acceptance. Do not change thresholds or reuse development images as holdout.
- After live execution, seal raw archives with one source copy/hash pass into
  lossless gzip transport and an independent durable destination read/decode.
  Verify the entire expanded original tar, including headers/padding/footer,
  separately from the stored compressed hash. Original image names/bytes remain.
  Independent transport verification checks every tar byte/member and every
  stored/BGRA/RGB hash in one sequential pass. The frozen physical auditor also
  rechecks all image hashes; this separate audit read remains required. No sampling
  or frame deletion.
  The old and new checkers reproduced the same original281-frame short result;
  all original frozen physical audits remain required.
- Preserve exact native replay, original6000/60000 receipts, watch slots, runtime
  restoration and original asset inodes. Restore boost automatically. All images
  remain excluded from subsequent independent quality evaluation.

This comparison does not authorize incomplete visual scenes or convert diagnostic
images into ECU inputs. Same-frame complete visual state, typed native mapping,
fresh independent quality and full M10 acceptance remain separate requirements.
