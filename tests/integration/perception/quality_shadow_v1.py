"""The registered six-class RTX 3090 detector, used only by the paired renderer."""

from contextlib import ExitStack, contextmanager
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "docs/test-plan/evidence/m10_quality_latency_v2/comparison.json"
ENGINE = ROOT / "build/m10-quality-latency-v1/dfine-fp16.plan"
LIBRARY = ENGINE.with_name("quality_crop_v2.so")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding():
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import m10_bus_support_quality as current

    reference = json.loads(REFERENCE.read_text())["runs"]["run1"]["binding"].copy()
    del reference["startup_ms"]
    for name, expected in reference["source"].items():
        folder = (
            ROOT / "tools"
            if name == "m10_quality_latency.py"
            else Path(__file__).parent
        )
        if digest(folder / name) != expected:
            raise ValueError(f"changed quality candidate source: {name}")
    if (
        current.nomination() != json.loads(current.MARK.read_text())
        or digest(current.MARK) != reference["reference"]
        or digest(ENGINE) != reference["engine_sha256"]
        or digest(LIBRARY) != reference["library_sha256"]
    ):
        raise ValueError("quality candidate identity")
    return reference


@contextmanager
def detector():
    import cv2
    import tensorrt
    from quality_latency import Detector
    from quality_latency_cuda import CropInput, Engine

    spec = binding()
    if tensorrt.__version__ != spec["tensorrt"]:
        raise ValueError("TensorRT version changed")
    cv2.setNumThreads(1)
    with ExitStack() as stack:
        crops = stack.enter_context(CropInput(LIBRARY))
        engine = stack.enter_context(Engine(ENGINE))
        model = Detector(crops, "targeted", engine)
        # Model setup can configure OpenCV. Apply the worker's explicit CPU setting.
        cv2.setNumThreads(1)
        yield model, spec


def predict(model, bgra):
    start = time.monotonic_ns()
    image = model.decode(bgra)
    decoded = time.monotonic_ns()
    boxes, stages = model.predict(image)
    return dict(detections=boxes, decode_ns=decoded - start, stages_ms=stages)


def replay_boxes(folder, renderer, images):
    """Check every completed live result against a fresh inference on the retained BGRA."""
    from endurance_recording_v1 import RawReader

    reader = RawReader(folder)
    try:
        with detector() as (model, spec):
            if renderer.get("quality_binding") != spec:
                raise ValueError("renderer used another quality candidate")
            for row in renderer["inference"]:
                bgra = reader.read(images[row["renderer_frame"]])
                if predict(model, bgra)["detections"] != row["detections"]:
                    raise ValueError(
                        f"live box replay differs at frame {row['renderer_frame']}"
                    )
    finally:
        reader.close()
