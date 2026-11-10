"""Native policy and numeric evidence must fail closed before fresh acquisition."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import numpy as np

from physical_ai.perception.contract import sha256_file
from physical_ai.perception.quality_candidates_v9 import (
    CANDIDATE,
    CANDIDATES,
    MODELS,
    decode,
)
from quality_benchmark import write_new
from quality_v9_common import check_numeric, validate_descriptors


class QualityV9Tests(unittest.TestCase):
    def test_fixed_policy_and_fresh_map_descriptors(self):
        validate_descriptors()

    def test_native_vector_keeps_bicycle_but_rejects_lower_person_score(self):
        raw = dict(
            labels=np.full((1, 300), 79, np.int64),
            scores=np.zeros((1, 300), np.float32),
            boxes=np.tile(np.array([[[10, 10, 30, 30]]], np.float32), (1, 300, 1)),
        )
        raw["labels"][0, :3] = [0, 1, 2]
        raw["scores"][0, :3] = [0.55, 0.45, 0.75]
        self.assertEqual([d.class_id for d in decode(CANDIDATE, raw)], [2, 1])
        with self.assertRaises(ValueError):
            decode("new-threshold", raw)

    def test_duplicate_probe_wrong_rgb_and_cold_exclusion_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "preparation-development-data/rgb.json"
            dataset.parent.mkdir()
            write_new(dataset, dict(frames=[dict(rgb_sha256=str(n)) for n in range(3)]))
            report = dict(
                schema="m10-model-check-v9",
                status="PASS",
                models=MODELS,
                dataset_sha256=sha256_file(dataset),
                baseline_raw_atol=0.001,
                baseline_raw_rtol=0.0001,
                baseline_box_atol=0.01,
                dfine_box_atol=0.1,
                score_atol=0.0001,
                cpu_node_fallback_disabled=True,
                cold_calls_excluded=0,
                rows=[
                    dict(
                        candidate=c,
                        probe=n,
                        rgb_sha256=str(n),
                        passed=True,
                        providers=["CUDAExecutionProvider"],
                    )
                    for c in CANDIDATES
                    for n in range(3)
                ],
            )
            good = root / "good.json"
            write_new(good, report)
            check_numeric(good)
            for n, mutation in enumerate(("probe", "rgb", "cold")):
                bad = deepcopy(report)
                if mutation == "probe":
                    bad["rows"][1]["probe"] = 0
                elif mutation == "rgb":
                    bad["rows"][1]["rgb_sha256"] = "wrong"
                else:
                    bad["cold_calls_excluded"] = 1
                path = root / f"bad-{n}.json"
                write_new(path, bad)
                with self.assertRaises(ValueError):
                    check_numeric(path)
