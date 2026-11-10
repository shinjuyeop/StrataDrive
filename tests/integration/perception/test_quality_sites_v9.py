"""Fresh map-route exclusion without any image/model input."""

from copy import deepcopy
from pathlib import Path
import json
import unittest

from quality_sites_v9 import select_fresh

ROOT = Path(__file__).resolve().parents[3]


class FreshRoadV9Tests(unittest.TestCase):
    def fixture(self):
        survey = json.loads(
            (
                ROOT / "docs/test-plan/evidence/m10_quality_v8/survey-selected.json"
            ).read_text()
        )
        used = json.loads(
            (ROOT / "profiles/perception-quality-v9-used-roads.json").read_text()
        )
        return survey["sites"], used

    def test_first_complete_unused_routes_are_selected(self):
        sites, used = self.fixture()
        chosen = select_fresh(sites, used)
        self.assertEqual([s["spawn_point_index"] for s in chosen], [38, 85])
        self.assertFalse(
            set(used["route_road_ids"])
            & {n["road_id"] for s in chosen for n in s["nodes"].values()}
        )

    def test_used_road_at_route_tail_cannot_hide_behind_fresh_origin(self):
        sites, used = self.fixture()
        modified = deepcopy(sites)
        selected = next(s for s in modified if s["spawn_point_index"] == 38)
        selected["nodes"]["42"]["road_id"] = used["route_road_ids"][0]
        self.assertNotIn(
            38, [s["spawn_point_index"] for s in select_fresh(modified, used)]
        )

    def test_previous_origin_and_map_namespace_are_enforced(self):
        sites, used = self.fixture()
        first = select_fresh(sites, used)[0]
        modified = deepcopy(used)
        modified["route_origins"].append(first["nodes"]["0"]["pose"]["location"])
        self.assertNotEqual(select_fresh(sites, modified)[0]["spawn_point_index"], 38)
        modified["map"] = "Town03_Opt"
        with self.assertRaisesRegex(ValueError, "map-specific"):
            select_fresh(sites, modified)


if __name__ == "__main__":
    unittest.main()
