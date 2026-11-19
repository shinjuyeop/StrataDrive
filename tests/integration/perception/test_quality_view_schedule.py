import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import quality_view_schedule as schedule
import quality_shadow_v1 as shadow


class ViewScheduleTest(unittest.TestCase):
    def setUp(self):
        self.model = SimpleNamespace(bundle={})
        self.crops = SimpleNamespace(frame=lambda image: image)
        self.detector = SimpleNamespace(
            model=self.model, views=SimpleNamespace(crops=self.crops)
        )

    def init_views(self, model, crops, mode):
        self.active.model = model
        self.active.crops = crops
        self.active.classifiers = {}
        self.active.config = {}

    def make(self, indices):
        self.active = schedule.ScheduledViews.__new__(schedule.ScheduledViews)
        with patch.object(schedule.Views, "__init__", side_effect=self.init_views):
            self.active.__init__(self.detector, indices)
        return self.active

    def test_original_view_identity_and_flip(self):
        views = self.make([0, 1, 5, 9])
        self.assertEqual(views.windows[0], (0, (0, 0, 2560, 1536), False))
        self.assertEqual(views.windows[1], (1, (0, 0, 2560, 1536), True))
        self.assertEqual([v[0] for v in views.windows], [0, 1, 5, 9])

        def observe(raw, rect, flip, index):
            return [index], [index]

        with (
            patch.object(views, "forward", return_value={}),
            patch.object(schedule, "base_from_raw", return_value=["base"]),
            patch.object(schedule, "box_observations", side_effect=observe),
            patch.object(schedule, "predict_proposals", return_value={}) as propose,
        ):
            for _ in range(2):
                self.assertEqual(views.prepare("pixels"), (["base"], {}, [0, 1, 5, 9]))
                self.assertEqual(views.cars, [0, 1, 5, 9])
                self.assertEqual(
                    propose.call_args.args[2], dict(base=["base"], obs=[0, 1, 5, 9])
                )

    def test_reject_invalid_schedules(self):
        for indices in ([], [1], [0, 1, 1], [0, 2, 1], [0, 10]):
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                self.make(indices)

    def test_fitted_artifact_bound_to_original_views_and_bytes(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = root / "verifier.joblib"
            path.write_bytes(b"registered bytes")
            registration = root / "verifier.json"
            registration.write_text(
                json.dumps(
                    dict(path=path.name, indices=[0, 2], sha256=shadow.digest(path))
                )
            )
            with (
                patch.object(shadow, "ROOT", root),
                patch.object(shadow, "VIEW_REGISTRATION", registration),
            ):
                self.assertEqual(shadow.fitted_verifier([0, 2]), path)
                with self.assertRaisesRegex(ValueError, "schedule"):
                    shadow.fitted_verifier([0, 1])
                path.write_bytes(b"altered")
                with self.assertRaisesRegex(ValueError, "hash"):
                    shadow.fitted_verifier([0, 2])
