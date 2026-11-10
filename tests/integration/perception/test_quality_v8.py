"""Fresh-map selection, fixed model identity and numeric denominator regressions."""

from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from physical_ai.perception.quality_candidates_v8 import (
    QualityCandidateV8,
    OfflineResultV8,
    LARGE_SHA256,
)
from physical_ai.perception.quality_candidates_v7 import TRAINED_SHA256
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from quality_road_v8 import build, select_fresh, SURVEY
from quality_road_v8b import build as build_revised
from quality_v8_common import validate_descriptors, check_numeric
from test_perception import frame


class QualityV8Tests(unittest.TestCase):
    def test_preparation_revision_changes_only_held_person_occluder_lateral(self):
        original, revised = build()[0], build_revised()[0]
        changed = []
        for part in original["partitions"]:
            for a, b in zip(
                original["partitions"][part]["cases"],
                revised["partitions"][part]["cases"],
            ):
                self.assertEqual(a["id"], b["id"])
                for before, after in zip(a["actors"], b["actors"]):
                    if before != after:
                        changed.append(
                            (part, a["stratum"], a["target_class"], before["role"])
                        )
                        self.assertEqual(before["right_m"], -0.6)
                        self.assertEqual(after["right_m"], -0.4)
                        for field in (
                            "road_node",
                            "route_distance_m",
                            "blueprint",
                            "class_id",
                            "yaw_offset_degrees",
                            "clearance_m",
                        ):
                            self.assertEqual(before[field], after[field])
        self.assertEqual(changed, [("holdout", "occluded", 0, "occluder")] * 3)

    def test_new_map_selection_is_order_independent_and_unchanged_gates(self):
        validate_descriptors()
        survey = read_json(SURVEY)
        reversed_survey = deepcopy(survey)
        reversed_survey["sites"].reverse()
        self.assertEqual(select_fresh(survey), select_fresh(reversed_survey))
        evaluation, preparation = build()
        self.assertEqual(evaluation["map"], "Town04_Opt")
        for part in evaluation["partitions"]:
            self.assertEqual(len(evaluation["partitions"][part]["cases"]), 81)
            self.assertEqual(len(preparation["partitions"][part]["cases"]), 99)
        survey["map"] = "Town03_Opt"
        with self.assertRaisesRegex(ValueError, "new Town04"):
            select_fresh(survey)

    def test_numeric_both_candidates_and_cold_calls_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "preparation-development-data"
            data.mkdir()
            (data / "rgb.json").write_text("{}\n")
            report = dict(
                schema="m10-model-check-v8",
                status="PASS",
                model_sha256=LARGE_SHA256,
                dataset_sha256=sha256_file(data / "rgb.json"),
                atol=0.001,
                rtol=0.0001,
                box_atol=0.01,
                score_atol=0.0001,
                cpu_node_fallback_disabled=True,
                cold_calls_excluded=0,
                rows=[
                    dict(candidate=c, passed=True)
                    for c in ("baseline", "large-v8")
                    for _ in range(3)
                ],
            )
            path = root / "model-check.json"
            path.write_text(json.dumps(report))
            check_numeric(path)
            report["rows"][0]["candidate"] = "large-v8"
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "candidate denominator"):
                check_numeric(path)
            report["rows"][0]["candidate"] = "baseline"
            report["cold_calls_excluded"] = 1
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "raw and complete"):
                check_numeric(path)

    def test_trained_checkpoint_cannot_impersonate_official_l(self):
        f = frame()
        OfflineResultV8(f.identity, (), 1, 2, 3, LARGE_SHA256).validate()
        with self.assertRaises(ValueError):
            OfflineResultV8(f.identity, (), 1, 2, 3, TRAINED_SHA256).validate()

    def test_candidate_identity_before_inference(self):
        with self.assertRaisesRegex(ValueError, "unknown v8"):
            QualityCandidateV8(Path("missing"), "trained-v1")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "wrong.onnx"
            path.write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError, "pinned large"):
                QualityCandidateV8(path, "large-v8", "cpu")
