# YOLOX training source v1

Unchanged `yolox/__init__.py`, `models/`, `utils/`, and Apache-2.0 LICENSE from
[official YOLOX source](https://github.com/Megvii-BaseDetection/YOLOX/tree/e1052df71842031413f6030723c3607b839c80ce),
commit `e1052df71842031413f6030723c3607b839c80ce` (0.1.1rc0). `sources.json` hashes every copied byte.
Training dependencies are isolated in `build/m10-training-v1/venv`. No setup.py or compiled extension is used.

The official `yolox_l.pth` release asset is 434357141 bytes, SHA256
`1e6b7fa6240375370b2a8a8eab9066b3cdd43fd1d0bfa8d2027fd3a51def2917`.
It is loaded with `torch.load(..., weights_only=True)` after byte/hash verification.
The training adaptor explicitly transplants classifier rows [0,1,2,3,5,7] into a six-class head;
all remaining pretrained tensors load strictly. The exported model has its own manifest and
`[1,8400,11]` output contract; it cannot be substituted for an existing 80-class runtime.

Upstream losses/SimOTA are unchanged. RGB input, labels, optimizer, frozen BN statistics,
selection, and offline export policy are declared in the project training protocol.
