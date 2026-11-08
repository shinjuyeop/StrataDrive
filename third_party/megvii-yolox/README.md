# Offline YOLOX-M candidate provenance

The M10 v3 experiment uses a separately pinned ONNX model from
[Megvii YOLOX release 0.1.1rc0](https://github.com/Megvii-BaseDetection/YOLOX/releases/tag/0.1.1rc0).
The tag resolves to `e1052df71842031413f6030723c3607b839c80ce`.

- [yolox_m.onnx](https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_m.onnx):
  101,259,744 bytes, SHA256 `21ff6cfdeb53b013bac2249599e55f00bff3cfdfdab37ed7a4620818c1d15b3f`.
- Apache-2.0; unchanged [LICENSE](LICENSE) from that commit.
- FP32 input `images` `[1,3,640,640]`, output `output` `[1,8400,85]`.
- Weights remain under ignored `build/`; no checkpoint deserialization or downloaded code execution.

This comparison explicitly retains the existing OpenCV Zoo RGB 0–255 top-left
letterbox114 preprocessing and class-aware decode/NMS. The S release asset has
the exact same bytes as the pinned Zoo S model. The release tag's old Python
normalization instructions differ from the Zoo demo. A normalized S diagnostic
on consumed development data produced zero detections; it was rejected and is
retained as a diagnostic, not a new acceptance result. M's numeric CPU/CUDA and
OpenCV comparison is recorded separately. Cross-runtime equivalence verifies
the specified tensor/decoder, not CARLA accuracy or training provenance.

The upstream [Zoo demo at its pinned revision](https://github.com/opencv/opencv_zoo/blob/a74cdfad334b102cbd8daed769fbe1d4cb1c327a/models/object_detection_yolox/demo.py)
defines the RGB tensor policy. V3 declares that policy before fresh evaluation.
The model and offline result retain their own SHA identity and cannot satisfy
the v1 C++ model contract by relabeling M as S.
