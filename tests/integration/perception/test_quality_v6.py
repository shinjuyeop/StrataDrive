from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import subprocess
import sys
import tempfile
import numpy as np
from physical_ai.perception.contract import Detection
from physical_ai.perception.large_model_v6 import (
    LargeYoloX,
    OfflineResultV6,
    LARGE_SHA256,
)
from physical_ai.perception.quality_candidates_v3 import MEDIUM_SHA256, OfflineResult
from physical_ai.perception.quality_candidates_v6 import (
    combine,
    weak_proposals,
    QualityCandidateV6,
)
from physical_ai.perception.dataset import read_json
from quality_road_v6 import build, SURVEY, USED_SITES
from test_perception import frame


def support(box=(280, 150, 320, 190), scores=(0.3, 0.3, 0.3, 0.3, 0.3, 0.3)):
    return np.array([tuple(box) + tuple(scores)], np.float64)


class QualityV6PolicyTests(unittest.TestCase):
    def test_model_identity_is_not_interchangeable_with_s_or_m(self):
        f = frame()
        r = OfflineResultV6(f.identity, (), 1, 2, 3, LARGE_SHA256)
        r.validate()
        with self.assertRaises(ValueError):
            OfflineResult(f.identity, (), 1, 2, 3, LARGE_SHA256).validate()
        with self.assertRaises(ValueError):
            OfflineResultV6(f.identity, (), 1, 2, 3, MEDIUM_SHA256).validate()
        with TemporaryDirectory() as t:
            p = Path(t) / "wrong.onnx"
            p.write_bytes(b"wrong pinned bytes")
            with self.assertRaisesRegex(ValueError, "pinned large"):
                LargeYoloX(p, "cpu")
        with self.assertRaisesRegex(ValueError, "unknown v6"):
            QualityCandidateV6(Path("missing"), "bad")

    def test_private_support_cannot_become_output_without_published_proposal(self):
        self.assertEqual(combine((), (), support()), ())
        raw = np.zeros((1, 8400, 85), np.float32)
        raw[0, 0, :2] = (38, 22)
        raw[0, 0, 4] = 0.5
        raw[0, 0, 5] = 0.4
        weak = weak_proposals(raw)
        self.assertGreater(len(weak), 0)
        self.assertEqual(combine((), (), weak), ())
        raw[0, -1, 0] = np.nan
        with self.assertRaises(ValueError):
            weak_proposals(raw)

    def test_person_requires_person_support_even_when_overlapping_bicycle(self):
        person = Detection(0, 0.65, (280, 150, 320, 190))
        only_bike = support(scores=(0, 0.8, 0, 0, 0, 0))
        self.assertEqual(combine((), (person,), only_bike), ())
        self.assertEqual(
            combine((), (person,), support(scores=(0.15, 0, 0, 0, 0, 0))), (person,)
        )

    def test_view_body_disagreement_uses_qualified_crop_and_preserves_person(self):
        bus = Detection(5, 0.8, (280, 150, 320, 190))
        truck = Detection(7, 0.7, (280, 150, 320, 190))
        rider = Detection(0, 0.8, (280, 150, 320, 190))
        result = combine((bus, rider), (truck,), support(scores=(0, 0, 0, 0, 0.8, 0)))
        self.assertEqual(set(d.class_id for d in result), {0, 7})
        low = Detection(7, 0.4, truck.box)
        result = combine((bus, rider), (low,), support())
        self.assertEqual(set(d.class_id for d in result), {0, 5})

    def test_distinct_body_boxes_are_not_arbitrated_as_one_object(self):
        car = Detection(2, 0.8, (200, 120, 250, 160))
        bike = Detection(1, 0.65, (300, 160, 325, 190))
        result = combine((car,), (bike,), support(box=bike.box))
        self.assertEqual(set(d.class_id for d in result), {1, 2})

    def test_base_verification_only_removes_weak_fully_visible_vru(self):
        weak = Detection(0, 0.4, (280, 150, 300, 180))
        strong = Detection(0, 0.65, (310, 150, 330, 180))
        outside = Detection(0, 0.4, (10, 10, 20, 30))
        result = combine((weak, strong, outside), (), np.empty((0, 10)))
        self.assertNotIn(weak, result)
        self.assertIn(strong, result)
        self.assertIn(outside, result)

    def test_rejects_invalid_weak_proposals_and_over_capacity(self):
        for weak in (
            np.zeros((0, 7)),
            np.full((1, 10), np.nan),
            support(scores=(-1, 0, 0, 0, 0, 0)),
            support(box=(-1, 0, 1, 1)),
        ):
            with self.assertRaises(ValueError):
                combine((), (), weak)
        d = Detection(0, 0.5, (1, 1, 5, 5))
        with self.assertRaises(ValueError):
            combine((d,) * 101, (), np.empty((0, 10)))
        with self.assertRaises(ValueError):
            combine((), (Detection(0, 0.2, d.box),), support())

    def test_new_plan_excludes_every_consumed_site_and_replays_map_order(self):
        plans = build()
        survey = read_json(SURVEY)
        self.assertIn(31, USED_SITES)
        self.assertIn(35, USED_SITES)
        self.assertEqual(
            [p["spawn_point_index"] for p in plans[0]["partitions"].values()], [74, 80]
        )
        self.assertEqual(
            sum(len(p["cases"]) for p in plans[1]["partitions"].values()), 198
        )
        roads = {
            s["spawn_point_index"]: s["nodes"]["0"]["road_id"] for s in survey["sites"]
        }
        self.assertTrue(
            set(roads[n] for n in (74, 80)).isdisjoint(roads[n] for n in USED_SITES)
        )

    def test_quality_cli_accepts_v6_plan_and_copies_staging_before_server_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "capture"
            code = """
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'tests/integration/perception')
import run_quality_evaluation_v6
from quality_v6_common import PLAN
from physical_ai.perception.contract import sha256_file
with patch('quality_v6_common.check_freeze',return_value={'plan_sha256':sha256_file(PLAN)}), patch('subprocess.check_output',side_effect=RuntimeError('SOURCE_IDENTITY_REACHED')), patch('socket.socket'):
    run_quality_evaluation_v6.main()
"""
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    code,
                    "--engine",
                    temp,
                    "--source",
                    temp,
                    "--python",
                    sys.executable,
                    "--output",
                    str(output),
                    "--freeze",
                    str(Path(temp) / "freeze.json"),
                    "--plan",
                    str(
                        Path(__file__).resolve().parents[3]
                        / "profiles/perception-road-evaluation-v6.json"
                    ),
                    "--partition",
                    "development",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("SOURCE_IDENTITY_REACHED", result.stderr)
            self.assertTrue((output / "quality_staging_v5.py").is_file())
