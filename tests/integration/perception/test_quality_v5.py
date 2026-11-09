from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
import subprocess
import sys
import tempfile
from unittest.mock import patch
import numpy as np

from physical_ai.perception.contract import Detection
from physical_ai.perception.quality_candidates_v5 import (
    combine,
    weak_vru_proposals,
    QualityCandidateV5,
    POLICY,
)
from physical_ai.perception.quality_candidates_v3 import OfflineResult, MEDIUM_SHA256
from physical_ai.perception.dataset import read_json
from quality_road_v5 import SURVEY, USED_SITES, select_fresh, build
from test_perception import frame
from quality_staging_v5 import staging_pose


def weak(box=(300, 150, 320, 190), scores=(0.3, 0.3, 0.3)):
    return np.array([tuple(box) + tuple(scores)], dtype=np.float64)


class QualityV5PolicyTests(unittest.TestCase):
    def test_quality_cli_accepts_v5_plan_and_copies_staging_before_server_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "capture"
            code = """
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'tests/integration/perception')
import run_quality_evaluation_v5
from quality_v5_common import PLAN
from physical_ai.perception.contract import sha256_file
with patch('quality_v5_common.check_freeze',return_value={'plan_sha256':sha256_file(PLAN)}), patch('subprocess.check_output',side_effect=RuntimeError('SOURCE_IDENTITY_REACHED')), patch('socket.socket'):
    run_quality_evaluation_v5.main()
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
                        / "profiles/perception-road-evaluation-v5.json"
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

    def test_temporary_staging_preserves_final_road_pose_and_separates_actors(self):
        pose = dict(
            location=dict(x=20, y=30, z=1), rotation=dict(pitch=2, yaw=90, roll=1)
        )
        a, b = staging_pose(pose, 0), staging_pose(pose, 1)
        self.assertEqual(pose["location"]["z"], 1)
        self.assertEqual((a["location"]["x"], a["location"]["y"]), (20, 30))
        self.assertEqual(a["rotation"], pose["rotation"])
        self.assertEqual((a["location"]["z"], b["location"]["z"]), (51, 61))

    def test_staging_rejects_invalid_index_or_nonfinite_position(self):
        pose = dict(
            location=dict(x=20, y=30, z=1), rotation=dict(pitch=0, yaw=0, roll=0)
        )
        for index in (-1, 100, True, 1.5):
            with self.assertRaises(ValueError):
                staging_pose(pose, index)
        pose["location"]["x"] = float("nan")
        with self.assertRaises(ValueError):
            staging_pose(pose, 0)

    def test_low_support_never_becomes_a_published_detection(self):
        raw = np.zeros((1, 8400, 85), np.float32)
        raw[0, 0, :2] = (38, 22)
        raw[0, 0, 4] = 0.5
        raw[0, 0, 5] = 0.4
        proposals = weak_vru_proposals(raw)
        self.assertEqual(proposals.shape, (1, 7))
        self.assertEqual(combine((), (), proposals, consensus=True), ())
        predicted = Detection(0, 0.4, (300.0, 172.0, 308.0, 180.0))
        self.assertEqual(
            combine((), (predicted,), proposals, consensus=True), (predicted,)
        )
        raw[0, 7000, 80] = np.nan
        with self.assertRaises(ValueError):
            weak_vru_proposals(raw)

    def test_crop_person_needs_semantic_support_or_strong_family_support(self):
        person = Detection(0, 0.5, (300.0, 150.0, 320.0, 190.0))
        self.assertEqual(
            combine((), (person,), weak(scores=(0.1, 0.7, 0.1)), consensus=True), ()
        )
        strong = replace(person, score=0.8)
        self.assertEqual(
            combine((), (strong,), weak(scores=(0.1, 0.7, 0.1)), consensus=True),
            (strong,),
        )
        self.assertEqual(
            combine((), (person,), np.empty((0, 7)), consensus=False), (person,)
        )

    def test_base_verification_applies_only_inside_available_crop(self):
        person = Detection(0, 0.5, (300.0, 150.0, 320.0, 190.0))
        self.assertEqual(combine((person,), (), weak(), consensus=True), ())
        outside = replace(person, box=(20.0, 30.0, 40.0, 80.0))
        self.assertEqual(combine((outside,), (), weak(), consensus=True), (outside,))
        strong = replace(person, score=POLICY["strong_vru_score"])
        self.assertEqual(combine((strong,), (), weak(), consensus=True), (strong,))
        self.assertEqual(
            combine((person,), (person,), weak(), consensus=True), (person,)
        )

    def test_body_conflicts_do_not_suppress_person_rider(self):
        box = (300.0, 150.0, 320.0, 190.0)
        person, bike = Detection(0, 0.9, box), Detection(1, 0.8, box)
        self.assertEqual(
            combine((person, bike), (), weak(), consensus=True), (person, bike)
        )
        car, truck = Detection(2, 0.4, box), Detection(7, 0.8, box)
        self.assertEqual(combine((car, truck), (), weak(), consensus=True), (truck,))
        other = replace(car, box=(315.0, 150.0, 335.0, 190.0))
        self.assertEqual(
            combine((other, truck), (), weak(), consensus=True), (truck, other)
        )

    def test_invalid_or_low_score_data_cannot_hide_behind_filter(self):
        person = Detection(0, 0.34, (300.0, 150.0, 320.0, 190.0))
        with self.assertRaises(ValueError):
            combine((), (person,), np.empty((0, 7)), consensus=True)
        for value in (
            np.ones((1, 4)),
            weak(scores=(1.1, 0.3, 0.3)),
            weak(box=(330, 150, 320, 190)),
        ):
            with self.assertRaises(ValueError):
                combine((), (), value, consensus=True)

    def test_new_sites_exclude_all_old_roads_and_ignore_query_order(self):
        survey = read_json(SURVEY)
        self.assertEqual(select_fresh(survey), [31, 35])
        survey["sites"].reverse()
        self.assertEqual(select_fresh(survey), [31, 35])
        e, p = build()
        self.assertEqual(sum(len(v["cases"]) for v in e["partitions"].values()), 162)
        self.assertEqual(sum(len(v["cases"]) for v in p["partitions"].values()), 198)
        self.assertFalse(
            set(USED_SITES) & {v["spawn_point_index"] for v in e["partitions"].values()}
        )

    def test_candidate_preserves_identity_and_actual_medium_hash(self):
        raw = np.zeros((1, 8400, 85), np.float32)
        calls = []

        def execute(*args):
            calls.append(args)
            return [raw]

        def infer(camera):
            calls.append(camera.identity)
            return OfflineResult(camera.identity, (), 0, 0, 0, MEDIUM_SHA256)

        fake = SimpleNamespace(session=SimpleNamespace(run=execute), infer=infer)
        with (
            patch(
                "physical_ai.perception.quality_candidates_v5.MediumYoloX",
                return_value=fake,
            ),
            patch("physical_ai.perception.quality_candidates_v5.image_health"),
        ):
            backend = QualityCandidateV5(Path("unused"), "medium-consensus-v5")
            camera = frame()
            result = backend.infer(camera)
            result.validate()
            self.assertEqual(result.identity, camera.identity)
            self.assertEqual(result.model_sha256, MEDIUM_SHA256)
            self.assertEqual(len(calls), 2)
