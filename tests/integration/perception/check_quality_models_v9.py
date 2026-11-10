#!/usr/bin/env python3
"""CPU/CUDA plus independent native reference checks before fresh evaluation."""

import argparse
from dataclasses import asdict
import hashlib
from itertools import islice
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import RgbDataset, read_json
from physical_ai.perception.quality_candidates_v9 import (
    CANDIDATES,
    MODELS,
    QualityCandidateV9,
    decode,
)
from check_model_screen_v1 import compare_top300, compare_detections
from quality_v9_common import check_preparation, require, write_new


def check(base, baseline, dfine, reference, output):
    check_preparation(base)
    require(
        (base / "preparation-reviewed.flag").exists(),
        "visual review before numeric inference",
    )
    data = base / "preparation-development-data/rgb.json"
    frames = list(islice(RgbDataset(data).frames(), 3))
    expected = read_json(reference / "reference.json")
    require(
        expected["status"] == "PASS"
        and expected["dataset_sha256"] == sha256_file(data),
        "native reference RGB identity",
    )
    report = dict(
        schema="m10-model-check-v9",
        status="PASS",
        models=MODELS,
        dataset_sha256=sha256_file(data),
        reference_sha256=sha256_file(reference / "reference.json"),
        baseline_raw_atol=0.001,
        baseline_raw_rtol=0.0001,
        baseline_box_atol=0.01,
        dfine_box_atol=0.1,
        score_atol=0.0001,
        cpu_node_fallback_disabled=True,
        cold_calls_excluded=0,
        rows=[],
        failures=[],
    )
    for candidate, path in zip(CANDIDATES, (baseline, dfine)):
        try:
            cpu, cuda = [
                QualityCandidateV9(path, candidate, mode) for mode in ("cpu", "cuda")
            ]
            for n, (source, frame) in enumerate(frames):
                require(
                    source["rgb_sha256"] == expected["rows"][n]["rgb_sha256"],
                    "new preparation probe identity",
                )
                feed = cpu.prepare(frame)
                field = (
                    "baseline_tensor_sha256"
                    if candidate == "baseline"
                    else "dfine_tensor_sha256"
                )
                require(
                    hashlib.sha256(feed["images"].tobytes()).hexdigest()
                    == expected["rows"][n][field],
                    "independent native input tensor bytes",
                )
                names = [o.name for o in cpu.detector.session.get_outputs()]
                actual = [
                    dict(zip(names, b.detector.session.run(None, feed)))
                    for b in (cpu, cuda)
                ]
                family = "baseline" if candidate == "baseline" else "dfine"
                with np.load(
                    reference / f"{family}-{n}.npz", allow_pickle=False
                ) as arrays:
                    native = dict(arrays)
                deltas = []
                for left, right in [(native, actual[0]), (actual[0], actual[1])]:
                    if candidate == "baseline":
                        np.testing.assert_allclose(
                            left["output"], right["output"], atol=0.001, rtol=0.0001
                        )
                        deltas.append(
                            dict(
                                raw_max_abs=float(
                                    np.max(np.abs(left["output"] - right["output"]))
                                )
                            )
                        )
                    else:
                        deltas.append(compare_top300(left, right))
                    compare_detections(
                        [asdict(d) for d in decode(candidate, left)],
                        [asdict(d) for d in decode(candidate, right)],
                        box_tol=0.01 if candidate == "baseline" else 0.1,
                    )
                report["rows"].append(
                    dict(
                        candidate=candidate,
                        probe=n,
                        rgb_sha256=source["rgb_sha256"],
                        passed=True,
                        deltas=deltas,
                        providers=cuda.detector.session.get_providers(),
                        provider_options=cuda.detector.session.get_provider_options(),
                    )
                )
            del cpu, cuda
        except Exception:
            report["status"] = "FAIL"
            report["failures"].append(
                dict(candidate=candidate, error=traceback.format_exc())
            )
    write_new(output, report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "baseline", "dfine", "reference", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    report = check(a.base, a.baseline, a.dfine, a.reference, a.output)
    print(report["status"])
    if report["status"] != "PASS":
        sys.exit(1)
