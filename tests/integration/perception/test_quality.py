from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from physical_ai.perception.contract import Detection, MODEL_SHA256, sha256_file
from physical_ai.perception.quality_candidates import merge, restore_crop
from quality_benchmark import (
    PLAN,
    freeze,
    score,
    relative,
    read_json,
    PROTOCOL,
    validate_protocol,
)


class QualityCandidateTests(unittest.TestCase):
    def test_vehicle_duplicates_removed_without_suppressing_person_or_two_wheelers(
        self,
    ):
        box = (10.0, 20.0, 60.0, 80.0)
        rows = [
            Detection(c, 0.9 - i * 0.01, box) for i, c in enumerate((2, 7, 5, 0, 1, 3))
        ]
        self.assertEqual([d.class_id for d in merge(rows)], [2, 0, 1, 3])

    def test_partial_overlap_of_different_vehicles_is_preserved(self):
        a = Detection(2, 0.9, (0.0, 0.0, 100.0, 100.0))
        b = Detection(7, 0.8, (20.0, 0.0, 120.0, 100.0))
        self.assertEqual(len(merge([a, b])), 2)
        self.assertEqual(merge([a, Detection(2, 0.8, b.box)]), (a,))
        self.assertEqual(
            len(merge([a, Detection(2, 0.8, b.box)], same_class_nms=False)), 2
        )

    def test_crop_is_restored_to_original_pixels_and_clipped_objects_are_not_published(
        self,
    ):
        d = Detection(0, 0.8, (20.0, 40.0, 100.0, 140.0))
        self.assertEqual(restore_crop([d])[0].box, (170.0, 116.0, 210.0, 166.0))
        for box in (
            (2.0, 10.0, 50.0, 80.0),
            (10.0, 2.0, 50.0, 80.0),
            (10.0, 20.0, 638.0, 100.0),
            (10.0, 20.0, 40.0, 382.0),
        ):
            self.assertEqual(restore_crop([Detection(2, 0.9, box)]), ())

    def test_ties_are_deterministic_and_invalid_data_is_not_hidden_by_suppression(self):
        a = Detection(7, 0.9, (0.0, 0.0, 100.0, 100.0))
        b = Detection(2, 0.9, a.box)
        self.assertEqual(merge([a, b]), (a,))
        with self.assertRaises(ValueError):
            merge([a, Detection(2, float("nan"), a.box)])
        with self.assertRaises(ValueError):
            merge([a] * 201)

    def test_predeclared_plan_and_candidate_descriptor(self):
        validate_protocol()
        p = read_json(PLAN)
        d, h = p["partitions"]["development"], p["partitions"]["holdout"]
        self.assertEqual(len(d["cases"]), 81)
        self.assertEqual(len(h["cases"]), 81)
        self.assertFalse({c["id"] for c in d["cases"]} & {c["id"] for c in h["cases"]})
        self.assertNotEqual(d["spawn_point_index"], h["spawn_point_index"])
        for part in (d, h):
            for cls in (0, 1, 2, 3, 5, 7):
                self.assertEqual(
                    sum(c["target_class"] == cls for c in part["cases"]), 12
                )


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def symbolic_fixture(root):
    """Independent perfect symbolic detections for all planned cases; no model inference."""
    frozen = root / "freeze.json"
    freeze(frozen)
    cases = read_json(PLAN)["partitions"]["development"]["cases"]
    image = bytes([30, 90, 180]) * 640 * 384
    (root / "source.rgb").write_bytes(image)
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
        schema="m10-visible-instance-gt-v1", capture_sha256="0" * 64, frames=[]
    )
    meta = dict(
        schema="m10-quality-dataset-v1",
        partition="development",
        plan_sha256=sha256_file(PLAN),
        capture_sha256="0" * 64,
        selection_sha256=None,
        scenes=[],
    )
    run = dict(
        schema="m10-quality-run-v1",
        status="PASS",
        candidate="baseline",
        phase="development",
        freeze_sha256=sha256_file(frozen),
        protocol_sha256=sha256_file(PROTOCOL),
        model_sha256=MODEL_SHA256,
        providers=["CUDAExecutionProvider"],
        cpu_node_fallback_disabled=True,
        expected=81,
        attempted=81,
        model_valid=81,
        admitted=81,
        errors=0,
        rows=[],
    )
    for n, case in enumerate(cases, 1):
        image_path = f"{n}.rgb"
        os.link(root / "source.rgb", root / image_path)
        source = dict(
            scene=case["id"],
            frame=n,
            source_ns=n * 50_000_000,
            rgb_path=image_path,
            rgb_sha256=hashlib.sha256(image).hexdigest(),
        )
        manifest["frames"].append(source)
        objects = []
        actors = []
        detections = []
        for index, actor in enumerate(case["actors"]):
            ident = n * 3 + index
            box = [10.0 + index * 80, 10.0, 40.0 + index * 80, 50.0]
            objects.append(
                dict(
                    class_id=actor["class_id"],
                    instance_id=ident,
                    visible_pixels=1200,
                    box=box,
                )
            )
            actors.append(
                dict(
                    actor_id=ident,
                    blueprint=actor["blueprint"],
                    class_id=actor["class_id"],
                    role=actor["role"],
                    included=True,
                    excluded_small=False,
                )
            )
            detections.append(asdict(Detection(actor["class_id"], 0.9, tuple(box))))
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
                detections=detections,
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
    seal = dict(
        schema="m10-quality-data-seal-v1",
        partition="development",
        plan_sha256=sha256_file(PLAN),
        metadata_sha256=sha256_file(root / "benchmark.json"),
        truth_sha256=sha256_file(root / "evaluation-only-gt.json"),
        rgb_manifest_sha256=sha256_file(root / "rgb.json"),
    )
    write(root / "benchmark-seal.json", seal)
    run.update(
        dataset_sha256=sha256_file(root / "rgb.json"),
        dataset_seal_sha256=sha256_file(root / "benchmark-seal.json"),
    )
    write(root / "result.json", run)
    return run, frozen


class QualityAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run, self.frozen = symbolic_fixture(self.root)

    def audit(self):
        return score(self.root, self.root / "result.json", self.frozen)

    def test_perfect_independent_fixture_passes_absolute_but_not_improvement_gate(self):
        r = self.audit()
        self.assertEqual(r["absolute_quality"], "PASS")
        self.assertEqual(r["micro"]["precision"], 1)
        self.assertEqual(r["visible_primary_cases"]["0"], 12)
        self.assertEqual(relative(r, r, read_json(PROTOCOL))["status"], "FAIL")

    def test_empty_valid_is_a_miss_not_an_error_or_a_dropped_denominator(self):
        row = self.run["rows"][0]
        row["detections"] = []
        write(self.root / "result.json", self.run)
        r = self.audit()
        self.assertEqual(r["micro"]["fn"], 1)
        self.assertEqual(r["near_person"]["recall"], 2 / 3)
        self.assertFalse(r["gates"]["near_person"])

    def test_raw_and_deadline_admitted_quality_are_distinct(self):
        self.run["rows"][0].update(elapsed_wall_ns=100_000_000, admitted=False)
        self.run["admitted"] -= 1
        write(self.root / "result.json", self.run)
        r = self.audit()
        self.assertEqual(r["micro"]["fn"], 0)
        self.assertEqual(r["admitted_micro"]["fn"], 1)

    def test_trace_mutations_rejected(self):
        mutations = [
            lambda r: r.update(attempted=80),
            lambda r: r.update(model_sha256="0" * 64),
            lambda r: r["rows"][0].update(frame=999),
            lambda r: r["rows"][0].update(source_ns=0),
            lambda r: r["rows"][0].update(rgb_sha256="0" * 64),
            lambda r: r["rows"][0].update(expires_ns=200_000_000),
            lambda r: r["rows"][0].update(elapsed_wall_ns=100_000_000),
            lambda r: r["rows"][0].update(model_valid=False),
            lambda r: r["rows"][0]["detections"][0].update(score=True),
            lambda r: r["rows"][0].update(preprocess_ns=-1),
            lambda r: r.update(dataset_seal_sha256="0" * 64),
            lambda r: r.update(phase="holdout"),
            lambda r: r.update(cpu_node_fallback_disabled=False),
            lambda r: r["rows"][0].update(model_valid=True, admitted=1),
        ]
        for n, change in enumerate(mutations):
            copy = deepcopy(self.run)
            change(copy)
            write(self.root / "result.json", copy)
            with self.subTest(mutation=n), self.assertRaises((ValueError, KeyError)):
                self.audit()

    def test_labels_and_strata_cannot_change_after_dataset_seal(self):
        metadata = read_json(self.root / "benchmark.json")
        metadata["scenes"][0]["stratum"] = "far"
        write(self.root / "benchmark.json", metadata)
        with self.assertRaisesRegex(ValueError, "seal"):
            self.audit()


if __name__ == "__main__":
    unittest.main()
