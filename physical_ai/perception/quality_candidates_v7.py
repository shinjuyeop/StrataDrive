"""Pinned trained L6, raw full view only; never publishes a runtime envelope."""

from dataclasses import dataclass
from pathlib import Path
import time

from .contract import FrameIdentity, Detection, MODEL_SHA256, uint, sha256_file
from .trained_model_v1 import TrainedOnnxV1
from .training_v1 import decode_six
from .yolox import YoloX, image_health, preprocess

TRAINED_SHA256 = "d264c01b4c797108db754e6d2193ad0b42e9cb012e06c3ae1c0e99521f9fa98e"
TRAINED_BYTES = 216580439
MANIFEST = (
    Path(__file__).resolve().parents[2] / "profiles/perception-trained-model-v1.json"
)
CANDIDATES = ("baseline", "trained-v1")
MODELS = dict(baseline=MODEL_SHA256, **{"trained-v1": TRAINED_SHA256})
INPUT_PROFILE = "rgb-unscaled-letterbox640-v1"
POLICY = dict(
    score_threshold=0.35,
    same_class_nms_iou=0.5,
    head_to_native=[0, 1, 2, 3, 5, 7],
    output_channels=11,
    crop=False,
)


@dataclass(frozen=True)
class OfflineResultV7:
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
            self.model_sha256 not in MODELS.values()
            or self.input_profile != INPUT_PROFILE
            or type(self.detections) is not tuple
            or len(self.detections) > 100
            or not all(
                uint(v)
                for v in (self.preprocess_ns, self.inference_ns, self.postprocess_ns)
            )
        ):
            raise ValueError("v7 offline envelope")
        for detection in self.detections:
            detection.validate()


class QualityCandidateV7:
    def __init__(self, model, candidate, execution="cuda"):
        if candidate not in CANDIDATES:
            raise ValueError("unknown v7 candidate")
        self.candidate = candidate
        if candidate == "baseline":
            self.detector = YoloX(model, execution)
        else:
            if (
                model.stat().st_size != TRAINED_BYTES
                or sha256_file(model) != TRAINED_SHA256
            ):
                raise ValueError("pinned trained model identity")
            self.detector = TrainedOnnxV1(model, MANIFEST, execution)
            if self.detector.manifest["model_sha256"] != TRAINED_SHA256:
                raise ValueError("pinned manifest identity")

    def infer(self, frame):
        if self.candidate == "baseline":
            r = self.detector.infer(frame)
            result = OfflineResultV7(
                r.identity,
                r.detections,
                r.preprocess_ns,
                r.inference_ns,
                r.postprocess_ns,
                MODELS[self.candidate],
            )
        else:
            start = time.monotonic_ns()
            image_health(frame)
            tensor, _ = preprocess(frame)
            prepared = time.monotonic_ns()
            raw = self.detector.session.run(["output"], {"images": tensor})[0]
            inferred = time.monotonic_ns()
            detections = decode_six(raw)
            complete = time.monotonic_ns()
            result = OfflineResultV7(
                frame.identity,
                detections,
                prepared - start,
                inferred - prepared,
                complete - inferred,
                TRAINED_SHA256,
            )
        result.validate()
        return result
