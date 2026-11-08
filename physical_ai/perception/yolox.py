"""Pinned YOLOX FP32 CPU inference. Model output has no authority or timestamps."""

from pathlib import Path
import hashlib
import time
import numpy as np
import cv2
from .artifact import verify
from .contract import (
    CLASSES,
    WIDTH,
    HEIGHT,
    MAX_CANDIDATES,
    MAX_DETECTIONS,
    CameraFrame,
    Detection,
    PerceptionResult,
    profile,
    MODEL_SHA256,
    MODEL_BYTES,
    execution_profile,
)


def preprocess(frame: CameraFrame):
    frame.validate()
    rgb = np.frombuffer(frame.rgb, np.uint8).reshape(HEIGHT, WIDTH, 3)
    ratio = min(640 / WIDTH, 640 / HEIGHT)
    resized = cv2.resize(
        rgb, (int(WIDTH * ratio), int(HEIGHT * ratio)), interpolation=cv2.INTER_LINEAR
    )
    padded = np.full((640, 640, 3), 114, dtype=np.float32)
    padded[: resized.shape[0], : resized.shape[1]] = resized
    return np.ascontiguousarray(padded.transpose(2, 0, 1)[None]), ratio


def _anchors():
    grids, strides = [], []
    for stride in (8, 16, 32):
        y, x = np.mgrid[: 640 // stride, : 640 // stride]
        grids.append(np.stack((x, y), axis=-1).reshape(-1, 2))
        strides.append(np.full((x.size, 1), stride))
    return np.concatenate(grids), np.concatenate(strides)


GRIDS, STRIDES = _anchors()


def image_health(frame: CameraFrame):
    """Obvious loss of image information, not a semantic/ODD health guarantee."""
    frame.validate()
    rgb = np.frombuffer(frame.rgb, np.uint8).reshape(HEIGHT, WIDTH, 3)
    luma = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    standard_deviation = float(luma.std())
    black_fraction = float(np.mean(luma <= 5))
    white_fraction = float(np.mean(luma >= 250))
    if standard_deviation < 2 or black_fraction > 0.98 or white_fraction > 0.98:
        raise ValueError("image information unavailable: flat/blackout/whiteout")
    return {
        "luma_std": standard_deviation,
        "near_black_fraction": black_fraction,
        "near_white_fraction": white_fraction,
    }


def iou(box, others):
    """Half-open boxes, no inclusive +1 pixel convention."""
    a = np.maximum(box[:2], others[:, :2])
    b = np.minimum(box[2:], others[:, 2:])
    intersection = np.prod(np.maximum(0, b - a), axis=1)
    area = (box[2] - box[0]) * (box[3] - box[1])
    areas = np.prod(others[:, 2:] - others[:, :2], axis=1)
    return intersection / (area + areas - intersection)


def postprocess(output, ratio=1.0):
    if (
        not isinstance(output, np.ndarray)
        or output.dtype != np.float32
        or output.shape != (1, 8400, 85)
        or not np.isfinite(output).all()
        or not np.isfinite(ratio)
        or ratio <= 0
    ):
        raise ValueError("model output shape/type/finite")
    raw = output[0]
    if np.any(raw[:, 4:] < 0) or np.any(raw[:, 4:] > 1):
        raise ValueError("model confidence range")
    # Decode every anchor first: do not hide an overflow behind low confidence.
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        try:
            centers = (raw[:, :2].astype(np.float64) + GRIDS) * STRIDES
            sizes = np.exp(raw[:, 2:4].astype(np.float64)) * STRIDES
            boxes = (
                np.concatenate((centers - sizes / 2, centers + sizes / 2), axis=1)
                / ratio
            )
        except FloatingPointError as error:
            raise ValueError("model box decode overflow") from error
    if not np.isfinite(boxes).all() or np.any(sizes <= 0):
        raise ValueError("nonfinite or collapsed decoded box")
    classes = np.argmax(raw[:, 5:], axis=1)
    scores = raw[:, 4].astype(np.float64) * raw[np.arange(8400), classes + 5]
    keep = np.flatnonzero((scores >= 0.35) & np.isin(classes, list(CLASSES)))
    if len(keep) > MAX_CANDIDATES:
        raise ValueError("candidate capacity exceeded")
    # NMS in model/original un-clipped coordinates, matching reference semantics.
    order = keep[np.argsort(-scores[keep], kind="stable")]
    selected = []
    while order.size:
        index = order[0]
        clipped = np.clip(boxes[index], (0, 0, 0, 0), (WIDTH, HEIGHT, WIDTH, HEIGHT))
        if clipped[0] < clipped[2] and clipped[1] < clipped[3]:
            selected.append(
                Detection(
                    int(classes[index]),
                    float(scores[index]),
                    tuple(map(float, clipped)),
                )
            )
            if len(selected) > MAX_DETECTIONS:
                raise ValueError("detection capacity exceeded")
        rest = order[1:]
        order = rest[
            (classes[rest] != classes[index]) | (iou(boxes[index], boxes[rest]) <= 0.5)
        ]
    return tuple(selected)


class YoloX:
    def __init__(self, model: Path, execution="cpu"):
        execution_settings = execution_profile(execution)
        import onnxruntime as ort  # Optional dependency; core C++ needs no ML SDK.

        profile()
        verified = verify(model)
        # Load exactly the bytes whose digest is admitted. Replacing the path
        # after verification cannot silently change the session's model.
        with verified.open("rb") as source:
            model_bytes = source.read(MODEL_BYTES + 1)
        if (
            len(model_bytes) != MODEL_BYTES
            or hashlib.sha256(model_bytes).hexdigest() != MODEL_SHA256
        ):
            raise ValueError("model changed during load")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        providers = ["CPUExecutionProvider"]
        if execution_settings is not None:
            if (
                ort.__version__ != "1.23.2"
                or "CUDAExecutionProvider" not in ort.get_available_providers()
            ):
                raise ValueError(
                    "pinned CUDA runtime unavailable; CPU fallback forbidden"
                )
            ort.preload_dlls(directory="")
            options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
            providers = [
                (
                    "CUDAExecutionProvider",
                    {
                        key: execution_settings[key]
                        for key in (
                            "device_id",
                            "use_tf32",
                            "cudnn_conv_algo_search",
                            "gpu_mem_limit",
                        )
                    },
                )
            ]
        self.session = ort.InferenceSession(
            model_bytes, sess_options=options, providers=providers
        )
        self.session.disable_fallback()
        actual = self.session.get_providers()
        if execution == "cpu" and actual != ["CPUExecutionProvider"]:
            raise ValueError("unexpected execution provider")
        if execution == "cuda":
            actual_options = self.session.get_provider_options().get(
                "CUDAExecutionProvider", {}
            )
            if actual[0] != "CUDAExecutionProvider" or any(
                actual_options.get(key) != execution_settings[key]
                for key in (
                    "device_id",
                    "use_tf32",
                    "cudnn_conv_algo_search",
                    "gpu_mem_limit",
                )
            ):
                raise ValueError("CUDA execution settings not applied")
        inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
        if (
            len(inputs) != 1
            or len(outputs) != 1
            or (inputs[0].name, inputs[0].type, inputs[0].shape)
            != ("images", "tensor(float)", [1, 3, 640, 640])
            or (outputs[0].name, outputs[0].type, outputs[0].shape)
            != ("output", "tensor(float)", [1, 8400, 85])
        ):
            raise ValueError("ONNX tensor contract mismatch")

    def infer(self, frame: CameraFrame):
        start = time.monotonic_ns()
        image_health(frame)
        tensor, ratio = preprocess(frame)
        prepared = time.monotonic_ns()
        raw = self.session.run(["output"], {"images": tensor})[0]
        inferred = time.monotonic_ns()
        detections = postprocess(raw, ratio)
        complete = time.monotonic_ns()
        result = PerceptionResult(
            frame.identity,
            detections,
            prepared - start,
            inferred - prepared,
            complete - inferred,
        )
        result.validate()
        return result
