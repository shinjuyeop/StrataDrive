"""Offline pinned YOLOX-M comparison. No v1 runtime or vehicle publication."""

from dataclasses import dataclass, replace
import hashlib
import time
import cv2
import numpy as np

from .contract import (
    FrameIdentity,
    Detection,
    MODEL_SHA256,
    execution_profile,
    uint,
)
from .quality_candidates import merge, restore_crop
from .yolox import YoloX, image_health, preprocess, postprocess

MEDIUM_SHA256 = "21ff6cfdeb53b013bac2249599e55f00bff3cfdfdab37ed7a4620818c1d15b3f"
MEDIUM_BYTES = 101259744
CANDIDATES = ("baseline", "medium-v3", "medium-refine-v3")
MODELS = {c: MODEL_SHA256 if c == "baseline" else MEDIUM_SHA256 for c in CANDIDATES}
INPUT_PROFILE = "rgb-unscaled-letterbox640-v1"


@dataclass(frozen=True)
class OfflineResult:
    identity: FrameIdentity
    detections: tuple[Detection, ...]
    preprocess_ns: int
    inference_ns: int
    postprocess_ns: int
    model_sha256: str
    input_profile: str = INPUT_PROFILE

    @property
    def expires_ns(self):
        return self.identity.source_ns + 100_000_000

    def validate(self):
        if type(self.identity) is not FrameIdentity:
            raise ValueError("offline identity type")
        self.identity.validate()
        if (
            self.model_sha256 not in (MODEL_SHA256, MEDIUM_SHA256)
            or self.input_profile != INPUT_PROFILE
            or type(self.detections) is not tuple
            or len(self.detections) > 100
            or not all(
                uint(v)
                for v in (self.preprocess_ns, self.inference_ns, self.postprocess_ns)
            )
        ):
            raise ValueError("offline result envelope")
        for d in self.detections:
            d.validate()


class MediumYoloX:
    def __init__(self, model, execution="cuda"):
        import onnxruntime as ort

        settings = execution_profile(execution)
        data = model.read_bytes()
        if (
            len(data) != MEDIUM_BYTES
            or hashlib.sha256(data).hexdigest() != MEDIUM_SHA256
        ):
            raise ValueError("pinned medium model identity")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        providers = ["CPUExecutionProvider"]
        if settings is not None:
            if (
                ort.__version__ != "1.23.2"
                or "CUDAExecutionProvider" not in ort.get_available_providers()
            ):
                raise ValueError("pinned CUDA unavailable")
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
        actual = self.session.get_providers()
        if execution == "cpu" and actual != ["CPUExecutionProvider"]:
            raise ValueError("unexpected CPU provider")
        if settings is not None:
            applied = self.session.get_provider_options().get(
                "CUDAExecutionProvider", {}
            )
            if actual[0] != "CUDAExecutionProvider" or any(
                applied.get(k) != settings[k]
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
            != ("output", "tensor(float)", [1, 8400, 85])
        ):
            raise ValueError("medium tensor contract")

    def infer(self, frame):
        start = time.monotonic_ns()
        image_health(frame)
        tensor, ratio = preprocess(frame)
        prepared = time.monotonic_ns()
        raw = self.session.run(["output"], {"images": tensor})[0]
        inferred = time.monotonic_ns()
        detections = postprocess(raw, ratio)
        end = time.monotonic_ns()
        result = OfflineResult(
            frame.identity,
            detections,
            prepared - start,
            inferred - prepared,
            end - inferred,
            MEDIUM_SHA256,
        )
        result.validate()
        return result


class QualityCandidateV3:
    def __init__(self, model, candidate):
        if candidate not in CANDIDATES:
            raise ValueError("unknown v3 candidate")
        self.candidate = candidate
        self.detector = (
            YoloX(model, "cuda") if candidate == "baseline" else MediumYoloX(model)
        )

    def infer(self, frame):
        base = self.detector.infer(frame)
        if self.candidate != "medium-refine-v3":
            return OfflineResult(
                base.identity,
                base.detections,
                base.preprocess_ns,
                base.inference_ns,
                base.postprocess_ns,
                MODELS[self.candidate],
            )
        start = time.monotonic_ns()
        pixels = np.frombuffer(frame.rgb, np.uint8).reshape(384, 640, 3)
        enlarged = cv2.resize(
            pixels[96:288, 160:480], (640, 384), interpolation=cv2.INTER_LINEAR
        )
        resize_ns = time.monotonic_ns() - start
        crop = self.detector.infer(replace(frame, rgb=enlarged.tobytes()))
        start = time.monotonic_ns()
        boxes = merge(
            base.detections + restore_crop(crop.detections), vehicle_nms=False
        )
        result = OfflineResult(
            frame.identity,
            boxes,
            base.preprocess_ns + crop.preprocess_ns + resize_ns,
            base.inference_ns + crop.inference_ns,
            base.postprocess_ns + crop.postprocess_ns + time.monotonic_ns() - start,
            MEDIUM_SHA256,
        )
        result.validate()
        return result
