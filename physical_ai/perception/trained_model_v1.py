"""Manifest-bound offline L6 ONNX inference; no runtime publication envelope."""

import hashlib
import json
from pathlib import Path
import numpy as np
from .contract import execution_profile
from .training_v1 import HEAD_TO_NATIVE, decode_six, pack_sample


class TrainedOnnxV1:
    def __init__(self, path, manifest, execution="cpu"):
        import onnxruntime as ort

        m = json.loads(Path(manifest).read_text())
        data = Path(path).read_bytes()
        if (
            m["schema"] != "m10-trained-model-v1"
            or m["architecture"] != "YOLOX-L-six-class"
            or m["head_to_native"] != list(HEAD_TO_NATIVE)
            or m["input"] != [1, 3, 640, 640]
            or m["output"] != [1, 8400, 11]
            or m["input_profile"] != "rgb-unscaled-letterbox640-v1"
            or m["runtime_promotion"] is not False
            or len(data) != m["model_bytes"]
            or hashlib.sha256(data).hexdigest() != m["model_sha256"]
        ):
            raise ValueError("trained model identity/contract")
        settings = execution_profile(execution)
        options = ort.SessionOptions()
        options.intra_op_num_threads, options.inter_op_num_threads = 4, 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        providers = ["CPUExecutionProvider"]
        if settings is not None:
            if (
                ort.__version__ != "1.23.2"
                or "CUDAExecutionProvider" not in ort.get_available_providers()
            ):
                raise ValueError("pinned CUDA provider unavailable")
            ort.preload_dlls(directory="")
            options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
            providers = [
                (
                    "CUDAExecutionProvider",
                    {
                        k: settings[k]
                        for k in (
                            "device_id",
                            "use_tf32",
                            "cudnn_conv_algo_search",
                            "gpu_mem_limit",
                        )
                    },
                )
            ]
        self.session = ort.InferenceSession(
            data, sess_options=options, providers=providers
        )
        self.session.disable_fallback()
        if execution == "cpu" and self.session.get_providers() != [
            "CPUExecutionProvider"
        ]:
            raise ValueError("unexpected CPU provider")
        if settings is not None:
            actual = self.session.get_provider_options().get(
                "CUDAExecutionProvider", {}
            )
            if self.session.get_providers()[0] != "CUDAExecutionProvider" or any(
                actual.get(k) != settings[k]
                for k in (
                    "device_id",
                    "use_tf32",
                    "cudnn_conv_algo_search",
                    "gpu_mem_limit",
                )
            ):
                raise ValueError("CUDA settings not applied")
        inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
        if (
            len(inputs) != 1
            or len(outputs) != 1
            or (inputs[0].name, inputs[0].type, inputs[0].shape)
            != ("images", "tensor(float)", [1, 3, 640, 640])
            or (outputs[0].name, outputs[0].type, outputs[0].shape)
            != ("output", "tensor(float)", [1, 8400, 11])
        ):
            raise ValueError("trained tensor contract")
        self.manifest = m

    def raw(self, rgb):
        tensor, _ = pack_sample(rgb, [])
        raw = self.session.run(["output"], {"images": tensor[None]})[0]
        if raw.dtype != np.float32 or raw.shape != (1, 8400, 11):
            raise ValueError("trained raw output contract")
        return raw

    def infer_rgb(self, rgb):
        return decode_six(self.raw(rgb))
