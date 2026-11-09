from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from physical_ai.perception.dataset import read_json
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.quality_candidates_v3 import INPUT_PROFILE
from prepare_quality_v4 import assess_visibility
from quality_v4_common import (
    PLAN,
    PROTOCOL,
    validate_descriptors,
    freeze,
    check_freeze,
    check_selection,
)
from quality_benchmark import write_new
from quality_benchmark_v4 import score
from test_quality_road_preparation_v4 import fixture
from test_quality_v2 import symbolic_v2, write


def evaluation_fixture():
    cases, scenes, truth = fixture()
    for scene in scenes:
        for actor in scene["actors"]:
            actor["included"] = True
    return cases[:81], scenes[:81], truth[:81]


class QualityV4Tests(unittest.TestCase):
    def test_independent_81_scene_score_and_rgb_identity_tamper(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("quality_v4_common.check_numeric"),
        ):
            root = Path(tmp)
            run, _ = symbolic_v2(root)
            write(root / "model-check.json", {})
            frozen = root / "v4-freeze.json"
            freeze(frozen)
            cases = read_json(PLAN)["partitions"]["development"]["cases"]
            for name, field in (
                ("rgb.json", "frames"),
                ("evaluation-only-gt.json", "frames"),
                ("benchmark.json", "scenes"),
            ):
                data = read_json(root / name)
                data["schema"] = data["schema"].replace(
                    "quality-dataset-v2", "quality-dataset-v4"
                )
                for row, case in zip(data[field], cases):
                    row["scene"] = case["id"]
                write(root / name, data)
            truth = read_json(root / "evaluation-only-gt.json")
            truth["rgb_manifest_sha256"] = sha256_file(root / "rgb.json")
            write(root / "evaluation-only-gt.json", truth)
            meta = read_json(root / "benchmark.json")
            meta.update(
                plan_sha256=sha256_file(PLAN),
                protocol_sha256=sha256_file(PROTOCOL),
                rgb_manifest_sha256=sha256_file(root / "rgb.json"),
                truth_sha256=sha256_file(root / "evaluation-only-gt.json"),
                exclusion_sha256=read_json(frozen)["exclusion_sha256"],
            )
            write(root / "benchmark.json", meta)
            visibility = assess_visibility(cases, meta["scenes"], truth["frames"])
            write(root / "visibility.json", visibility)
            seal = read_json(root / "benchmark-seal.json")
            seal.update(
                schema="m10-quality-data-seal-v4",
                metadata_sha256=sha256_file(root / "benchmark.json"),
                visibility_sha256=sha256_file(root / "visibility.json"),
            )
            for key in (
                "plan_sha256",
                "protocol_sha256",
                "rgb_manifest_sha256",
                "truth_sha256",
                "exclusion_sha256",
            ):
                seal[key] = meta[key]
            write(root / "benchmark-seal.json", seal)
            run.update(
                schema="m10-quality-run-v4",
                freeze_sha256=sha256_file(frozen),
                protocol_sha256=sha256_file(PROTOCOL),
                input_profile=INPUT_PROFILE,
                dataset_sha256=sha256_file(root / "rgb.json"),
                dataset_seal_sha256=sha256_file(root / "benchmark-seal.json"),
            )
            for row, case in zip(run["rows"], cases):
                row["scene"] = case["id"]
            write(root / "result.json", run)
            self.assertEqual(
                score(root, root / "result.json", frozen)["absolute_quality"], "PASS"
            )
            run["rows"][0]["rgb_sha256"] = "0" * 64
            write(root / "result.json", run)
            with self.assertRaisesRegex(ValueError, "source identity"):
                score(root, root / "result.json", frozen)

    def test_preparation_seal_and_unchanged_numeric_gates(self):
        validate_descriptors()
        with tempfile.TemporaryDirectory() as tmp:
            bad = read_json(PROTOCOL)
            bad["absolute_quality"]["micro_precision_min"] = 0.8
            path = Path(tmp) / "protocol.json"
            write_new(path, bad)
            with patch("quality_v4_common.PROTOCOL", path):
                with self.assertRaisesRegex(ValueError, "strict gates"):
                    validate_descriptors()

    def test_background_instance_cannot_replace_planned_actor(self):
        cases, scenes, truth = evaluation_fixture()
        self.assertEqual(assess_visibility(cases, scenes, truth)["status"], "PASS")
        truth[2]["objects"][0]["instance_id"] = 60000
        scenes[2]["actors"][0]["included"] = False
        result = assess_visibility(cases, scenes, truth)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(len(result["missing_actors"]), 1)

    def test_rider_is_required_even_when_two_wheeler_is_visible(self):
        cases, scenes, truth = evaluation_fixture()
        truth[6]["objects"] = [
            o for o in truth[6]["objects"] if 13 not in o["semantic_tags"]
        ]
        result = assess_visibility(cases, scenes, truth)
        self.assertTrue(result["gates"]["all_planned_actors_visible"])
        self.assertFalse(result["gates"]["all_two_wheeler_riders_visible"])

    def test_visibility_denominator_and_inclusion_tamper(self):
        cases, scenes, truth = evaluation_fixture()
        with self.assertRaisesRegex(ValueError, "denominator"):
            assess_visibility(cases[:-1], scenes[:-1], truth[:-1])
        scenes[0]["actors"][0]["included"] = False
        with self.assertRaisesRegex(ValueError, "inclusion binding"):
            assess_visibility(cases, scenes, truth)

    def test_freeze_detects_source_and_nomination_identity_tamper(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("quality_v4_common.check_numeric"),
        ):
            root = Path(tmp)
            write_new(root / "model-check.json", {})
            path = root / "freeze.json"
            value = freeze(path)
            self.assertEqual(check_freeze(path), value)
            bad = deepcopy(value)
            bad["sources"]["tests/integration/perception/prepare_quality_v4.py"] = (
                "0" * 64
            )
            write_new(root / "bad.json", bad)
            with self.assertRaisesRegex(ValueError, "source changed"):
                check_freeze(root / "bad.json")
            selection = dict(
                schema="m10-quality-selection-v4",
                freeze_sha256="0" * 64,
                selected="medium-v3",
                runtime_promotion=False,
            )
            write_new(root / "selection.json", selection)
            with self.assertRaisesRegex(ValueError, "nomination"):
                check_selection(root / "selection.json", path)

    def test_holdout_without_nomination_is_rejected_before_server_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Valid frozen identity is injected in the child; no CARLA import or RPC is used.
            code = """
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, 'tests/integration/perception')
import run_quality_evaluation_v4
from physical_ai.perception.contract import sha256_file
with patch('quality_v4_common.check_freeze', return_value={'plan_sha256':sha256_file(Path(sys.argv[sys.argv.index('--plan')+1]))}):
    run_quality_evaluation_v4.main()
"""
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    code,
                    "--engine",
                    str(root / "absent-engine"),
                    "--source",
                    str(root / "absent-source"),
                    "--python",
                    sys.executable,
                    "--output",
                    str(root / "capture"),
                    "--freeze",
                    str(root / "freeze.json"),
                    "--plan",
                    str(PLAN),
                    "--partition",
                    "holdout",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(
                "holdout requires selection before server launch", result.stderr
            )
            self.assertFalse((root / "capture").exists())

    def test_sealed_development_plan_passes_cli_schema_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = """
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, 'tests/integration/perception')
import run_quality_evaluation_v4
from physical_ai.perception.contract import sha256_file
with patch('quality_v4_common.check_freeze', return_value={'plan_sha256':sha256_file(Path(sys.argv[sys.argv.index('--plan')+1]))}), patch('subprocess.check_output', side_effect=RuntimeError('PRELAUNCH_REACHED_SOURCE_IDENTITY')):
    run_quality_evaluation_v4.main()
"""
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    code,
                    "--engine",
                    str(root / "absent-engine"),
                    "--source",
                    str(root / "absent-source"),
                    "--python",
                    sys.executable,
                    "--output",
                    str(root / "capture"),
                    "--freeze",
                    str(root / "freeze.json"),
                    "--plan",
                    str(PLAN),
                    "--partition",
                    "development",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("PRELAUNCH_REACHED_SOURCE_IDENTITY", result.stderr)
            self.assertTrue((root / "capture/capture-probe.py").is_file())
