from copy import deepcopy
import unittest
from quality_plan_v4 import build, validate_plan, TEMPLATE
from physical_ai.perception.dataset import read_json
from quality_geometry_v4 import road_pose, route_eligible, select_sites


def survey():
    sites = []
    for index in (14, 18):
        nodes = {
            str(i): dict(
                id=index * 100 + i,
                road_id=index,
                section_id=0,
                lane_id=-1,
                s=i,
                lane_width=3.5,
                is_junction=False,
                pose=dict(
                    location=dict(x=float(i), y=float(index * 20), z=0.0),
                    rotation=dict(yaw=0.0, pitch=0.0, roll=0.0),
                ),
            )
            for i in range(43)
        }
        camera = road_pose(nodes["0"], 0, 2.0)
        camera["rotation"]["pitch"] = -6
        sites.append(
            dict(
                spawn_point_index=index,
                nodes=nodes,
                camera_pose=camera,
                base_clearance_m=0.3,
                eligible=True,
            )
        )
    return dict(
        schema="m10-road-survey-v4",
        status="PASS",
        client_version="294096e-dirty",
        server_version="294096e-dirty",
        selected_sites=[14, 18],
        sites=sites,
        xodr_sha256="a" * 64,
    )


class RoadPlanTests(unittest.TestCase):
    def test_middle_junction_is_rejected_even_if_base_is_clear(self):
        s = survey()
        site = s["sites"][1]
        self.assertTrue(route_eligible(site))
        site["nodes"]["20"]["is_junction"] = True
        self.assertFalse(site["nodes"]["0"]["is_junction"])
        self.assertFalse(route_eligible(site))
        with self.assertRaises(ValueError):
            build(s, "b" * 64, read_json(TEMPLATE), "c" * 64)

    def test_sites_are_ordered_and_must_be_spatially_separated(self):
        s = survey()
        self.assertEqual(
            [x["spawn_point_index"] for x in select_sites(s["sites"][::-1])], [14, 18]
        )
        site = s["sites"][1]
        for node in site["nodes"].values():
            node["pose"]["location"]["y"] = 300.0
        site["camera_pose"]["location"]["y"] = 300.0
        with self.assertRaises(ValueError):
            select_sites(s["sites"])

    def plans(self):
        return build(survey(), "b" * 64, read_json(TEMPLATE), "c" * 64)

    def test_every_actual_site_has_complete_preparation_and_references(self):
        evaluation, preparation = self.plans()
        validate_plan(evaluation)
        validate_plan(preparation)
        self.assertEqual(
            evaluation["partitions"]["holdout"]["cases"][2]["actors"][0][
                "route_distance_m"
            ],
            26,
        )
        self.assertEqual(
            preparation["partitions"]["holdout"]["cases"][2]["actors"][0][
                "route_distance_m"
            ],
            27,
        )
        self.assertEqual(
            [len(v["cases"]) for v in preparation["partitions"].values()], [99, 99]
        )
        for part in ("development", "holdout"):
            prep = preparation["partitions"][part]
            ev = evaluation["partitions"][part]
            self.assertEqual(prep["spawn_point_index"], ev["spawn_point_index"])
            self.assertAlmostEqual(
                prep["camera_pose"]["location"]["z"]
                - ev["camera_pose"]["location"]["z"],
                0.05,
            )
            self.assertEqual(sum("reference_for" in c for c in prep["cases"]), 18)
            for a, b in zip(prep["cases"][:81], ev["cases"]):
                for x, y in zip(a["actors"], b["actors"]):
                    self.assertEqual(x["route_distance_m"], y["route_distance_m"] + 1)

    def test_pose_and_camera_drift_cannot_be_hidden_by_valid_metadata(self):
        evaluation, _ = self.plans()
        for kind in ("pose", "projection"):
            changed = deepcopy(evaluation)
            a = changed["partitions"]["holdout"]["cases"][0]["actors"][0]
            if kind == "pose":
                a["pose"]["location"]["z"] += 0.1
            else:
                a["camera_projection"]["u"] += 1
            with self.assertRaises(ValueError):
                validate_plan(changed)

    def test_duplicate_cases_and_rejected_survey_are_not_preparable(self):
        evaluation, _ = self.plans()
        evaluation["partitions"]["holdout"]["cases"][0]["id"] = evaluation[
            "partitions"
        ]["development"]["cases"][0]["id"]
        with self.assertRaises(ValueError):
            validate_plan(evaluation)
        s = survey()
        s["sites"][0]["eligible"] = False
        with self.assertRaises(ValueError):
            build(s, "b" * 64, read_json(TEMPLATE), "c" * 64)
