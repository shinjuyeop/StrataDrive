#!/usr/bin/env python3
"""Full native static/dynamic PyTorch and ORT CPU/CUDA resolution probes."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from itertools import islice
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import RgbDataset, local_path
from physical_ai.perception.resolution_v1 import SIZES, ResolutionDetector, decode
from resolution_v1_common import PROBES, models, require, write_new
from check_model_screen_v1 import compare_top300, compare_detections


def check(base):
    _, manifest = models(base)
    probes = list(islice(RgbDataset(PROBES).frames(), 3))
    report = dict(
        schema="m10-resolution-numeric-v1",
        started_utc=datetime.now(timezone.utc).isoformat(),
        status="PASS",
        model_manifest_sha256=sha256_file(base / "models.json"),
        box_atol=0.1,
        score_atol=0.0001,
        cold_calls_excluded=0,
        cpu_node_fallback_disabled=True,
        rows=[],
        failures=[],
    )
    for size in SIZES:
        try:
            path = local_path(base, manifest["models"][str(size)]["path"])
            cpu, cuda = [
                ResolutionDetector(size, path, base / "models.json", mode)
                for mode in ("cpu", "cuda")
            ]
            for n, (source, frame) in enumerate(probes):
                ref = next(
                    r
                    for r in manifest["references"]
                    if r["size"] == size and r["probe"] == n
                )
                feed = cpu.prepare(frame)
                require(
                    source["rgb_sha256"] == ref["rgb_sha256"]
                    and hashlib.sha256(feed["images"].tobytes()).hexdigest()
                    == ref["tensor_sha256"],
                    "probe RGB/native tensor identity",
                )
                with np.load(
                    local_path(base, ref["file"]), allow_pickle=False
                ) as arrays:
                    expected = dict(arrays)
                outputs = [expected, cpu.raw(feed), cuda.raw(feed)]
                deltas = []
                for left, right in zip(outputs, outputs[1:]):
                    deltas.append(compare_top300(left, right))
                    compare_detections(
                        [asdict(d) for d in decode(left)],
                        [asdict(d) for d in decode(right)],
                    )
                report["rows"].append(
                    dict(
                        size=size,
                        probe=n,
                        rgb_sha256=source["rgb_sha256"],
                        passed=True,
                        deltas=deltas,
                        providers=cuda.session.get_providers(),
                        provider_options=cuda.session.get_provider_options(),
                    )
                )
            del cpu, cuda
        except Exception:
            report["status"] = "FAIL"
            report["failures"].append(dict(size=size, error=traceback.format_exc()))
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_new(base / "numeric.json", report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("base", type=Path)
    a = p.parse_args()
    r = check(a.base)
    print(r["status"], len(r["rows"]), "probes")
    sys.exit(0 if r["status"] == "PASS" else 1)
