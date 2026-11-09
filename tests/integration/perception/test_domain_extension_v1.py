import unittest
from domain_plan_v1 import build
from domain_extension_v1 import build_extension, validate_plan


class DomainExtensionTests(unittest.TestCase):
    def test_append_only_plan_keeps_original_and_disjoint_case_ids(self):
        base = build()
        extra = build_extension()
        self.assertEqual(sum(len(p["cases"]) for p in extra["partitions"].values()), 48)
        original = {c["id"] for p in base["partitions"].values() for c in p["cases"]}
        self.assertTrue(
            original.isdisjoint(
                c["id"] for p in extra["partitions"].values() for c in p["cases"]
            )
        )
        self.assertEqual(base, build())

    def test_extension_rejects_changed_reference_and_road_pose(self):
        p = build_extension()
        part = next(iter(p["partitions"].values()))
        part["cases"][1]["camera_pose"]["location"]["x"] += 0.1
        with self.assertRaises(ValueError):
            validate_plan(p)
        p = build_extension()
        next(iter(p["partitions"].values()))["cases"][0]["actors"][0]["pose"][
            "location"
        ]["z"] += 0.1
        with self.assertRaises(ValueError):
            validate_plan(p)
