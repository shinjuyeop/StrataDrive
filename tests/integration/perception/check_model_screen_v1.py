#!/usr/bin/env python3
"""Independent upstream probes and CPU/CUDA numeric checks before development scoring."""

from dataclasses import asdict
import importlib.util
from pathlib import Path
import sys
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import CLASSES
from physical_ai.perception.dataset import RgbDataset, read_json
from physical_ai.perception.model_screen_v1 import CANDIDATES, ScreenDetector
from run_model_screen_v1 import write_new

ROOT = Path(__file__).resolve().parents[3]

PROBES = ROOT / "build/m10-quality-v7/preparation-development-data/rgb.json"


def upstream_reference(output, checkpoint, rtdetr_path, nano_path):
    import torch
    import torchvision.transforms as T
    from PIL import Image
    from screen_rtdetr_v1 import model_from_checkpoint

    output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model = model_from_checkpoint(checkpoint)
    nano_spec = importlib.util.spec_from_file_location(
        "nanodet_reference", ROOT / "third_party/nanodet-screen-v1/nanodet.py"
    )
    nano_module = importlib.util.module_from_spec(nano_spec)
    nano_spec.loader.exec_module(nano_module)
    nano = nano_module.NanoDet(str(nano_path))
    demo_spec = importlib.util.spec_from_file_location(
        "nanodet_demo_reference", ROOT / "third_party/nanodet-screen-v1/demo.py"
    )
    demo = importlib.util.module_from_spec(demo_spec)
    sys.modules["nanodet"] = nano_module
    demo_spec.loader.exec_module(demo)
    rt = ScreenDetector("rtdetrv2-r18", rtdetr_path, "cpu")
    nano_backend = ScreenDetector("nanodet-plus416", nano_path, "cpu")
    rows = []
    for i, (source, camera) in enumerate(RgbDataset(PROBES).frames()):
        if i == 3:
            break
        rgb = np.frombuffer(camera.rgb, np.uint8).reshape(384, 640, 3)
        tensor = T.Compose([T.Resize((640, 640)), T.ToTensor()])(Image.fromarray(rgb))[
            None
        ]
        np.testing.assert_array_equal(tensor.numpy(), rt.prepare(camera)["images"])
        with torch.inference_mode():
            labels, boxes, scores = model(tensor, torch.tensor([[640, 384]]))
        reference = dict(
            labels=labels.numpy(), boxes=boxes.numpy(), scores=scores.numpy()
        )
        np.savez_compressed(output / f"rtdetr-{i}.npz", **reference)
        image, scale = demo.letterbox(rgb)
        np.testing.assert_array_equal(
            nano.pre_process(image), nano_backend.prepare(camera)["input.1"]
        )
        nano.net.setInput(nano.pre_process(image))
        names = nano.net.getUnconnectedOutLayersNames()
        values = nano.net.forward(names)
        np.savez_compressed(output / f"nanodet-{i}.npz", **dict(zip(names, values)))
        detections = []
        for pred in nano.post_process(values):
            if int(pred[5]) in CLASSES:
                box = demo.unletterbox(pred[:4], (384, 640), scale)
                if box[0] < box[2] and box[1] < box[3]:
                    detections.append(
                        dict(
                            class_id=int(pred[5]),
                            score=float(pred[4]),
                            box=box.tolist(),
                        )
                    )
        rows.append(dict(rgb_sha256=source["rgb_sha256"], nano_detections=detections))
    write_new(
        output / "reference.json",
        dict(
            status="PASS",
            frames=rows,
            raw_atol=0.003,
            raw_rtol=0.003,
            detection_box_atol=0.1,
            detection_score_atol=0.0001,
            nanodet_official_integer_box_atol=1.01,
            torch_version=torch.__version__,
        ),
    )


def compare_detections(expected, actual, box_tol=0.1):
    expected = sorted(expected, key=lambda d: (d["class_id"], -d["score"]))
    actual = sorted(actual, key=lambda d: (d["class_id"], -d["score"]))
    if len(expected) != len(actual):
        raise ValueError("numeric detection count mismatch")
    for a, b in zip(expected, actual):
        if a["class_id"] != b["class_id"]:
            raise ValueError("numeric detection class mismatch")
        np.testing.assert_allclose(a["box"], b["box"], atol=box_tol, rtol=0)
        np.testing.assert_allclose(a["score"], b["score"], atol=0.0001, rtol=0)


def compare_top300(expected, actual):
    """TopK is an unordered detection set; bind every row one-to-one, including lows."""
    available = set(range(300))
    moved = 0
    box_max = score_max = 0.0
    for n in range(300):
        candidates = [
            j
            for j in available
            if expected["labels"][0, n] == actual["labels"][0, j]
            and abs(float(expected["scores"][0, n] - actual["scores"][0, j])) <= 0.0001
            and np.max(np.abs(expected["boxes"][0, n] - actual["boxes"][0, j])) <= 0.1
        ]
        if not candidates:
            raise ValueError("RT-DETR complete top300 set mismatch")
        j = min(
            candidates,
            key=lambda j: float(
                np.max(np.abs(expected["boxes"][0, n] - actual["boxes"][0, j]))
            ),
        )
        available.remove(j)
        moved += int(j != n)
        box_max = max(
            box_max,
            float(np.max(np.abs(expected["boxes"][0, n] - actual["boxes"][0, j]))),
        )
        score_max = max(
            score_max, abs(float(expected["scores"][0, n] - actual["scores"][0, j]))
        )
    return dict(
        permuted_rows=moved,
        all300_matched=True,
        box_max_abs=box_max,
        score_max_abs=score_max,
    )


def numeric(reference, model_paths):
    report = dict(
        status="PASS", probes=str(PROBES.relative_to(ROOT)), rows=[], failures=[]
    )
    frames = list(RgbDataset(PROBES).frames())[:3]
    references = read_json(reference / "reference.json")
    for candidate in CANDIDATES:
        try:
            cpu, cuda = [
                ScreenDetector(candidate, model_paths[candidate], mode)
                for mode in ("cpu", "cuda")
            ]
            for i, (source, camera) in enumerate(frames):
                if source["rgb_sha256"] != references["frames"][i]["rgb_sha256"]:
                    raise ValueError("numeric probe identity")
                feed = cpu.prepare(camera)
                names = [o.name for o in cpu.session.get_outputs()]
                outputs = [
                    dict(zip(names, backend.session.run(None, feed)))
                    for backend in (cpu, cuda)
                ]
                deltas = {}
                for name in names if candidate != "rtdetrv2-r18" else []:
                    a, b = (out[name] for out in outputs)
                    if np.issubdtype(a.dtype, np.integer):
                        np.testing.assert_array_equal(a, b)
                    else:
                        np.testing.assert_allclose(a, b, atol=0.003, rtol=0.003)
                    deltas[name] = float(
                        np.max(np.abs(a.astype(float) - b.astype(float)))
                    )
                if candidate == "rtdetrv2-r18":
                    deltas = compare_top300(*outputs)
                detections = [
                    [asdict(d) for d in backend.decode(out)]
                    for backend, out in zip((cpu, cuda), outputs)
                ]
                compare_detections(*detections)
                if candidate in ("rtdetrv2-r18", "nanodet-plus416"):
                    family = "rtdetr" if candidate.startswith("rtdetr") else "nanodet"
                    expected = dict(np.load(reference / f"{family}-{i}.npz"))
                    for name in names if family != "rtdetr" else []:
                        if np.issubdtype(expected[name].dtype, np.integer):
                            np.testing.assert_array_equal(
                                outputs[0][name], expected[name]
                            )
                        else:
                            np.testing.assert_allclose(
                                outputs[0][name], expected[name], atol=0.003, rtol=0.003
                            )
                    if family == "rtdetr":
                        compare_top300(expected, outputs[0])
                        compare_detections(
                            [asdict(d) for d in cpu.decode(expected)], detections[0]
                        )
                    else:
                        compare_detections(
                            references["frames"][i]["nano_detections"],
                            detections[0],
                            box_tol=1.01,
                        )
                report["rows"].append(
                    dict(
                        candidate=candidate,
                        probe=i,
                        status="PASS",
                        rgb_sha256=source["rgb_sha256"],
                        raw_max_abs=deltas,
                        detection_count=len(detections[0]),
                    )
                )
        except Exception:
            import traceback

            report["failures"].append(
                dict(candidate=candidate, error=traceback.format_exc())
            )
            report["status"] = "FAIL"
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("reference", "check"))
    p.add_argument("--models", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    paths = read_json(a.models)
    if a.action == "reference":
        upstream_reference(
            a.reference, a.checkpoint, paths["rtdetrv2-r18"], paths["nanodet-plus416"]
        )
    else:
        result = numeric(a.reference, paths)
        write_new(a.output, result)
        print(result["status"], len(result["rows"]), result["failures"])
        sys.exit(0 if result["status"] == "PASS" else 1)
