import unittest

from bus_recall_fit import recover

POLICY = dict(score=0.6, support=0.35, ratio=0.6, truck_max=0.3)


def observation(**changes):
    return dict(
        dict(
            score=0.8,
            box=[10, 10, 40, 44],
            old5=0.8,
            adapted5=0.55,
            adapted7=0.24,
            old7=0.45,
        ),
        **changes,
    )


class BusRecallTest(unittest.TestCase):
    def test_agreement_recovers_once(self):
        p = observation()
        self.assertEqual(
            recover([], [p, dict(p, score=0.7)], POLICY),
            [dict(class_id=5, box=p["box"], score=0.8)],
        )

    def test_truck_cutoff_and_insufficient_agreement(self):
        for change in (dict(adapted7=0.3), dict(adapted5=0.34), dict(score=0.59)):
            with self.subTest(change=change):
                self.assertEqual(recover([], [observation(**change)], POLICY), [])

    def test_existing_bus_is_preserved(self):
        p = observation()
        existing = dict(class_id=5, score=0.52, box=p["box"])
        self.assertEqual(recover([existing], [p], POLICY), [existing])
