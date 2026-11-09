from pathlib import Path
import hashlib
import json
import tempfile
import unittest
import numpy as np
from physical_ai.perception.domain_data_v1 import (
    visible_objects,
    encode_rle,
    decode_rle,
    export,
    DomainDataset,
    write_json_new,
)
from physical_ai.perception.contract import sha256_file
from domain_plan_v1 import build, ASSETS


class DomainDataTests(unittest.TestCase):
    def test_plan_split_views_and_reserved_holdout(self):
        p = build()
        self.assertEqual(sum(len(r["cases"]) for r in p["partitions"].values()), 1020)
        self.assertEqual(p["partitions"]["validation-104"]["spawn_point_index"], 104)
        self.assertNotIn(
            127, {r["spawn_point_index"] for r in p["partitions"].values()}
        )
        for cls in (0, 1, 2, 3):
            self.assertTrue(
                set(ASSETS["train"][cls]).isdisjoint(ASSETS["validation"][cls])
            )
        for run in p["partitions"].values():
            regular = [
                r for r in run["cases"] if r["stratum"] in ("near", "medium", "far")
            ]
            self.assertEqual(
                len(
                    {
                        (
                            r["target_class"],
                            r["weather"],
                            r["orientation_degrees"],
                            r["stratum"],
                        )
                        for r in regular
                    }
                ),
                216,
            )
            pairs = {r["id"]: r for r in run["cases"]}
            for row in run["cases"]:
                if "reference_for" in row:
                    target = pairs[row["reference_for"]]
                    self.assertEqual(row["camera_pose"], target["camera_pose"])
                    self.assertEqual(row["actors"][0], target["actors"][0])

    def test_rle_known_column_major_and_edge_masks(self):
        mask = np.zeros((384, 640), bool)
        mask[0, 0] = True
        mask[2:5, 3] = True
        r = encode_rle(mask)
        self.assertEqual(r["counts"][:5], [0, 1, 1153, 3, 244603])
        self.assertTrue(np.array_equal(decode_rle(r), mask))
        for m in (np.zeros_like(mask), np.ones_like(mask)):
            self.assertTrue(np.array_equal(decode_rle(encode_rle(m)), m))
        with self.assertRaises(ValueError):
            decode_rle(dict(size=[384, 640], counts=[1]))
        with self.assertRaises(ValueError):
            decode_rle(dict(size=[384, 640], counts=[True, 245759]))

    def test_small_fragments_stay_positive_and_rider_is_distinct_class(self):
        p = np.zeros((384, 640, 4), np.uint8)
        p[10:15, 10:15] = [0, 17, 19, 255]
        p[8:13, 11:16] = [0, 17, 13, 255]
        p[30:32, 30:32] = [0, 18, 14, 255]
        objects = visible_objects(p.tobytes())
        self.assertEqual({o["class_id"] for o in objects}, {0, 1, 2})
        small = next(o for o in objects if o["class_id"] == 2)
        self.assertFalse(small["quality_eligible"])
        self.assertEqual(small["visible_pixels"], 4)
        self.assertEqual(
            next(o for o in objects if o["class_id"] == 0)["semantic_tags"], [13]
        )

    def fixture(self, root):
        result = {}
        for n, split in enumerate(("train", "validation"), 1):
            p = root / split
            p.mkdir()
            rgb = bytes([20 * n, 40, 80]) * 640 * 384
            (p / "frame.rgb").write_bytes(rgb)
            raw = np.zeros((384, 640, 4), np.uint8)
            raw[10:15, 10:15] = [0, 1, 12, 255]
            raw[20:22, 20:22] = [0, 2, 14, 255]
            write_json_new(
                p / "data.json",
                dict(
                    split=split,
                    site=n,
                    road_id=n,
                    capture_sha256=str(n) * 64,
                    frames=[
                        dict(
                            scene=split,
                            rgb_path="frame.rgb",
                            rgb_sha256=hashlib.sha256(rgb).hexdigest(),
                            variant_group=split,
                            objects=visible_objects(raw.tobytes()),
                        )
                    ],
                ),
            )
            result[split] = [p]
        return result

    def test_lossless_export_category_mapping_and_small_positive(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            report = export(self.fixture(root), root / "dataset", "a" * 64, "b" * 64)
            self.assertEqual(report["splits"]["train"]["small_fragments"], 1)
            train = DomainDataset(root / "dataset", "train")
            valid = DomainDataset(root / "dataset", "validation")
            self.assertTrue(train.validate_split(valid))
            im, rgb, labels = next(train.samples())
            self.assertEqual(rgb[0, 0].tolist(), [20, 40, 80])
            self.assertEqual({a["native_class"] for a in labels}, {0, 2})
            self.assertTrue(all(a["iscrowd"] == 0 for a in train.coco["annotations"]))
            self.assertEqual(
                {c["id"] for c in train.coco["categories"]}, {1, 2, 3, 4, 6, 8}
            )

    def test_split_checks_geometric_family_and_consumed_content(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            export(self.fixture(root), root / "dataset", "a" * 64, "b" * 64)
            a, b = (
                DomainDataset(root / "dataset", "train"),
                DomainDataset(root / "dataset", "validation"),
            )
            for field in (
                "rgb_sha256",
                "site",
                "road_id",
                "variant_group",
                "capture_sha256",
            ):
                im = next(iter(b.images.values()))
                old = im[field]
                im[field] = next(iter(a.images.values()))[field]
                with self.assertRaisesRegex(ValueError, "split overlap"):
                    a.validate_split(b)
                im[field] = old

    def test_hash_and_semantic_tampering_are_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            export(self.fixture(root), root / "dataset", "a" * 64, "b" * 64)
            manifest = root / "dataset/dataset.json"
            path = root / "dataset/annotations/instances_train.json"
            original = path.read_text()
            value = json.loads(original)
            value["annotations"][0]["area"] += 1
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "annotation hash"):
                DomainDataset(root / "dataset", "train")
            m = json.loads(manifest.read_text())
            m["splits"]["train"]["annotation_sha256"] = sha256_file(path)
            manifest.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError, "visible mask"):
                DomainDataset(root / "dataset", "train")
