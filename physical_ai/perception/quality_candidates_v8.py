"""Fixed official L full-view candidate on fresh Town04; offline only."""

from dataclasses import dataclass

from .contract import FrameIdentity, Detection, MODEL_SHA256, uint
from .large_model_v6 import LargeYoloX, LARGE_SHA256
from .yolox import YoloX

CANDIDATES = ("baseline", "large-v8")
MODELS = {"baseline": MODEL_SHA256, "large-v8": LARGE_SHA256}
INPUT_PROFILE = "rgb-unscaled-letterbox640-v1"
POLICY = dict(
    score_threshold=0.35, same_class_nms_iou=0.5, output_channels=85, crop=False
)


@dataclass(frozen=True)
class OfflineResultV8:
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
            raise ValueError("v8 offline envelope")
        for detection in self.detections:
            detection.validate()


class QualityCandidateV8:
    def __init__(self, model, candidate, execution="cuda"):
        if candidate not in CANDIDATES:
            raise ValueError("unknown v8 candidate")
        self.candidate = candidate
        self.detector = (
            YoloX(model, execution)
            if candidate == "baseline"
            else LargeYoloX(model, execution)
        )

    def infer(self, frame):
        r = self.detector.infer(frame)
        result = OfflineResultV8(
            r.identity,
            r.detections,
            r.preprocess_ns,
            r.inference_ns,
            r.postprocess_ns,
            MODELS[self.candidate],
        )
        result.validate()
        return result
