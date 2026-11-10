"""Fixed D-FINE input-resolution experiment; offline only, never publication."""

from pathlib import Path
import numpy as np
from PIL import Image
from .class_calibration_v1 import decode as decode_vector
from .contract import execution_profile, sha256_file
from .dataset import read_json
from .yolox import image_health

SIZES = (640, 960, 1280)
VECTOR = (0.6, 0.4, 0.7, 0.5, 0.5, 0.6)
CHECKPOINT_SHA = "b44a7586bf490858c7b8bce9e44bd025cb88724df9a07a8deb3ae1c12e608195"
ORIGINAL_ONNX_SHA = "40097ba600ba21b94c673a76ff602ece600392fc1d9641576ff66bfa0300e1c2"


def validate_size(size):
    if type(size) is not int or size not in SIZES:
        raise ValueError("undeclared resolution")


def prepare_rgb(rgb, size):
    validate_size(size)
    if rgb.dtype != np.uint8 or rgb.shape != (384, 640, 3):
        raise ValueError("original RGB640x384 bytes required")
    resized = Image.fromarray(rgb).resize((size, size), Image.Resampling.BILINEAR)
    tensor = np.asarray(resized, np.float32).transpose(2, 0, 1)[None] / 255.0
    return dict(
        images=np.ascontiguousarray(tensor),
        orig_target_sizes=np.array([[640, 384]], np.int64),
    )


def decode(raw):
    return decode_vector(raw, VECTOR)


class ResolutionDetector:
    def __init__(self, size, model, manifest, execution="cuda"):
        import onnxruntime as ort

        validate_size(size)
        spec = read_json(manifest)["models"][str(size)]
        if (
            spec["size"] != size
            or sha256_file(model) != spec["sha256"]
            or Path(model).stat().st_size != spec["bytes"]
        ):
            raise ValueError("resolution model identity")
        settings = execution_profile(execution)
        if ort.__version__ != "1.23.2":
            raise ValueError("pinned ORT")
        options = ort.SessionOptions()
        options.intra_op_num_threads, options.inter_op_num_threads = 4, 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        providers = ["CPUExecutionProvider"]
        if settings is not None:
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
            str(model), sess_options=options, providers=providers
        )
        self.session.disable_fallback()
        actual = self.session.get_provider_options().get("CUDAExecutionProvider", {})
        if settings is not None:
            if self.session.get_providers()[0] != "CUDAExecutionProvider" or any(
                actual.get(k) != settings[k]
                for k in (
                    "device_id",
                    "use_tf32",
                    "cudnn_conv_algo_search",
                    "gpu_mem_limit",
                )
            ):
                raise ValueError("CUDA settings/fallback")
        elif self.session.get_providers() != ["CPUExecutionProvider"]:
            raise ValueError("CPU provider")
        expected_inputs = [
            ("images", [1, 3, size, size], "tensor(float)"),
            ("orig_target_sizes", [1, 2], "tensor(int64)"),
        ]
        expected_outputs = [
            ("labels", [1, 300], "tensor(int64)"),
            ("boxes", [1, 300, 4], "tensor(float)"),
            ("scores", [1, 300], "tensor(float)"),
        ]
        for values, expected in [
            (self.session.get_inputs(), expected_inputs),
            (self.session.get_outputs(), expected_outputs),
        ]:
            if [(v.name, v.shape, v.type) for v in values] != expected:
                raise ValueError("native resolution tensor contract")
        self.size = size

    def prepare(self, frame):
        image_health(frame)
        return prepare_rgb(
            np.frombuffer(frame.rgb, np.uint8).reshape(384, 640, 3), self.size
        )

    def raw(self, feed):
        return dict(
            zip(
                (v.name for v in self.session.get_outputs()),
                self.session.run(None, feed),
            )
        )
