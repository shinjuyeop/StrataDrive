# YOLOX model provenance

The optional M10 host profile downloads the **YOLOX-S FP32** model from
[OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/a74cdfad334b102cbd8daed769fbe1d4cb1c327a/models/object_detection_yolox),
revision `a74cdfad334b102cbd8daed769fbe1d4cb1c327a`.

- File: `object_detection_yolox_2022nov.onnx`, 35,858,002 bytes.
- SHA256: `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`.
- Directory license: Apache-2.0, copied without changes to [LICENSE](LICENSE).
- The upstream directory credits Sri Siddarth Chakaravarthy, Google Summer of Code 2022 / OpenCV.
- The original training implementation is [Megvii YOLOX](https://github.com/Megvii-BaseDetection/YOLOX).

Weights are downloaded only by an explicit command and are not committed to this repository.
StrataDrive's adapter implements the documented RGB letterbox/YOLOX grid decode contract;
it does not execute downloaded Python or unpickle a checkpoint. The model is pretrained on
COCO; no local training, CARLA accuracy guarantee, or collision probability is implied.
The model does not produce localization, depth, drivable area, or vehicle commands.
