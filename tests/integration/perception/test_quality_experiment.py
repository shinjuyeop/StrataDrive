from copy import deepcopy
import unittest

from audit_quality_experiment import (
    compare_development,
    compare_selection,
    separate_partitions,
)


class QualityExperimentTests(unittest.TestCase):
    def test_nomination_rejects_other_dataset_with_same_freeze(self):
        score = dict(metadata_sha256="a", freeze_sha256="f", partition="development")
        compare_development([score, score])
        with self.assertRaisesRegex(ValueError, "datasets"):
            compare_development([score, dict(score, metadata_sha256="b")])
        with self.assertRaisesRegex(ValueError, "partition"):
            compare_development([score, dict(score, partition="holdout")])
        with self.assertRaisesRegex(ValueError, "experiment"):
            compare_development([score, dict(score, freeze_sha256="g")])

    def test_nomination_recomputed_including_decision_fields(self):
        original = dict(
            created_utc="old",
            selected="a",
            runtime_promotion=False,
            score_files={"a": "digest"},
            development_relative={"a": "FAIL"},
        )
        recomputed = dict(original, created_utc="new")
        compare_selection(original, recomputed)
        for field, value in (
            ("selected", "b"),
            ("runtime_promotion", True),
            ("score_files", {}),
            ("development_relative", {"a": "PASS"}),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                compare_selection(original, dict(recomputed, **{field: value}))

    def test_renaming_scene_does_not_hide_reused_rgb(self):
        a = dict(frames=[dict(scene="development-0", rgb_sha256="a")])
        b = dict(frames=[dict(scene="holdout-0", rgb_sha256="b")])
        separate_partitions(a, b)
        copied = deepcopy(b)
        copied["frames"][0]["rgb_sha256"] = "a"
        with self.assertRaisesRegex(ValueError, "RGB"):
            separate_partitions(a, copied)
        copied = deepcopy(b)
        copied["frames"][0]["scene"] = "development-0"
        with self.assertRaisesRegex(ValueError, "scene"):
            separate_partitions(a, copied)


if __name__ == "__main__":
    unittest.main()
