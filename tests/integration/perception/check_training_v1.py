"""Independent ONNX/OpenCV replay of pinned PyTorch numeric probes and RGB data."""

import argparse
import json
from pathlib import Path
import sys
import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.domain_data_v1 import DomainDataset, write_json_new
from physical_ai.perception.training_v1 import decode_six, pack_sample
from physical_ai.perception.trained_model_v1 import TrainedOnnxV1
from train_domain_v1 import score_records


def compare(expected, actual):
    if not np.allclose(expected, actual, atol=0.003, rtol=0.003):
        raise ValueError("raw numeric tolerance")
    a, b = decode_six(expected), decode_six(actual)
    if len(a) != len(b) or [d.class_id for d in a] != [d.class_id for d in b]:
        raise ValueError("numeric detection count/class")
    box = max(
        (max(abs(x - y) for x, y in zip(i.box, j.box)) for i, j in zip(a, b)),
        default=0.0,
    )
    score = max((abs(i.score - j.score) for i, j in zip(a, b)), default=0.0)
    if box > 0.1 or score > 0.0001:
        raise ValueError("final detection numeric tolerance")
    return dict(
        max_raw_absolute_error=float(np.max(np.abs(expected - actual))),
        detections=len(a),
        max_box_error=box,
        max_score_error=score,
    )


def check(export, data, output, execution):
    manifest = export / "manifest.json"
    m = json.loads(manifest.read_text())
    probes = json.loads((export / "probes.json").read_text())
    if probes["manifest_sha256"] != sha256_file(manifest):
        raise ValueError("probe model binding")
    runtime = TrainedOnnxV1(export / "model.onnx", manifest, execution)
    dnn = (
        cv2.dnn.readNetFromONNX(str(export / "model.onnx"))
        if execution == "cpu"
        else None
    )
    comparisons = []
    for probe in probes["probes"]:
        path = export / probe["file"]
        if sha256_file(path) != probe["sha256"]:
            raise ValueError("numeric probe bytes")
        with np.load(path, allow_pickle=False) as saved:
            rgb, raw = saved["rgb"], saved["raw"]
        row = dict(name=probe["name"], onnx=compare(raw, runtime.raw(rgb)))
        if dnn is not None:
            tensor, _ = pack_sample(rgb, [])
            dnn.setInput(tensor[None])
            row["opencv"] = compare(raw, dnn.forward())
        comparisons.append(row)
    validation = DomainDataset(data, "validation")
    if (
        validation.manifest["collection_freeze_sha256"] == ""
        or sha256_file(data / "dataset.json") != m["dataset_sha256"]
    ):
        raise ValueError("numeric validation dataset")
    records = []
    for im, rgb, _ in validation.samples():
        records.append(
            dict(
                image_id=im["id"],
                rgb_sha256=im["rgb_sha256"],
                detections=[
                    dict(class_id=d.class_id, score=d.score, box=list(d.box))
                    for d in runtime.infer_rgb(rgb)
                ],
            )
        )
    write_json_new(output.with_suffix(".predictions.json"), records)
    report = dict(
        schema="m10-trained-numeric-check-v1",
        status="PASS",
        execution=execution,
        model_sha256=m["model_sha256"],
        provider=runtime.session.get_providers(),
        probes=comparisons,
        validation_score=score_records(validation, records),
        scope="FP32 serialization/numeric and development replay; no quality holdout or runtime promotion",
    )
    write_json_new(output, report)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("export", type=Path)
    p.add_argument("data", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--execution", choices=("cpu", "cuda"), default="cpu")
    a = p.parse_args()
    check(a.export, a.data, a.output, a.execution)
