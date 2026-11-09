"""Preparation-only CPU/CUDA agreement of the complete V5 multi-view policies."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import RgbDataset
from physical_ai.perception.quality_candidates_v5 import QualityCandidateV5, CANDIDATES
from quality_benchmark import write_new


def check(dataset, model):
    rows = []
    frames = [
        (s, f)
        for n, (s, f) in enumerate(RgbDataset(dataset).frames())
        if n in (0, 24, 48)
    ]
    for candidate in CANDIDATES[1:]:
        cpu = QualityCandidateV5(model, candidate, "cpu")
        cuda = QualityCandidateV5(model, candidate, "cuda")
        for source, frame in frames:
            a, b = cpu.infer(frame), cuda.infer(frame)
            remaining = list(b.detections)
            errors = []
            passed = len(a.detections) == len(b.detections)
            for d in a.detections:
                choices = [
                    (max(abs(x - y) for x, y in zip(d.box, p.box)), n)
                    for n, p in enumerate(remaining)
                    if d.class_id == p.class_id
                ]
                error, index = min(choices, default=(float("inf"), -1))
                if index < 0:
                    passed = False
                    continue
                p = remaining.pop(index)
                score_error = abs(d.score - p.score)
                passed &= error <= 0.01 and score_error <= 1e-4
                errors.append(dict(maximum_box_error=error, score_error=score_error))
            passed &= not remaining
            rows.append(
                dict(
                    candidate=candidate,
                    scene=source["scene"],
                    rgb_sha256=source["rgb_sha256"],
                    passed=bool(passed),
                    cpu_detections=len(a.detections),
                    cuda_detections=len(b.detections),
                    errors=errors,
                )
            )
    return dict(
        schema="m10-v5-view-check",
        status="PASS" if len(rows) == 6 and all(r["passed"] for r in rows) else "FAIL",
        dataset_sha256=sha256_file(dataset),
        model_sha256=sha256_file(model),
        source_sha256=sha256_file(
            Path(__file__).resolve().parents[3]
            / "physical_ai/perception/quality_candidates_v5.py"
        ),
        box_atol=0.01,
        score_atol=1e-4,
        rows=rows,
        scope="Three preparation RGB per candidate; complete view/policy numerical comparison only, not quality",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "model", "output"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    result = check(a.dataset, a.model)
    write_new(a.output, result)
    print({k: result[k] for k in ("status", "dataset_sha256", "source_sha256")})
    raise SystemExit(0 if result["status"] == "PASS" else 1)
