"""Immutable camera/results and the frozen M10 host contract."""

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

PROFILE_PATH = Path(__file__).resolve().parents[2] / "profiles/perception-host-v1.json"
CUDA_PROFILE_PATH = PROFILE_PATH.with_name("perception-cuda-host-v1.json")
CARLA_RGB_PROFILE_PATH = PROFILE_PATH.with_name("perception-carla-rgb-host-v1.json")
MODEL_SHA256 = "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063"
MODEL_BYTES = 35858002
MODEL_REVISION = "a74cdfad334b102cbd8daed769fbe1d4cb1c327a"
MODEL_URL = (
    f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{MODEL_REVISION}"
    "/models/object_detection_yolox/object_detection_yolox_2022nov.onnx"
)
WIDTH, HEIGHT, PERIOD_NS, LIFETIME_NS = 640, 384, 50_000_000, 100_000_000
MAX_DETECTIONS, MAX_CANDIDATES = 100, 1000
CLASSES = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
UINT64_MAX = 2**64 - 1


def uint(value, maximum=UINT64_MAX, positive=False):
    return type(value) is int and (1 if positive else 0) <= value <= maximum


def execution_profile(execution):
    if execution == "cpu":
        return None
    if execution != "cuda":
        raise ValueError("unsupported execution profile")
    data = json.loads(CUDA_PROFILE_PATH.read_text())
    expected = {
        "schema": "m10-perception-cuda-host-v1",
        "semantic_profile": "m10-perception-host-v1",
        "onnxruntime_version": "1.23.2",
        "provider": "CUDAExecutionProvider",
        "device_id": "0",
        "use_tf32": "0",
        "cudnn_conv_algo_search": "HEURISTIC",
        "gpu_mem_limit": "2147483648",
        "disable_cpu_ep_fallback": "1",
        "precision": "float32",
        "warmup_exclusion": False,
    }
    if data != expected:
        raise ValueError("CUDA profile/executable mismatch")
    return data


def carla_rgb_profile():
    data = json.loads(CARLA_RGB_PROFILE_PATH.read_text())
    if data != {
        "schema": "m10-perception-carla-rgb-host-v1",
        "semantic_profile": "m10-perception-host-v1",
        "map": "Town03_Opt",
        "weather": "ClearNoon",
        "server_quality": "Low",
        "enable_postprocess_effects": True,
        "camera_schedule": "frame5",
        "camera_role": "m7_frame5",
        "sensor_tick_seconds": 0.05,
        "renderer_acceptance": "NOT_CLAIMED",
    }:
        raise ValueError("CARLA RGB profile/executable mismatch")
    return data


def profile():
    """Return provenance, checking executable/profile drift before running."""
    data = json.loads(PROFILE_PATH.read_text())
    m, c = data["model"], data["camera"]
    expected = (
        data["schema"] == "m10-perception-host-v1"
        and (m["sha256"], m["bytes"], m["revision"], m["url"])
        == (MODEL_SHA256, MODEL_BYTES, MODEL_REVISION, MODEL_URL)
        and (m["input_name"], m["input_shape"], m["output_name"], m["output_shape"])
        == ("images", [1, 3, 640, 640], "output", [1, 8400, 85])
        and (
            m["precision"],
            m["provider"],
            m["intra_op_threads"],
            m["inter_op_threads"],
        )
        == ("float32", "CPUExecutionProvider", 4, 1)
        and (
            c["id"],
            c["calibration_revision"],
            c["width"],
            c["height"],
            c["period_ns"],
            c["format"],
            c["fov_degrees"],
        )
        == (1, 1, WIDTH, HEIGHT, PERIOD_NS, "RGB8", 90)
        and (data["score_threshold"], data["nms_iou_threshold"], data["class_ids"])
        == (0.35, 0.5, list(CLASSES))
        and (
            data["max_detections"],
            data["max_candidates"],
            data["source_lifetime_ns"],
            data["host_processing_budget_ns"],
            data["queue_capacity"],
        )
        == (MAX_DETECTIONS, MAX_CANDIDATES, LIFETIME_NS, LIFETIME_NS, 1)
        and data["tracking"]
        == {"iou_threshold": 0.3, "history_frames": 10, "max_gap_ns": LIFETIME_NS}
        and data["image_health"]
        == {
            "minimum_luma_std": 2.0,
            "maximum_near_black_fraction": 0.98,
            "maximum_near_white_fraction": 0.98,
            "near_black_max": 5,
            "near_white_min": 250,
        }
    )
    if not expected:
        raise ValueError(
            "profile/executable mismatch; create and validate a new revision"
        )
    return data


@dataclass(frozen=True)
class FrameIdentity:
    epoch: int
    clock_instance: int
    frame: int
    source_ns: int
    camera_id: int = 1
    calibration_revision: int = 1

    def validate(self):
        if not (
            uint(self.epoch, 2**32 - 1, True)
            and uint(self.clock_instance, positive=True)
            and uint(self.frame, positive=True)
            and uint(self.source_ns, UINT64_MAX - LIFETIME_NS)
            and type(self.camera_id) is int
            and self.camera_id == 1
            and type(self.calibration_revision) is int
            and self.calibration_revision == 1
        ):
            raise ValueError("invalid camera identity")


@dataclass(frozen=True)
class CameraFrame:
    identity: FrameIdentity
    rgb: bytes
    width: int = WIDTH
    height: int = HEIGHT

    def validate(self):
        if type(self.identity) is not FrameIdentity:
            raise ValueError("camera identity type")
        self.identity.validate()
        if (
            type(self.width) is not int
            or type(self.height) is not int
            or (self.width, self.height) != (WIDTH, HEIGHT)
            or type(self.rgb) is not bytes
            or len(self.rgb) != WIDTH * HEIGHT * 3
        ):
            raise ValueError("RGB8 camera layout")


@dataclass(frozen=True)
class Detection:
    class_id: int
    score: float
    box: tuple[float, float, float, float]

    def validate(self):
        if (
            type(self.class_id) is not int
            or self.class_id not in CLASSES
            or type(self.score) not in (int, float)
            or not math.isfinite(self.score)
            or not 0.35 <= self.score <= 1
            or type(self.box) is not tuple
            or len(self.box) != 4
            or not all(type(v) in (int, float) and math.isfinite(v) for v in self.box)
        ):
            raise ValueError("invalid detection")
        x1, y1, x2, y2 = self.box
        if not (0 <= x1 < x2 <= WIDTH and 0 <= y1 < y2 <= HEIGHT):
            raise ValueError("box outside original image")


@dataclass(frozen=True)
class PerceptionResult:
    identity: FrameIdentity
    detections: tuple[Detection, ...]
    preprocess_ns: int
    inference_ns: int
    postprocess_ns: int
    model_sha256: str = MODEL_SHA256

    @property
    def expires_ns(self):
        return self.identity.source_ns + LIFETIME_NS

    def validate(self):
        if type(self.identity) is not FrameIdentity:
            raise ValueError("result identity type")
        self.identity.validate()
        if (
            self.model_sha256 != MODEL_SHA256
            or type(self.detections) is not tuple
            or len(self.detections) > MAX_DETECTIONS
            or not all(
                uint(v)
                for v in (self.preprocess_ns, self.inference_ns, self.postprocess_ns)
            )
        ):
            raise ValueError("invalid result envelope")
        for detection in self.detections:
            if type(detection) is not Detection:
                raise ValueError("detection type")
            detection.validate()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
