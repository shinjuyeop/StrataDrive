"""Development-only pretrained model screening; no runtime result publication."""

import hashlib
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image

from .contract import CLASSES, Detection, HEIGHT, WIDTH, execution_profile
from .dataset import read_json
from .yolox import image_health, postprocess, preprocess

REGISTRY = (
    Path(__file__).resolve().parents[2] / "profiles/perception-model-screen-v1.json"
)
CANDIDATES = ("yolox-s", "yolox-m", "yolox-l", "rtdetrv2-r18", "nanodet-plus416")


def prepare_rgb(rgb, family):
    if rgb.dtype != np.uint8 or rgb.shape != (HEIGHT, WIDTH, 3):
        raise ValueError("screen RGB contract")
    if family == "rtdetr":
        image = Image.fromarray(rgb).resize((640, 640), Image.Resampling.BILINEAR)
        tensor = np.asarray(image).astype(np.float32).transpose(2, 0, 1) / 255.0
        return {
            "images": np.ascontiguousarray(tensor[None]),
            "orig_target_sizes": np.array([[WIDTH, HEIGHT]], dtype=np.int64),
        }
    if family == "nanodet":
        # Exact pinned OpenCV demo RGB/INTER_AREA/zero-centered letterbox recipe.
        newh = int(416 * HEIGHT / WIDTH)
        top = (416 - newh) // 2
        image = cv2.resize(rgb, (416, newh), interpolation=cv2.INTER_AREA)
        image = cv2.copyMakeBorder(
            image, top, 416 - newh - top, 0, 0, cv2.BORDER_CONSTANT, value=0
        ).astype(np.float32)
        image = (image - np.array([103.53, 116.28, 123.675], np.float32)) / np.array(
            [57.375, 57.12, 58.395], np.float32
        )
        return {"input.1": np.ascontiguousarray(image.transpose(2, 0, 1)[None])}
    raise ValueError("unknown screen preprocessing family")


def _detections(labels, scores, boxes):
    if not np.isfinite(boxes).all() or not np.isfinite(scores).all():
        raise ValueError("nonfinite screen output")
    if np.any(scores < 0) or np.any(scores > 1):
        raise ValueError("screen confidence range")
    if np.any(boxes[:, 2:] < boxes[:, :2]):
        raise ValueError("inverted screen box")
    result = []
    for i in np.argsort(-scores, kind="stable"):
        if int(labels[i]) not in CLASSES or scores[i] < 0.35:
            continue
        box = np.clip(boxes[i], [0, 0, 0, 0], [WIDTH, HEIGHT, WIDTH, HEIGHT])
        if box[0] >= box[2] or box[1] >= box[3]:
            continue
        d = Detection(int(labels[i]), float(scores[i]), tuple(map(float, box)))
        d.validate()
        result.append(d)
        if len(result) > 100:
            raise ValueError("screen detection capacity exceeded")
    return tuple(result)


def decode_rtdetr(raw):
    if set(raw) != {"labels", "boxes", "scores"}:
        raise ValueError("RT-DETR output names")
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
        raise ValueError("RT-DETR raw contract")
    return _detections(labels[0], scores[0], boxes[0])


def decode_nanodet(raw):
    names = [("792", "795", 8, 52), ("814", "817", 16, 26), ("836", "839", 32, 13)]
    if set(raw) != {n for row in names for n in row[:2]}:
        raise ValueError("NanoDet output names")
    all_boxes, all_scores = [], []
    for cname, bname, stride, side in names:
        c, b = raw[cname], raw[bname]
        if (
            c.dtype != np.float32
            or c.shape != (1, side * side, 80)
            or b.dtype != np.float32
            or b.shape != (1, side * side, 32)
            or not np.isfinite(c).all()
            or not np.isfinite(b).all()
            or np.any(c < 0)
            or np.any(c > 1)
        ):
            raise ValueError("NanoDet raw contract")
        c = c[0]
        # Stable softmax preserves the official distributional box expectation.
        logits = b[0].astype(np.float64).reshape(-1, 4, 8)
        exps = np.exp(logits - logits.max(axis=2, keepdims=True))
        distances = (exps / exps.sum(axis=2, keepdims=True)) @ np.arange(8)
        distances *= stride
        y, x = np.mgrid[:side, :side]
        centers = np.column_stack((x.ravel(), y.ravel())) * stride + 0.5 * (stride - 1)
        if len(c) > 1000:
            top = c.max(axis=1).argsort()[::-1][:1000]
            centers, distances, c = centers[top], distances[top], c[top]
        boxes = np.column_stack(
            (centers - distances[:, :2], centers + distances[:, 2:])
        )
        all_boxes.append(np.clip(boxes, 0, 416))
        all_scores.append(c)
    boxes, scores = np.concatenate(all_boxes), np.concatenate(all_scores)
    labels, confidence = scores.argmax(axis=1), scores.max(axis=1)
    # The upstream model uses class-agnostic NMS across all80 classes BEFORE
    # selecting our6 classes. Preserve that behavior, including non-target classes.
    wh = boxes.copy()
    wh[:, 2:] -= wh[:, :2]
    keep = cv2.dnn.NMSBoxes(wh.tolist(), confidence.tolist(), 0.35, 0.6)
    indices = np.asarray(keep, dtype=np.int64).reshape(-1)
    boxes = boxes[indices]
    newh = int(416 * HEIGHT / WIDTH)
    top = (416 - newh) // 2
    boxes = (boxes - [0, top, 0, top]) * ([WIDTH / 416, HEIGHT / newh] * 2)
    return _detections(labels[indices], confidence[indices], boxes)


class ScreenDetector:
    def __init__(self, candidate, path, execution="cuda", registry=REGISTRY):
        import onnxruntime as ort

        specs = read_json(registry)
        if (
            specs["schema"] != "m10-pretrained-screen-registry-v1"
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
        if self.spec["family"] == "yolox":
            tensor, _ = preprocess(frame)
            return {"images": tensor}
        rgb = np.frombuffer(frame.rgb, np.uint8).reshape(HEIGHT, WIDTH, 3)
        return prepare_rgb(rgb, self.spec["family"])

    def decode(self, raw):
        family = self.spec["family"]
        if family == "yolox":
            return postprocess(raw["output"])
        if family == "rtdetr":
            return decode_rtdetr(raw)
        return decode_nanodet(raw)

    def infer(self, frame):
        start = time.monotonic_ns()
        feed = self.prepare(frame)
        prepared = time.monotonic_ns()
        values = self.session.run(None, feed)
        inferred = time.monotonic_ns()
        raw = dict(zip((o.name for o in self.session.get_outputs()), values))
        detections = self.decode(raw)
        complete = time.monotonic_ns()
        return detections, dict(
            preprocess_ns=prepared - start,
            inference_ns=inferred - prepared,
            postprocess_ns=complete - inferred,
        )
