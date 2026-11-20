import unittest
from unittest.mock import patch

from quality_cached_views import CachedFrameViews, ScheduledViews


class FrameCacheTest(unittest.TestCase):
    def test_key_includes_flip_and_bounds_and_resets_on_each_prepare(self):
        views = CachedFrameViews.__new__(CachedFrameViews)
        with (
            patch.object(ScheduledViews, "prepare"),
            patch.object(ScheduledViews, "forward", side_effect=range(4)) as infer,
        ):
            views.prepare("first")
            rect = (0, 0, 12, 24)
            self.assertEqual(views.forward(rect), 0)
            self.assertEqual(views.forward(list(rect)), 0)
            self.assertEqual(views.forward(rect, True), 1)
            self.assertEqual(views.forward((1, 0, 12, 24)), 2)
            views.prepare("next")
            self.assertEqual(views.forward(rect), 3)
            self.assertEqual(infer.call_count, 4)
