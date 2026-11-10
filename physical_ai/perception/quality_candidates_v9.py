"""Fixed S and pretrained D-FINE class-v1; offline envelopes, never publication."""

from dataclasses import dataclass
from pathlib import Path
import time

from .class_calibration_v1 import decode as decode_dfine
from .contract import Detection, FrameIdentity, MODEL_SHA256, sha256_file, uint
from .dataset import read_json
from .model_screen_v2 import ScreenDetector
from .yolox import YoloX, image_health, postprocess, preprocess

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "profiles/perception-class-calibration-candidates-v1.json"
CANDIDATE = "dfine-m-class-v1"
CANDIDATES = ("baseline", CANDIDATE)
MODELS = {
    "baseline": MODEL_SHA256,
    CANDIDATE: "40097ba600ba21b94c673a76ff602ece600392fc1d9641576ff66bfa0300e1c2",
}
MODEL_BYTES = {"baseline": 35858002, CANDIDATE: 77949424}
VECTOR = (0.6, 0.4, 0.7, 0.5, 0.5, 0.6)
INPUT_PROFILE = "m10-native-per-model-rgb-v9"
POLICY = dict(
    baseline=dict(
        score_threshold=0.35,
        same_class_nms_iou=0.5,
        output_channels=85,
        input="RGB0-255 top-left letterbox640 fill114",
    ),
    dfine=dict(
        class_order=[0, 1, 2, 3, 5, 7],
        confidence_vector=list(VECTOR),
        native_classes=80,
        top_queries=300,
        nms=False,
        input="PIL RGB bilinear direct640 /255; original[width,height]",
    ),
    crop=False,
    training=False,
    runtime_promotion=False,
)


def validate_policy():
    profile = read_json(PROFILE)
    spec = profile["models"][CANDIDATE]
    if (
        profile["schema"] != "m10-offline-class-calibration-candidates-v1"
        or profile["next_fresh_quality_candidate"] != CANDIDATE
        or profile["runtime_promotion"] is not False
        or profile["training"] is not False
        or spec["onnx_sha256"] != MODELS[CANDIDATE]
        or spec["onnx_bytes"] != MODEL_BYTES[CANDIDATE]
        or tuple(spec["class_thresholds"][str(c)] for c in (0, 1, 2, 3, 5, 7)) != VECTOR
        or spec["native_preprocess_source_sha256"]
        != sha256_file(Path(__file__).with_name("model_screen_v2.py"))
        or profile["class_adapter_source_sha256"]
        != sha256_file(Path(__file__).with_name("class_calibration_v1.py"))
    ):
        raise ValueError("fixed pretrained class-v1 policy identity")


@dataclass(frozen=True)
class OfflineResultV9:
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
            raise ValueError("V9 offline envelope")
        for detection in self.detections:
            detection.validate()


def decode(candidate, raw):
    if candidate == "baseline":
        if set(raw) != {"output"}:
            raise ValueError("baseline raw names")
        return postprocess(raw["output"])
    if candidate != CANDIDATE:
        raise ValueError("unknown V9 candidate")
    return tuple(
        Detection(d.class_id, d.score, d.box) for d in decode_dfine(raw, VECTOR)
    )


class QualityCandidateV9:
    def __init__(self, model, candidate, execution="cuda"):
        if candidate not in CANDIDATES:
            raise ValueError("unknown V9 candidate")
        validate_policy()
        self.candidate = candidate
        self.detector = (
            YoloX(model, execution)
            if candidate == "baseline"
            else ScreenDetector("dfine-m", model, execution)
        )

    def prepare(self, frame):
        if self.candidate == "baseline":
            image_health(frame)
            tensor, ratio = preprocess(frame)
            if ratio != 1.0:
                raise ValueError("fixed original640x384 camera scale")
            return {"images": tensor}
        return self.detector.prepare(frame)

    def infer(self, frame):
        start = time.monotonic_ns()
        feed = self.prepare(frame)
        prepared = time.monotonic_ns()
        names = [o.name for o in self.detector.session.get_outputs()]
        raw = dict(zip(names, self.detector.session.run(None, feed)))
        inferred = time.monotonic_ns()
        detections = decode(self.candidate, raw)
        complete = time.monotonic_ns()
        result = OfflineResultV9(
            frame.identity,
            detections,
            prepared - start,
            inferred - prepared,
            complete - inferred,
            MODELS[self.candidate],
        )
        result.validate()
        return result, raw
