"""Offline pretrained screen v2; confidence calibration never publishes runtime output."""

import hashlib
from pathlib import Path
import time
from dataclasses import dataclass
import math
import cv2
import numpy as np
from .contract import CLASSES, HEIGHT, WIDTH, execution_profile
from .dataset import read_json
from .model_screen_v1 import prepare_rgb
from .yolox import GRIDS, STRIDES, image_health, iou, preprocess

REGISTRY = (
    Path(__file__).resolve().parents[2] / "profiles/perception-model-screen-v2.json"
)
CANDIDATES = ("yolox-s", "yolox-l", "rtdetrv2-r18", "dfine-m", "rtv4-s", "damo-s")
THRESHOLDS = (0.10, 0.20, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70)


@dataclass(frozen=True)
class ScreenDetection:
    """Offline value only; distinct from the frozen runtime envelope."""

    class_id: int
    score: float
    box: tuple[float, float, float, float]

    def validate(self):
        if (
            type(self.class_id) is not int
            or self.class_id not in CLASSES
            or type(self.score) not in (int, float)
            or not math.isfinite(self.score)
            or not 0.1 <= self.score <= 1
            or type(self.box) is not tuple
            or len(self.box) != 4
            or not all(type(v) in (int, float) and math.isfinite(v) for v in self.box)
        ):
            raise ValueError("invalid offline screen detection")
        x1, y1, x2, y2 = self.box
        if not (0 <= x1 < x2 <= WIDTH and 0 <= y1 < y2 <= HEIGHT):
            raise ValueError("offline box outside image")


def select(labels, scores, boxes, threshold):
    if not np.isfinite(boxes).all() or not np.isfinite(scores).all():
        raise ValueError("nonfinite screen output")
    if np.any(scores < 0) or np.any(scores > 1) or np.any(boxes[:, 2:] < boxes[:, :2]):
        raise ValueError("invalid screen confidence/box")
    result = []
    for i in np.argsort(-scores, kind="stable"):
        if int(labels[i]) not in CLASSES or scores[i] < threshold:
            continue
        box = np.clip(boxes[i], [0, 0, 0, 0], [WIDTH, HEIGHT, WIDTH, HEIGHT])
        if box[0] >= box[2] or box[1] >= box[3]:
            continue
        detection = ScreenDetection(
            int(labels[i]), float(scores[i]), tuple(map(float, box))
        )
        detection.validate()
        result.append(detection)
        if len(result) > 100:
            raise ValueError("screen detection capacity exceeded")
    return tuple(result)


def nms(labels, scores, boxes, threshold, limit=None):
    order = np.argsort(-scores, kind="stable")
    selected = []
    while order.size:
        index = order[0]
        selected.append(index)
        if limit is not None and len(selected) == limit:
            break
        rest = order[1:]
        order = rest[
            (labels[rest] != labels[index])
            | (iou(boxes[index], boxes[rest]) <= threshold)
        ]
    return np.asarray(selected, dtype=np.int64)


def decode(raw, family, threshold):
    if threshold not in THRESHOLDS:
        raise ValueError("undeclared confidence threshold")
    if family == "rtdetr":
        if set(raw) != {"labels", "boxes", "scores"}:
            raise ValueError("DETR output names")
        labels, boxes, scores = (raw[k] for k in ("labels", "boxes", "scores"))
        if (
            labels.dtype != np.int64
            or labels.shape != (1, 300)
            or boxes.dtype != np.float32
            or boxes.shape != (1, 300, 4)
            or scores.dtype != np.float32
            or scores.shape != (1, 300)
            or np.any(labels < 0)
            or np.any(labels >= 80)
        ):
            raise ValueError("DETR raw contract")
        return select(labels[0], scores[0], boxes[0], threshold)
    if family == "yolox":
        if set(raw) != {"output"}:
            raise ValueError("YOLOX output names")
        out = raw["output"]
        if (
            out.dtype != np.float32
            or out.shape != (1, 8400, 85)
            or not np.isfinite(out).all()
        ):
            raise ValueError("YOLOX raw contract")
        out = out[0]
        if np.any(out[:, 4:] < 0) or np.any(out[:, 4:] > 1):
            raise ValueError("YOLOX confidence range")
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            centers = (out[:, :2].astype(np.float64) + GRIDS) * STRIDES
            sizes = np.exp(out[:, 2:4].astype(np.float64)) * STRIDES
            boxes = np.concatenate((centers - sizes / 2, centers + sizes / 2), axis=1)
        if not np.isfinite(boxes).all() or np.any(sizes <= 0):
            raise ValueError("YOLOX box decode")
        labels = np.argmax(out[:, 5:], axis=1)
        scores = out[:, 4].astype(np.float64) * out[np.arange(8400), labels + 5]
        indices = np.flatnonzero(scores >= threshold)
        if np.count_nonzero(np.isin(labels[indices], list(CLASSES))) > 1000:
            raise ValueError("YOLOX candidate capacity")
        labels, scores, boxes = labels[indices], scores[indices], boxes[indices]
        keep = nms(labels, scores, boxes, 0.5)
    elif family == "damo":
        if set(raw) != {"scores", "boxes"}:
            raise ValueError("DAMO output names")
        scores, boxes = raw["scores"], raw["boxes"]
        if (
            scores.dtype != np.float32
            or scores.shape != (1, 8400, 80)
            or boxes.dtype != np.float32
            or boxes.shape != (1, 8400, 4)
            or not np.isfinite(scores).all()
            or not np.isfinite(boxes).all()
            or np.any(scores < 0)
            or np.any(scores > 1)
            or np.any(boxes[:, :, 2:] < boxes[:, :, :2])
        ):
            raise ValueError("DAMO raw contract")
        anchors, labels = np.nonzero(scores[0] > threshold)
        scores, boxes = scores[0, anchors, labels], boxes[0, anchors].copy()
        # Pinned official continuous-coordinate batched NMS / native top500.
        keep = nms(labels, scores, boxes, 0.7, limit=500)
        boxes *= np.array([WIDTH / 640, HEIGHT / 640] * 2, dtype=np.float32)
    else:
        raise ValueError("unknown screen family")
    return select(labels[keep], scores[keep], boxes[keep], threshold)


class ScreenDetector:
    def __init__(self, candidate, path, execution="cuda", registry=REGISTRY):
        import onnxruntime as ort

        specs = read_json(registry)
        if (
            specs["schema"] != "m10-pretrained-screen-registry-v2"
            or candidate not in CANDIDATES
        ):
            raise ValueError("screen registry/candidate")
        self.spec = specs["models"][candidate]
        self.candidate = candidate
        data = Path(path).read_bytes()
        if (
            len(data) != self.spec["bytes"]
            or hashlib.sha256(data).hexdigest() != self.spec["sha256"]
        ):
            raise ValueError("screen pinned model identity")
        settings = execution_profile(execution)
        if ort.__version__ != "1.23.2":
            raise ValueError("screen pinned ORT")
        options = ort.SessionOptions()
        options.intra_op_num_threads, options.inter_op_num_threads = 4, 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        providers = ["CPUExecutionProvider"]
        if settings is not None:
            if "CUDAExecutionProvider" not in ort.get_available_providers():
                raise ValueError("screen CUDA unavailable")
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
                raise ValueError("screen CUDA settings mismatch")
        elif self.session.get_providers() != ["CPUExecutionProvider"]:
            raise ValueError("screen CPU provider mismatch")
        for items, key in (
            (self.session.get_inputs(), "inputs"),
            (self.session.get_outputs(), "outputs"),
        ):
            actual = [dict(name=i.name, shape=i.shape, dtype=i.type) for i in items]
            if actual != self.spec[key]:
                raise ValueError("screen tensor contract " + key)

    def prepare(self, frame):
        image_health(frame)
        family = self.spec["family"]
        if family == "yolox":
            tensor, _ = preprocess(frame)
            return {"images": tensor}
        rgb = np.frombuffer(frame.rgb, np.uint8).reshape(HEIGHT, WIDTH, 3)
        if family == "rtdetr":
            return prepare_rgb(rgb, "rtdetr")
        if family == "damo":
            # Official still-image demo uses PIL RGB, direct resize (keep_ratio=False).
            resized = cv2.resize(rgb, (640, 640), interpolation=cv2.INTER_LINEAR)
            return {
                "images": np.ascontiguousarray(
                    resized.transpose(2, 0, 1)[None], dtype=np.float32
                )
            }
        raise ValueError("unknown screen preprocessing")

    def decode(self, raw, threshold=0.35):
        return decode(raw, self.spec["family"], threshold)

    def infer(self, frame):
        start = time.monotonic_ns()
        feed = self.prepare(frame)
        prepared = time.monotonic_ns()
        values = self.session.run(None, feed)
        inferred = time.monotonic_ns()
        raw = dict(zip((o.name for o in self.session.get_outputs()), values))
        detections = self.decode(raw)
        complete = time.monotonic_ns()
        return (
            raw,
            detections,
            dict(
                preprocess_ns=prepared - start,
                inference_ns=inferred - prepared,
                postprocess_ns=complete - inferred,
            ),
        )
