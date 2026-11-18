"""Verify the development-qualified model, decoder, parameters, and supporting records."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/test-plan/evidence/m10_parking_verifier_v1"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(bundle):
    freeze = read(EVIDENCE / "development-freeze.json")
    for name, expected in freeze["files"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"frozen evidence or inference source changed: {name}")
    for name, expected in freeze["bundle"].items():
        if sha(bundle / name) != expected:
            raise ValueError(f"selected model bundle changed: {name}")
    manifest = read(bundle / "manifest.json")
    result = read(EVIDENCE / "selected/result.json")
    score = read(EVIDENCE / "selected/score.json")
    group = read(EVIDENCE / "selected/validation.json")
    if not (
        manifest["model_sha256"]
        == freeze["bundle"]["parking-dfine-960.onnx"]
        == result["onnx_sha256"]
        == group["model"]
        and sha(bundle / "manifest.json") == sha(EVIDENCE / "selected/manifest.json")
        and manifest["selection_sha256"] == sha(EVIDENCE / "selected/selection.json")
        and result["predictions_sha256"] == sha(EVIDENCE / "selected/predictions.json")
        and result["absolute"] == score["absolute_quality"] == "PASS"
        and result["relative"]["status"] == "PASS"
        and all(result["relative"]["gates"].values())
        and result["frames"] == score["frames"] == 81
        and all(score["gates"].values())
        and result["quality_matches_torch"]
        and result["frame_class_count_or_match_differences"] == []
        and {k: v["images"] for k, v in group["groups"].items()}
        == {"previous": 315, "Town02_Opt": 384}
        and all(
            v["precision"] >= 0.85 and v["recall"] >= 0.80
            for v in group["groups"].values()
        )
    ):
        raise ValueError(
            "development or validation records do not match the selected model"
        )
    return freeze["bundle"]["parking-dfine-960.onnx"]


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--bundle",
        type=Path,
        default=ROOT / "build/m10-parking-verifier-v1/export-bus-truck",
    )
    print("PASS", verify(p.parse_args().bundle))
