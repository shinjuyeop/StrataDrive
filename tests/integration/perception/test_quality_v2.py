from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import unittest

from physical_ai.perception.contract import Detection, MODEL_SHA256, sha256_file
from physical_ai.perception.quality_candidates import merge
from physical_ai.perception.quality_candidates_v2 import append_vru, CANDIDATES
from prepare_quality_v2 import check_pose
from quality_annotation import SEMANTICS_BY_CLASS
from quality_benchmark_v2 import measure, score, nominate, validate_truth
from quality_v2_common import PLAN, PROTOCOL, freeze, read_json, validate_descriptors


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


class QualityV2PolicyTests(unittest.TestCase):
    def test_crop_vehicle_conflicts_do_not_suppress_real_vehicle(self):
        car = Detection(2, 0.9, (10.0, 10.0, 40.0, 40.0))
        truck = Detection(7, 0.8, car.box)
        self.assertEqual(merge([car, truck], vehicle_nms=False), (car, truck))

    def test_vru_refinement_preserves_base_and_cannot_add_vehicle_fp(self):
        person = Detection(0, 0.4, (10.0, 10.0, 40.0, 40.0))
        car = Detection(2, 0.8, (50.0, 50.0, 90.0, 90.0))
        bike = Detection(1, 0.7, (100.0, 100.0, 130.0, 130.0))
        self.assertEqual(
            append_vru(
                (person, car),
                (Detection(0, 0.9, person.box), bike, Detection(7, 0.95, car.box)),
            ),
            (person, car, bike),
        )
        with self.assertRaises(ValueError):
            append_vru((person,), (Detection(2, float("nan"), car.box),))

    def test_small_ignore_is_diagnostic_and_one_to_one(self):
        obj = dict(
            class_id=0,
            instance_id=1,
            box=[10, 10, 14, 16],
            visible_pixels=24,
            semantic_tags=[13],
            reason="small_visible_support",
        )
        pred = asdict(Detection(0, 0.8, (10.0, 10.0, 14.0, 16.0)))
        raw, matched, diag, ignored, _ = measure([pred, pred], [], [obj])
        self.assertEqual(raw["0"], dict(tp=0, fp=2, fn=0))
        self.assertEqual(diag["0"], dict(tp=0, fp=1, fn=0))
        self.assertEqual(ignored, {0})
        self.assertFalse(matched)

    def test_amodal_cover_does_not_turn_visible_iou_miss_into_tp(self):
        g = dict(class_id=0, instance_id=1, box=[10, 10, 20, 20])
        p = asdict(Detection(0, 0.8, (0.0, 0.0, 40.0, 40.0)))
        raw, matched, _, _, covered = measure([p], [g], [])
        self.assertEqual(raw["0"], dict(tp=0, fp=1, fn=1))
        self.assertEqual(covered, {0})
        self.assertFalse(matched)

    def test_zero_cached_pose_rejected_and_wraparound_yaw_accepted(self):
        base = dict(location=dict(x=10, y=20, z=1), rotation=dict(yaw=180))
        planned = dict(forward_m=5, right_m=2, z_offset_m=0.5, yaw_offset_degrees=180)
        actual = dict(location=dict(x=5, y=18, z=1.5), rotation=dict(yaw=0))
        check_pose(base, actual, planned)
        with self.assertRaises(ValueError):
            check_pose(base, dict(actual, location=dict(x=0, y=0, z=0)), planned)

    def test_rider_class_and_support_mutations_rejected(self):
        obj = dict(
            class_id=0,
            instance_id=1,
            visible_pixels=25,
            box=[10, 10, 15, 15],
            semantic_tags=[13],
        )
        validate_truth(dict(objects=[obj], excluded=[]))
        for mutated in (
            dict(obj, class_id=1),
            dict(obj, visible_pixels=24),
            dict(obj, semantic_tags=[12, 12]),
        ):
            with self.subTest(mutated=mutated), self.assertRaises(ValueError):
                validate_truth(dict(objects=[mutated], excluded=[]))

    def test_frozen_descriptors_and_fresh_ids(self):
        validate_descriptors()
        plan = read_json(PLAN)
        ids = [c["id"] for p in plan["partitions"].values() for c in p["cases"]]
        self.assertEqual(len(set(ids)), 162)
        self.assertTrue(all(x.startswith("v2-") for x in ids))


def symbolic_v2(root):
    frozen = root / "freeze.json"
    freeze(frozen)
    (root / "source.rgb").write_bytes(bytes([31, 97, 181]) * 640 * 384)
    manifest = dict(
        schema="m10-rgb-dataset-v1",
        split="evaluation",
        capture_sha256="0" * 64,
        camera=dict(
            width=640, height=384, camera_id=1, calibration_revision=1, format="RGB8"
        ),
        epoch=1,
        clock_instance=7,
        frames=[],
    )
    truth = dict(
        schema="m10-rider-visible-gt-v2",
        partition="development",
        capture_sha256="0" * 64,
        frames=[],
    )
    meta = dict(
        schema="m10-quality-dataset-v2",
        partition="development",
        capture_sha256="0" * 64,
        plan_sha256=sha256_file(PLAN),
        protocol_sha256=sha256_file(PROTOCOL),
        selection_sha256=None,
        scenes=[],
    )
    run = dict(
        schema="m10-quality-run-v2",
        status="PASS",
        phase="development",
        candidate="baseline",
        freeze_sha256=sha256_file(frozen),
        protocol_sha256=sha256_file(PROTOCOL),
        model_sha256=MODEL_SHA256,
        providers=["CUDAExecutionProvider"],
        cpu_node_fallback_disabled=True,
        selection_sha256=None,
        expected=81,
        attempted=81,
        model_valid=81,
        admitted=81,
        errors=0,
        rows=[],
    )
    for n, case in enumerate(read_json(PLAN)["partitions"]["development"]["cases"], 1):
        path = f"{n}.rgb"
        os.link(root / "source.rgb", root / path)
        source = dict(
            scene=case["id"],
            frame=n,
            source_ns=n * 50_000_000,
            rgb_path=path,
            rgb_sha256=sha256_file(root / path),
        )
        manifest["frames"].append(source)
        objects = []
        actors = []
        for index, actor in enumerate(case["actors"]):
            ident = n * 4 + index
            cls = actor["class_id"]
            x = 10 + len(objects) * 90
            objects.append(
                dict(
                    class_id=cls,
                    instance_id=ident,
                    visible_pixels=400,
                    box=[x, 10, x + 20, 30],
                    semantic_tags=[SEMANTICS_BY_CLASS[cls][0]],
                )
            )
            actors.append(
                dict(
                    actor_id=ident,
                    blueprint=actor["blueprint"],
                    class_id=cls,
                    role=actor["role"],
                    included=True,
                    excluded_small=False,
                )
            )
            if cls in (1, 3):
                x = 10 + len(objects) * 90
                objects.append(
                    dict(
                        class_id=0,
                        instance_id=ident,
                        visible_pixels=400,
                        box=[x, 10, x + 20, 30],
                        semantic_tags=[13],
                    )
                )
        truth["frames"].append(
            dict(scene=case["id"], frame=n, objects=objects, excluded=[])
        )
        meta["scenes"].append(
            dict(
                scene=case["id"],
                weather=case["weather"],
                stratum=case["stratum"],
                target_class=case["target_class"],
                actors=actors,
            )
        )
        run["rows"].append(
            dict(
                scene=case["id"],
                frame=n,
                source_ns=source["source_ns"],
                rgb_sha256=source["rgb_sha256"],
                model_valid=True,
                admitted=True,
                detections=[
                    asdict(Detection(o["class_id"], 0.9, tuple(o["box"])))
                    for o in objects
                ],
                expires_ns=source["source_ns"] + 100_000_000,
                elapsed_wall_ns=10_000_000,
                preprocess_ns=1_000_000,
                inference_ns=1_000_000,
                postprocess_ns=1_000_000,
            )
        )
    write(root / "rgb.json", manifest)
    truth["rgb_manifest_sha256"] = sha256_file(root / "rgb.json")
    write(root / "evaluation-only-gt.json", truth)
    meta.update(
        rgb_manifest_sha256=sha256_file(root / "rgb.json"),
        truth_sha256=sha256_file(root / "evaluation-only-gt.json"),
    )
    write(root / "benchmark.json", meta)
    seal = {
        k: meta[k]
        for k in (
            "partition",
            "capture_sha256",
            "plan_sha256",
            "protocol_sha256",
            "selection_sha256",
            "rgb_manifest_sha256",
            "truth_sha256",
        )
    }
    seal.update(
        schema="m10-quality-data-seal-v2",
        metadata_sha256=sha256_file(root / "benchmark.json"),
    )
    write(root / "benchmark-seal.json", seal)
    run.update(
        dataset_sha256=sha256_file(root / "rgb.json"),
        dataset_seal_sha256=sha256_file(root / "benchmark-seal.json"),
    )
    write(root / "result.json", run)
    return run, frozen


class QualityV2AuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.run, self.frozen = symbolic_v2(self.root)

    def audit(self):
        return score(self.root, self.root / "result.json", self.frozen)

    def test_perfect_independent_fixture_covers_riders_and_every_stratum(self):
        result = self.audit()
        self.assertEqual(result["absolute_quality"], "PASS")
        self.assertEqual(result["riders"]["visible"], 27)
        self.assertEqual(result["primary_coverage"]["1"]["far"], 3)

    def test_deadline_and_semantic_misses_keep_separate_denominators(self):
        self.run["rows"][0].update(elapsed_wall_ns=100_000_000, admitted=False)
        self.run["admitted"] -= 1
        write(self.root / "result.json", self.run)
        result = self.audit()
        self.assertEqual(result["micro"]["fn"], 0)
        self.assertEqual(result["admitted_micro"]["fn"], 1)

    def test_trace_and_seal_mutations_rejected(self):
        changes = [
            lambda r: r.update(attempted=80),
            lambda r: r.update(model_sha256="0" * 64),
            lambda r: r.update(phase="holdout"),
            lambda r: r.update(selection_sha256="f" * 64),
            lambda r: r.update(dataset_seal_sha256="0" * 64),
            lambda r: r.update(cpu_node_fallback_disabled=False),
            lambda r: r["rows"][0].update(frame=3),
            lambda r: r["rows"][0].update(expires_ns=1),
            lambda r: r["rows"][0].update(elapsed_wall_ns=100_000_000),
            lambda r: r["rows"][0].update(model_valid=False),
            lambda r: r["rows"][0]["detections"][0].update(score=True),
            lambda r: r["rows"][0].update(preprocess_ns=-1),
        ]
        for n, change in enumerate(changes):
            run = deepcopy(self.run)
            change(run)
            write(self.root / "result.json", run)
            with self.subTest(mutation=n), self.assertRaises((ValueError, KeyError)):
                self.audit()

    def test_nomination_rejects_mixed_dataset_before_using_scores(self):
        result = self.audit()
        paths = []
        for c in CANDIDATES:
            path = self.root / f"{c}.json"
            write(path, dict(result, candidate=c))
            paths.append(path)
        selected = nominate(paths, self.frozen, self.root / "selection.json")
        self.assertFalse(selected["runtime_promotion"])
        altered = read_json(paths[-1])
        altered["metadata_sha256"] = "0" * 64
        write(paths[-1], altered)
        with self.assertRaisesRegex(ValueError, "dataset"):
            nominate(paths, self.frozen, self.root / "bad-selection.json")


if __name__ == "__main__":
    unittest.main()
