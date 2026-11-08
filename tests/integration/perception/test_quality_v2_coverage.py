"""Regression: aggregate support must not hide a completely empty far stratum."""

from pathlib import Path
import tempfile
import unittest

from physical_ai.perception.contract import sha256_file
from quality_v2_common import read_json
from quality_benchmark_v2 import score
from test_quality_v2 import symbolic_v2, write


class QualityV2CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.run, self.frozen = symbolic_v2(self.root)

    def exclude_far_people(self, retain_predictions):
        truth = read_json(self.root / "evaluation-only-gt.json")
        meta = read_json(self.root / "benchmark.json")
        for i, scene in enumerate(meta["scenes"]):
            if scene["target_class"] == 0 and scene["stratum"] == "far":
                obj = truth["frames"][i]["objects"].pop()
                obj.update(visible_pixels=18, reason="small_visible_support")
                truth["frames"][i]["excluded"].append(obj)
                scene["actors"][0].update(included=False, excluded_small=True)
                if not retain_predictions:
                    self.run["rows"][i]["detections"] = []
        write(self.root / "evaluation-only-gt.json", truth)
        meta["truth_sha256"] = sha256_file(self.root / "evaluation-only-gt.json")
        write(self.root / "benchmark.json", meta)
        seal = read_json(self.root / "benchmark-seal.json")
        seal.update(
            truth_sha256=meta["truth_sha256"],
            metadata_sha256=sha256_file(self.root / "benchmark.json"),
        )
        write(self.root / "benchmark-seal.json", seal)
        self.run["dataset_seal_sha256"] = sha256_file(self.root / "benchmark-seal.json")
        write(self.root / "result.json", self.run)
        return score(self.root, self.root / "result.json", self.frozen)

    def test_perfect_precision_recall_and_total_nine_do_not_hide_empty_far_cell(self):
        result = self.exclude_far_people(False)
        self.assertEqual(sum(result["primary_coverage"]["0"].values()), 9)
        self.assertEqual(result["micro"]["precision"], 1)
        self.assertEqual(result["micro"]["recall"], 1)
        self.assertFalse(result["gates"]["coverage"])
        self.assertEqual(result["absolute_quality"], "FAIL")

    def test_small_ignore_diagnostic_never_changes_primary_gate_or_counts(self):
        result = self.exclude_far_people(True)
        self.assertEqual(result["micro"]["fp"], 3)
        self.assertEqual(result["small_ignore_diagnostic_micro"]["fp"], 0)
        self.assertEqual(result["small_predictions_ignored_diagnostic"], 3)
        self.assertFalse(result["gates"]["coverage"])


if __name__ == "__main__":
    unittest.main()
