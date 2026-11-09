from pathlib import Path
import json
import tempfile
import unittest
from physical_ai.perception.quality_candidates_v7 import (
    QualityCandidateV7,
    OfflineResultV7,
    TRAINED_SHA256,
)
from physical_ai.perception.large_model_v6 import OfflineResultV6, LARGE_SHA256
from physical_ai.perception.quality_candidates_v3 import MEDIUM_SHA256
from quality_road_v7 import build, USED_SITES
from quality_v7_common import validate_descriptors, check_numeric
from physical_ai.perception.contract import sha256_file
from test_perception import frame


class QualityV7Tests(unittest.TestCase):
    def test_numeric_report_requires_both_candidates_without_cold_exclusion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "preparation-development-data"
            data.mkdir()
            (data / "rgb.json").write_text("{}\n")
            report = dict(
                schema="m10-model-check-v7",
                status="PASS",
                model_sha256=TRAINED_SHA256,
                dataset_sha256=sha256_file(data / "rgb.json"),
                atol=0.001,
                rtol=0.0001,
                box_atol=0.01,
                score_atol=0.0001,
                cpu_node_fallback_disabled=True,
                cold_calls_excluded=0,
                rows=[
                    dict(candidate=c, passed=True)
                    for c in ("baseline", "trained-v1")
                    for _ in range(3)
                ],
            )
            path = root / "model-check.json"
            path.write_text(json.dumps(report))
            check_numeric(path)
            report["rows"][0]["candidate"] = "trained-v1"
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "candidate denominator"):
                check_numeric(path)
            report["rows"][0]["candidate"] = "baseline"
            report["cold_calls_excluded"] = 1
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "raw and complete"):
                check_numeric(path)

    def test_fresh_roads_reserved_holdout_and_unchanged_descriptors(self):
        validate_descriptors()
        evaluation, preparation = build()
        self.assertEqual(
            [p["spawn_point_index"] for p in evaluation["partitions"].values()],
            [215, 127],
        )
        self.assertTrue({74, 80, 104}.issubset(USED_SITES))
        for name, p in evaluation["partitions"].items():
            self.assertEqual(len(p["cases"]), 81)
            self.assertEqual(len(preparation["partitions"][name]["cases"]), 99)
            for c in p["cases"]:
                for actor in c["actors"]:
                    self.assertNotIn(actor["road_node"]["road_id"], (52, 28, 3, 4))

    def test_trained_model_cannot_impersonate_legacy_envelopes(self):
        f = frame()
        OfflineResultV7(f.identity, (), 1, 2, 3, TRAINED_SHA256).validate()
        with self.assertRaises(ValueError):
            OfflineResultV6(f.identity, (), 1, 2, 3, TRAINED_SHA256).validate()
        for digest in (MEDIUM_SHA256, LARGE_SHA256):
            with self.assertRaises(ValueError):
                OfflineResultV7(f.identity, (), 1, 2, 3, digest).validate()

    def test_candidate_identity_rejected_before_model_execution(self):
        with self.assertRaisesRegex(ValueError, "unknown v7"):
            QualityCandidateV7(Path("missing"), "large-v6")
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary) / "wrong.onnx"
            p.write_bytes(b"wrong weights")
            with self.assertRaisesRegex(ValueError, "pinned trained"):
                QualityCandidateV7(p, "trained-v1", "cpu")
