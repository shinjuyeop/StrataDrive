"""Resolution input identity, development isolation and raw-to-primary regression."""

from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.model_screen_v1 import prepare_rgb as original_prepare
from physical_ai.perception.resolution_v1 import prepare_rgb, decode
from quality_annotation import SEMANTICS_BY_CLASS
from resolution_v1_common import ROOT, development, safe_input, write_new
from run_resolution_v1 import quality, score, rank, nonregression, json_detections


def fixture():
    cases = read_json(ROOT / "profiles/perception-road-evaluation-v9.json")[
        "partitions"
    ]["development"]["cases"]
    scenes, truths, frames = [], [], []
    for n, case in enumerate(cases):
        actors, objects = [], []
        for index, actor in enumerate(case["actors"], 1):
            actors.append(
                dict(class_id=actor["class_id"], actor_id=index, role=actor["role"])
            )
            classes = [actor["class_id"]] + ([0] if actor["class_id"] in (1, 3) else [])
            for c in classes:
                objects.append(
                    dict(
                        class_id=c,
                        instance_id=index,
                        box=[index * 40, 10, index * 40 + 20, 30],
                        visible_pixels=400,
                        semantic_tags=[13]
                        if c == 0 and actor["class_id"] in (1, 3)
                        else [SEMANTICS_BY_CLASS[c][0]],
                    )
                )
        scenes.append(
            dict(
                scene=case["id"],
                stratum=case["stratum"],
                target_class=case["target_class"],
                actors=actors,
            )
        )
        truths.append(dict(scene=case["id"], frame=n + 1, objects=objects, excluded=[]))
        frames.append(
            dict(
                scene=case["id"],
                frame=n + 1,
                source_ns=(n + 1) * 50_000_000,
                rgb_sha256="a" * 64,
            )
        )
    return scenes, truths, frames


class ResolutionV1Tests(unittest.TestCase):
    def test_native640_tensor_is_exact_and_original_size_stays_width_height(self):
        rgb = np.random.default_rng(4).integers(0, 256, (384, 640, 3), np.uint8)
        for size in (640, 960, 1280):
            feed = prepare_rgb(rgb, size)
            self.assertEqual(feed["images"].shape, (1, 3, size, size))
            self.assertEqual(feed["images"].dtype, np.float32)
            self.assertTrue(feed["images"].flags.c_contiguous)
            self.assertEqual(feed["orig_target_sizes"].tolist(), [[640, 384]])
        np.testing.assert_array_equal(
            prepare_rgb(rgb, 640)["images"], original_prepare(rgb, "rtdetr")["images"]
        )
        for size in (True, 641, 1024):
            with self.assertRaises(ValueError):
                prepare_rgb(rgb, size)

    def test_holdout_is_rejected_before_gt_or_rgb_read(self):
        with self.assertRaisesRegex(ValueError, "holdout"):
            safe_input(ROOT / "build/example/holdout-data/rgb.json")
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("resolution_v1_common.safe_input"),
        ):
            data = Path(directory)
            write_new(data / "benchmark.json", dict(partition="holdout"))
            with self.assertRaisesRegex(ValueError, "holdout"):
                development(data)

    def test_full_primary_and_rider_coverage_is_not_ignored(self):
        scenes, truths, _ = fixture()
        rows = [
            (
                s,
                g,
                [
                    dict(class_id=o["class_id"], score=0.9, box=o["box"])
                    for o in g["objects"]
                ],
                True,
                True,
                None,
            )
            for s, g in zip(scenes, truths)
        ]
        result = quality(rows)
        self.assertEqual(result["absolute_quality"], "PASS")
        self.assertEqual(result["micro"]["tp"], 129)
        self.assertEqual(result["riders"], dict(visible=27, detected=27))
        bad = deepcopy(rows)
        bad[0][2].clear()
        self.assertEqual(quality(bad)["micro"]["fn"], 1)

    def test_gate_failure_cannot_win_with_better_f1_and_ties_use_smaller_input(self):
        scenes, truths, _ = fixture()
        result = quality(
            [
                (
                    s,
                    g,
                    [
                        dict(class_id=o["class_id"], score=0.9, box=o["box"])
                        for o in g["objects"]
                    ],
                    True,
                    True,
                    None,
                )
                for s, g in zip(scenes, truths)
            ]
        )
        a = dict(size=960, eligible=True, score=deepcopy(result))
        b = dict(size=1280, eligible=True, score=deepcopy(result))
        self.assertGreater(rank(a), rank(b))
        b["eligible"] = False
        a["score"]["macro_f1"] = 0.9
        self.assertGreater(rank(a), rank(b))
        altered = deepcopy(result)
        altered["per_class"]["5"]["recall"] = 0.9
        self.assertEqual(nonregression(result, altered)["status"], "FAIL")

    def test_valid_looking_json_prediction_must_equal_native_raw(self):
        scenes, truths, frames = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_path = root / "runs/640/selection/run.json"
            (run_path.parent / "raw").mkdir(parents=True)
            for name in ("freeze.json", "models.json", "numeric.json"):
                write_new(root / name, {})
            report = dict(
                size=640,
                group="selection",
                freeze_sha256=sha256_file(root / "freeze.json"),
                models_sha256=sha256_file(root / "models.json"),
                numeric_sha256=sha256_file(root / "numeric.json"),
                providers=["CUDAExecutionProvider"],
                cpu_node_fallback_disabled=True,
                cold_calls_excluded=0,
                expected=81,
                attempted=81,
                model_valid=81,
                admitted=81,
                errors=0,
                status="PASS",
                rows=[],
            )
            for n, (source, gt) in enumerate(zip(frames, truths)):
                raw = dict(
                    labels=np.full((1, 300), 79, np.int64),
                    scores=np.zeros((1, 300), np.float32),
                    boxes=np.tile(
                        np.array([[[10, 10, 30, 30]]], np.float32), (1, 300, 1)
                    ),
                )
                for index, obj in enumerate(gt["objects"]):
                    raw["labels"][0, index] = obj["class_id"]
                    raw["scores"][0, index] = 0.9
                    raw["boxes"][0, index] = obj["box"]
                path = run_path.parent / "raw" / f"{n}.npz"
                np.savez_compressed(path, **raw)
                report["rows"].append(
                    dict(
                        dataset="fixture",
                        **source,
                        valid=True,
                        admitted=True,
                        elapsed_wall_ns=10_000_000,
                        raw=str(path.relative_to(run_path.parent)),
                        raw_sha256=sha256_file(path),
                        detections=json_detections(decode(raw)),
                    )
                )
            write_new(run_path, report)
            with (
                patch("run_resolution_v1.check_freeze"),
                patch(
                    "run_resolution_v1.GROUPS",
                    dict(selection=dict(fixture="development-data")),
                ),
                patch(
                    "run_resolution_v1.development",
                    return_value=(
                        SimpleNamespace(manifest=dict(frames=frames)),
                        dict(scenes=scenes),
                        dict(frames=truths),
                    ),
                ),
            ):
                self.assertEqual(
                    score(root, 640, "selection")["absolute_quality"], "PASS"
                )
                report["rows"][0]["detections"][0]["score"] = 0.8
                import json

                run_path.write_text(json.dumps(report))
                with self.assertRaisesRegex(ValueError, "raw decode"):
                    score(root, 640, "selection")
