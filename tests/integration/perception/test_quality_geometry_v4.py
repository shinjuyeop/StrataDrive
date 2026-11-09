from copy import deepcopy
import math
import unittest

from quality_geometry_v4 import road_pose, camera_projection, check_pose, route_choice


def node(ident=1, yaw=0, z=0):
    return dict(
        id=ident,
        road_id=1,
        section_id=0,
        lane_id=-1,
        s=ident,
        lane_width=3.5,
        pose=dict(
            location=dict(x=10.0, y=20.0, z=z),
            rotation=dict(pitch=0.0, yaw=yaw, roll=0.0),
        ),
    )


class RoadGeometryTests(unittest.TestCase):
    def test_road_height_heading_and_origin_clearance_replace_flat_camera_ray(self):
        result = road_pose(node(yaw=90, z=2), 1, 0.3, 15)
        self.assertAlmostEqual(result["location"]["x"], 9)
        self.assertAlmostEqual(result["location"]["y"], 20)
        self.assertAlmostEqual(result["location"]["z"], 2.3)
        self.assertAlmostEqual(result["rotation"]["yaw"], 105)

    def test_banked_road_offset_preserves_bank_and_rejects_outside_lane(self):
        n = node()
        n["pose"]["rotation"]["roll"] = 10
        p = road_pose(n, 1, 0.3)
        self.assertAlmostEqual(p["location"]["z"], 0.3 - math.sin(math.radians(10)))
        with self.assertRaises(ValueError):
            road_pose(n, 1.6, 0.3)
        with self.assertRaises(ValueError):
            road_pose(n, float("nan"), 0.3)

    def test_route_branch_is_deterministic_and_heading_continuous(self):
        a, b, c = node(2, 5), node(1, -5), node(3, 90)
        self.assertEqual(route_choice(0, [a, b, c]), b)
        self.assertEqual(route_choice(0, [c, b, a]), b)
        with self.assertRaises(ValueError):
            route_choice(0, [])

    def test_camera_screen_rejects_behind_and_outside_view(self):
        camera = dict(
            location=dict(x=0.0, y=0.0, z=1.7),
            rotation=dict(yaw=0.0, pitch=0.0, roll=0.0),
        )

        def point(x, y):
            return dict(location=dict(x=x, y=y, z=0.5))

        self.assertTrue(camera_projection(camera, point(20, 0))["in_frame"])
        self.assertFalse(camera_projection(camera, point(-20, 0))["in_frame"])
        self.assertFalse(camera_projection(camera, point(20, 30))["in_frame"])

    def test_pose_check_includes_pitch_roll_and_wrapped_yaw(self):
        p = road_pose(node(yaw=179), 0, 0.3)
        q = deepcopy(p)
        q["rotation"]["yaw"] = -181
        check_pose(q, p)
        for group, key, delta in (
            ("location", "z", 0.03),
            ("rotation", "pitch", 0.11),
            ("rotation", "roll", 0.11),
        ):
            q = deepcopy(p)
            q[group][key] += delta
            with self.assertRaises(ValueError):
                check_pose(q, p)
