"""Regression checks for the timing candidate's frame decoder and spatial pruning."""

from itertools import combinations
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from quality_latency import Detector
import quality_vehicle_windows as windows
from quality_views import box_observations


class VehicleWindowTests(unittest.TestCase):
    def test_original_bgra_channel_order_and_buffer_reuse(self):
        rng = np.random.default_rng(3)
        raw = rng.integers(0, 256, (1536, 2560, 4), np.uint8).tobytes()
        reusable = np.empty((1536, 2560, 3), np.uint8)
        detector = SimpleNamespace(
            direct=True, views=SimpleNamespace(rgb_buffer=reusable)
        )
        result = Detector.decode(detector, raw)
        self.assertIs(result, reusable)
        self.assertEqual(
            result.tobytes(),
            Image.frombytes("RGB", (2560, 1536), raw, "raw", "BGRX").tobytes(),
        )

    def test_all_window_subsets_leave_only_disjoint_unseen_windows(self):
        for size in range(11):
            for group in combinations(range(10), size):
                checked, unseen = windows.split_windows(group)
                self.assertEqual(sorted(checked + unseen), list(group))
                for i, j in combinations(unseen, 2):
                    self.assertEqual(
                        windows.intersection_area(
                            windows.WINDOW_BOXES[i], windows.WINDOW_BOXES[j]
                        ),
                        0,
                    )

    def test_duplicate_bound_does_not_prune_displaced_match(self):
        box = [150, 160, 168, 169]
        self.assertFalse(windows.could_supply_box(box, [dict(class_id=2, box=box)]))
        self.assertTrue(
            windows.could_supply_box(box, [dict(class_id=2, box=[161, 160, 179, 169])])
        )
        self.assertTrue(windows.could_supply_box(box, [dict(class_id=0, box=box)]))

    def test_two_views_required_and_alternate_pair_preserved(self):
        box = [310, 170, 328, 179]
        views = SimpleNamespace(cars=[(0, 0.5, box)], forward=lambda rect: rect)
        chosen = tuple(
            i
            for i, (x, y, r, b) in enumerate(windows.WINDOW_BOXES)
            if x <= box[2] and r >= box[0] and y <= box[3] and b >= box[1]
        )
        for i, j in combinations(chosen, 2):

            def observe(raw, rect, flip, view, collect):
                found = [(view, 0.97, box)] if view in (i, j) else []
                return [], found

            with patch.object(windows, "box_observations", side_effect=observe):
                result = windows.confirm_cars(views, [])
            self.assertEqual([d["box"] for d in result], [box, box])
        with patch.object(
            windows, "box_observations", return_value=([], [])
        ) as observe:
            self.assertEqual(windows.confirm_cars(views, []), [])
            self.assertLess(observe.call_count, len(chosen))

    def test_pruning_preserves_fusion_with_partial_occlusion_and_low_score_pairs(self):
        from quality_views import paired_cars
        from quality_vehicle_windows import bus, tiles, visible

        rng = np.random.default_rng(612)
        for _ in range(80):
            # Nearby proposals deliberately straddle the median side cutoff,
            # high score threshold, and boundaries between camera windows.
            cx, cy = rng.uniform([150, 140], [450, 210])
            seed = [cx - 8, cy - 3, cx + 8, cy + 3]
            parent = [
                dict(class_id=2, box=[cx + 12, cy - 7, cx + 24, cy + 4], score=0.8)
            ]
            views = SimpleNamespace(cars=[(0, 0.5, seed)], forward=lambda rect: rect)
            observed = {}
            for i, (x, y, r, b) in enumerate(windows.WINDOW_BOXES):
                if not (
                    x <= seed[2] and r >= seed[0] and y <= seed[3] and b >= seed[1]
                ):
                    continue
                boxes = []
                for _ in range(4):
                    lx, ty = np.array([cx - 8, cy - 3]) + rng.uniform(-2, 2, 2)
                    rx, by = lx + rng.uniform(12, 19), ty + rng.uniform(4, 7)
                    if x < lx < rx < r and y < ty < by < b:
                        boxes.append(
                            (i, float(rng.choice([0.4, 0.95, 0.985])), [lx, ty, rx, by])
                        )
                observed[i] = boxes

            def fused(candidates):
                return visible.select_boxes(
                    parent,
                    tiles.add(parent, candidates, visible.FIX["cutoff"]),
                    bus.MASK,
                )

            expected = fused(
                paired_cars([item for items in observed.values() for item in items])
            )
            with patch.object(
                windows,
                "box_observations",
                side_effect=lambda raw, rect, flip, i, collect: ([], observed[i]),
            ):
                self.assertEqual(fused(windows.confirm_cars(views, parent)), expected)

    def test_rider_fusion_matches_reference_with_ties_and_duplicate_views(self):
        from cycle_transfer import suggestions
        from quality_features import rider_suggestions

        rng = np.random.default_rng(38)
        for _ in range(24):

            def boxes(n, classes):
                out = []
                for _ in range(n):
                    x, y = rng.integers(0, 10, 2)
                    out.append(
                        dict(
                            class_id=int(rng.choice(classes)),
                            score=float(
                                rng.choice([0.05, 0.20, 0.35, 0.45, 0.6, 0.87])
                            ),
                            box=[x, y, x + 10, y + 9],
                        )
                    )
                return out

            verified = boxes(14, [1])
            parent = boxes(5, [0, 1, 3])
            local = boxes(18, [0, 1, 3])
            obs = [
                [i % 4, 0, d["class_id"], d["score"], *d["box"]]
                for i, d in enumerate(boxes(22, [0, 1, 3]))
            ]
            self.assertEqual(
                rider_suggestions(verified, parent, obs, local),
                suggestions(verified, parent, obs, local),
            )

    def test_decode_flip_internal_edge_and_two_heads(self):
        fields = dict(
            labels=np.array([0, 2, 2, 0]),
            scores=np.array([0.5, 0.95, 0.1, 0.8], np.float32),
            boxes=np.array(
                [[2, 10, 34, 90], [60, 60, 88, 80], [55, 60, 70, 73], [0, 10, 20, 90]],
                np.float32,
            ),
        )
        raw = dict(fields, **{"original_" + k: v for k, v in fields.items()})
        rect = (256, 0, 1536, 1536)
        others, cars = box_observations(raw, rect, True, 2)
        self.assertEqual(
            others, [[2, h, 0, 0.5, 367.0, 10.0, 383.0, 90.0] for h in (0, 1)]
        )
        self.assertEqual(
            cars, [(2, float(np.float32(0.95)), [340.0, 60.0, 354.0, 80.0])] * 2
        )
