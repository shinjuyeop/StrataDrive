from types import SimpleNamespace
import unittest
from unittest.mock import patch

from quality_cached_views import CachedFrameViews

try:
    from quality_batch_views import BatchViews
except ModuleNotFoundError as error:
    if error.name not in ("tensorrt", "cuda", "cuda.bindings"):
        raise
    BatchViews = None


@unittest.skipIf(BatchViews is None, "TensorRT Python bindings required")
class BatchScheduleTest(unittest.TestCase):
    def test_fixed_batch_runs_once_per_image_before_dynamic_crops(self):
        views = BatchViews.__new__(BatchViews)
        views.windows = [(i, (i, 0, 100, 80), False) for i in range(6)]
        views.crops = object()
        calls = []

        def infer(crops, windows):
            self.assertIs(crops, views.crops)
            calls.append(tuple(windows))
            return {(rect, flip): (len(calls), i) for i, rect, flip in windows}

        views.batch = SimpleNamespace(infer=infer)

        def prepare(image):
            views.outputs = {}
            views.count = 0
            for i, rect, flip in views.windows:
                self.assertEqual(views.forward(rect, flip), (image, i))
            return image

        def forward(rect, flip=False):
            return views.outputs.get((tuple(rect), flip), "dynamic")

        with (
            patch.object(CachedFrameViews, "prepare", side_effect=prepare),
            patch.object(CachedFrameViews, "forward", side_effect=forward),
        ):
            for image in (1, 2):
                self.assertEqual(views.prepare(image), image)
                self.assertEqual(views.count, 6)
                self.assertEqual(views.forward((8, 0, 100, 80)), "dynamic")
        self.assertEqual(len(calls), 2)
