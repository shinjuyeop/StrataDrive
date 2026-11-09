# Offline YOLOX-L candidate provenance

M10 V6 uses the official [YOLOX 0.1.1rc0 release](https://github.com/Megvii-BaseDetection/YOLOX/releases/tag/0.1.1rc0),
whose tag commit is `e1052df71842031413f6030723c3607b839c80ce`.
The [official ONNX model table](https://github.com/Megvii-BaseDetection/YOLOX/blob/0.1.1rc0/demo/ONNXRuntime/README.md)
identifies the L architecture. The downloaded release asset is
[`yolox_l.onnx`](https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_l.onnx),
216,746,733 bytes, SHA256 `7860ae79de6c89a3c1eb72ae9a2756c0ccfbe04b7791bb5880afabd97855a411`.
It is not a model retrained on CARLA. Weights remain under ignored `build/` and are not in the evidence archive.
No downloaded Python or checkpoint deserialization is executed.

The unchanged Apache-2.0 [LICENSE](LICENSE) is retained from the pinned YOLOX source.
The FP32 contract is `images [1,3,640,640]` -> `output [1,8400,85]`.
V6 explicitly uses the same RGB0–255/top-left letterbox114 policy as the existing S/M experiments.
Independent tensor and CPU/CUDA/OpenCV output comparison verifies this specified implementation,
not detection quality or generalization. L has its own model identity and offline envelope;
it cannot be published as the S v1 C++ contract or M envelope.
