from copy import deepcopy
from pathlib import Path
import unittest
from physical_ai.perception.dataset import read_json
from prepare_quality_road_v4 import assess_frames
from quality_annotation import SEMANTICS_BY_CLASS


def fixture():
    path = (
        Path(__file__).resolve().parents[3]
        / "profiles/perception-road-preparation-v4.json"
    )
    cases = read_json(path)["partitions"]["development"]["cases"]
    scenes = []
    truth = []
    for n, case in enumerate(cases):
        actors = []
        objects = []
        for index, a in enumerate(case["actors"]):
            ident = n * 4 + index + 1
            actors.append(
                dict(
                    class_id=a["class_id"],
                    actor_id=ident,
                    blueprint=a["blueprint"],
                    role=a["role"],
                )
            )
            objects.append(
                dict(
                    class_id=a["class_id"],
                    instance_id=ident,
                    visible_pixels=200
                    if case["stratum"] == "occluded" and a["role"] == "target"
                    else 400,
                    box=[10 + index * 30, 10, 30 + index * 30, 30],
                    semantic_tags=[SEMANTICS_BY_CLASS[a["class_id"]][0]],
                )
            )
            if a["class_id"] in (1, 3):
                objects.append(
                    dict(
                        class_id=0,
                        instance_id=ident,
                        visible_pixels=100,
                        box=[50, 50, 60, 60],
                        semantic_tags=[13],
                    )
                )
        scenes.append(dict(scene=case["id"], actors=actors))
        truth.append(dict(scene=case["id"], objects=objects, excluded=[]))
    return cases, scenes, truth


class RoadPreparationTests(unittest.TestCase):
    def test_complete_site_requires_primary_riders_and_real_occlusion(self):
        result = assess_frames(*fixture())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["occlusion_checks"]), 18)
        self.assertTrue(
            all(v == 3 for c in result["primary_coverage"].values() for v in c.values())
        )

    def test_unrelated_instance_cannot_replace_missing_planned_target(self):
        cases, scenes, truth = fixture()
        missing = deepcopy(truth[2]["objects"][0])
        missing["instance_id"] = 60000
        truth[2]["objects"] = [missing]
        result = assess_frames(cases, scenes, truth)
        self.assertFalse(result["gates"]["all_planned_actors_visible"])
        self.assertFalse(result["gates"]["every_class_stratum"])

    def test_visible_two_wheeler_does_not_hide_missing_rider(self):
        cases, scenes, truth = fixture()
        truth[6]["objects"] = [
            g for g in truth[6]["objects"] if 13 not in g["semantic_tags"]
        ]
        result = assess_frames(cases, scenes, truth)
        self.assertTrue(result["gates"]["all_planned_actors_visible"])
        self.assertFalse(result["gates"]["all_two_wheeler_riders_visible"])
        self.assertEqual(result["status"], "FAIL")

    def test_unoccluded_scene_and_changed_denominator_are_rejected(self):
        cases, scenes, truth = fixture()
        truth[3]["objects"][0]["visible_pixels"] = 400
        self.assertFalse(
            assess_frames(cases, scenes, truth)["gates"]["occlusion_references"]
        )
        with self.assertRaises(ValueError):
            assess_frames(cases[:-1], scenes[:-1], truth[:-1])
        scenes[0]["actors"] = []
        with self.assertRaises(ValueError):
            assess_frames(cases, scenes, truth)
