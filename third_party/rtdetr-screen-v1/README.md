# RT-DETRv2-R18 pretrained screening provenance

Inference modules/configs and LICENSE are copied byte-for-byte from
[lyuwenyu/RT-DETR](https://github.com/lyuwenyu/RT-DETR/tree/df2a96c8c3a098567a1149bf0248da6efe6d495d),
revision `df2a96c8c3a098567a1149bf0248da6efe6d495d`. See [sources.json](sources.json).
Apache-2.0 applies; upstream notices remain intact. No setup script or training entry point runs.
The local factory loads only these modules using isolated package namespaces and instantiates the
merged official R18 config; every checkpoint tensor is strict-loaded without local training.

Official [checkpoint](https://github.com/lyuwenyu/storage/releases/download/v0.2/rtdetrv2_r18vd_120e_coco_rerun_48.1.pth):
81,198,974 bytes, SHA256 `2ace52184b620204004509b72752ac7bfe64aadaf7fc1d076b18df8ab5a5c77e`.
It is hashed before `torch.load(..., weights_only=True)`. The checkpoint's EMA model is used.
The initial attempt at the old v0.1 URL returned404; no checkpoint was loaded from that URL.

The unchanged official deploy/postprocessor logic is exported to fixed batch1 ONNX opset16 FP32,
RGB PIL bilinear direct640 resize and0–1 input. `orig_target_sizes` is `[width,height]`.
Labels are contiguous COCO80 positions; only native0/1/2/3/5/7 pass the common screen filter.
Top300/no-NMS is retained. The fixed export is documented in the screening registry/evidence.
Official example throughput is not a measurement on our Host or either Jetson.

ONNX uses standard GridSample and other standard-domain operators. That is a deployment route,
not confirmation of TensorRT import, board compatibility, numerical accuracy or real-time behavior.
Board engine construction and optimization remain deferred as requested.
