# NanoDet-Plus-1.5x416 pretrained screening provenance

The unchanged official [OpenCV Zoo directory](https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/object_detection_nanodet)
at revision `48b10fa505aeb51fbd127fc60a5c660040e823b7` supplies the FP32 ONNX, reference
decoder/demo and Apache-2.0 LICENSE. This is a different lightweight detector family for the
development screen, not a claim that it will outperform newer or larger models.

Official [model](https://media.githubusercontent.com/media/opencv/opencv_zoo/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/object_detection_nanodet/object_detection_nanodet_2022nov.onnx):
3,800,954 bytes, SHA256 `4b82da9944b88577175ee23a459dce2e26e6e4be573def65b1055dc2d9720186`.
RGB INTER_AREA centered zero letterbox416, official channel mean/std, distributional regression,
top1000 per feature level and class-agnostic NMS.6 are preserved.6class filtering happens after NMS.
Float coordinates are retained rather than truncating to display pixels. Numeric checks compare
the independent official OpenCV implementation as well as ORT CPU/CUDA.

The original graph exposes weights as overridable initializer inputs and triggers ORT warnings;
the model bytes are preserved. The wrapper feeds only the image input and does not override weights.
No graph simplification, quantization or Jetson engine optimization is performed.
Jetson/TensorRT compatibility and performance remain unverified.
