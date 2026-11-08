from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from physical_ai.perception.contract import (
    FrameIdentity,
    PerceptionResult,
    MODEL_SHA256,
    sha256_file,
)
from physical_ai.perception.quality_candidates_v3 import (
    OfflineResult,
    MEDIUM_SHA256,
    MediumYoloX,
    INPUT_PROFILE,
)
from quality_v3_common import (
    PLAN,
    PREPARATION_PLAN,
    PROTOCOL,
    validate_plan,
    validate_descriptors,
    check_preparation,
    check_model_report,
    freeze,
    read_json,
)
from quality_benchmark_v3 import score
from test_quality_v2 import symbolic_v2, write


def preparation_report():
    cases = read_json(PREPARATION_PLAN)["partitions"]["preparation"]["cases"]
    return dict(
        schema="m10-quality-preparation-v3",
        status="PASS",
        frames=len(cases),
        plan_sha256=sha256_file(PREPARATION_PLAN),
        missing_actors=0,
        occlusion_failures=0,
        inference_performed=False,
        completed_utc="2026-01-01T00:00:00+00:00",
        rgb_sha256=[],
        rgb_manifest_sha256="0" * 64,
        planned_targets=[
            dict(weather=c["weather"], stratum=c["stratum"], actor=a)
            for c in cases
            for a in c["actors"]
            if a["role"] == "target"
        ],
    )


class QualityV3Tests(unittest.TestCase):
    def test_denied_asset_cli_never_starts_server_or_creates_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = read_json(PLAN)
            plan["partitions"]["development"]["cases"][0]["actors"][0]["blueprint"] = (
                "vehicle.carlamotors.european_hgv"
            )
            write(root / "bad-plan.json", plan)
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("run_capture_v3.py")),
                    "--engine",
                    str(root / "missing-engine"),
                    "--source",
                    str(root / "missing-source"),
                    "--python",
                    sys.executable,
                    "--output",
                    str(root / "capture"),
                    "--mode",
                    "quality-v3",
                    "--plan",
                    str(root / "bad-plan.json"),
                    "--partition",
                    "development",
                    "--quality",
                    "Epic",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("before server launch", result.stderr)
            self.assertFalse((root / "capture").exists())

    def test_failed_numeric_check_cannot_be_used_for_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model-check.json"
            write(path, dict(schema="m10-model-check-v3", status="FAIL"))
            with self.assertRaisesRegex(ValueError, "numeric"):
                check_model_report(path)

    def test_model_result_cannot_impersonate_live_s_contract(self):
        result = OfflineResult(
            FrameIdentity(1, 7, 1, 50_000_000), (), 0, 0, 0, MEDIUM_SHA256
        )
        result.validate()
        with self.assertRaises(ValueError):
            PerceptionResult(result.identity, (), 0, 0, 0, MEDIUM_SHA256).validate()
        for r in (
            replace(result, model_sha256="0" * 64),
            replace(result, input_profile="BGR"),
            replace(result, inference_ns=-1),
            replace(result, identity=None),
        ):
            with self.subTest(r=r), self.assertRaises(ValueError):
                r.validate()

    def test_wrong_medium_bytes_rejected_before_runtime_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wrong.onnx"
            path.write_bytes(b"not a model")
            # ONNX Runtime is optional for logical tests. Identity must reject first.
            with patch.dict("sys.modules", {"onnxruntime": object()}):
                with self.assertRaisesRegex(ValueError, "identity"):
                    MediumYoloX(path)

    def test_denied_asset_and_nonfinite_pose_fail_prelaunch_policy(self):
        plan = read_json(PLAN)
        validate_plan(plan)
        for value in (float("nan"), float("inf"), True):
            changed = deepcopy(plan)
            changed["partitions"]["development"]["cases"][0]["actors"][0][
                "forward_m"
            ] = value
            with self.assertRaisesRegex(ValueError, "pose"):
                validate_plan(changed)
        changed = deepcopy(plan)
        changed["partitions"]["development"]["cases"][0]["actors"][0]["blueprint"] = (
            "vehicle.carlamotors.european_hgv"
        )
        with self.assertRaisesRegex(ValueError, "NW"):
            validate_plan(changed)

    def test_preparation_requires_every_target_and_excludes_consumed_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preparation.json"
            report = preparation_report()
            write(path, report)
            check_preparation(path)
            changes = [
                lambda r: r.update(status="FAIL"),
                lambda r: r.update(missing_actors=1),
                lambda r: r.update(inference_performed=True),
                lambda r: r.update(frames=143),
                lambda r: r.update(planned_targets=[]),
                lambda r: r.update(rgb_sha256=["f" * 64]),
            ]
            for n, change in enumerate(changes):
                changed = deepcopy(report)
                change(changed)
                write(path, changed)
                with self.subTest(mutation=n), self.assertRaises(ValueError):
                    check_preparation(path)

    def test_descriptors_keep_numeric_gates_and_distinct_case_ids(self):
        validate_descriptors()
        cases = [c for p in read_json(PLAN)["partitions"].values() for c in p["cases"]]
        self.assertEqual(len({c["id"] for c in cases}), 162)
        self.assertTrue(all(c["id"].startswith("v3-") for c in cases))

    def test_independent_81_case_fixture_and_wrong_model_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, _ = symbolic_v2(root)
            write(root / "preparation-acceptance.json", preparation_report())
            write(
                root / "model-check.json",
                dict(
                    schema="m10-model-check-v3",
                    status="PASS",
                    model_sha256=MEDIUM_SHA256,
                    input_profile=INPUT_PROFILE,
                    atol=1e-3,
                    rtol=1e-4,
                    cpu_node_fallback_disabled=True,
                    cuda_providers=["CUDAExecutionProvider"],
                    cold_calls_excluded=0,
                    dataset_sha256="0" * 64,
                    rows=[
                        dict(
                            equal_tensor=True,
                            comparisons={
                                k: dict(equal=True) for k in ("cuda", "opencv")
                            },
                        )
                        for _ in range(3)
                    ],
                ),
            )
            frozen = root / "v3-freeze.json"
            freeze(frozen)
            cases = read_json(PLAN)["partitions"]["development"]["cases"]
            for name, field in (
                ("rgb.json", "frames"),
                ("evaluation-only-gt.json", "frames"),
                ("benchmark.json", "scenes"),
            ):
                data = read_json(root / name)
                data["schema"] = data["schema"].replace(
                    "quality-dataset-v2", "quality-dataset-v3"
                )
                for row, c in zip(data[field], cases):
                    row["scene"] = c["id"]
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
            )
            write(root / "benchmark.json", meta)
            seal = read_json(root / "benchmark-seal.json")
            seal.update(
                schema="m10-quality-data-seal-v3",
                metadata_sha256=sha256_file(root / "benchmark.json"),
            )
            for key in (
                "plan_sha256",
                "protocol_sha256",
                "rgb_manifest_sha256",
                "truth_sha256",
            ):
                seal[key] = meta[key]
            write(root / "benchmark-seal.json", seal)
            run.update(
                schema="m10-quality-run-v3",
                freeze_sha256=sha256_file(frozen),
                protocol_sha256=sha256_file(PROTOCOL),
                input_profile=INPUT_PROFILE,
                dataset_sha256=sha256_file(root / "rgb.json"),
                dataset_seal_sha256=sha256_file(root / "benchmark-seal.json"),
            )
            for row, c in zip(run["rows"], cases):
                row["scene"] = c["id"]
            write(root / "result.json", run)
            self.assertEqual(
                score(root, root / "result.json", frozen)["absolute_quality"], "PASS"
            )
            run.update(candidate="medium-v3", model_sha256=MODEL_SHA256)
            write(root / "result.json", run)
            with self.assertRaisesRegex(ValueError, "provenance"):
                score(root, root / "result.json", frozen)
            run["model_sha256"] = MEDIUM_SHA256
            write(root / "result.json", run)
            self.assertEqual(
                score(root, root / "result.json", frozen)["micro"]["fn"], 0
            )


if __name__ == "__main__":
    unittest.main()
