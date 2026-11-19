import unittest

from person_support_replay import choose


class PersonSupportTest(unittest.TestCase):
    def test_one_unconfirmed_small_person_restores_whole_view(self):
        full = [{"box": [10, 10, 20, 25]}]
        zoom = [{"box": [20, 20, 30, 35]}, {"box": [0, 0, 3, 20]}]
        selected, use_zoom, flags = choose(full, zoom, 4)
        self.assertIs(selected, full)
        self.assertFalse(use_zoom)
        self.assertEqual([v["small"] for v in flags], [False, True])
        self.assertEqual(len(zoom), 2)

    def test_small_person_confirmed_by_both_views_is_retained(self):
        full = [{"box": [1, 1, 4, 16]}]
        zoom = [{"box": [1, 1, 4, 16]}, {"box": [10, 10, 15, 15]}]
        selected, use_zoom, flags = choose(full, zoom, 4)
        self.assertIs(selected, zoom)
        self.assertTrue(use_zoom)
        self.assertEqual([v["confirmed"] for v in flags], [True, False])

    def test_both_size_conditions_are_required(self):
        for box, accepted in (
            ([0, 0, 4, 6], False),
            ([0, 0, 4, 6.25], True),
            ([0, 0, 3.75, 10], False),
        ):
            with self.subTest(box=box):
                selected, use_zoom, flags = choose([], [{"box": box}], 4)
                self.assertEqual(use_zoom, accepted)
                self.assertEqual(len(selected), int(accepted))
                self.assertEqual(flags[0]["small"], not accepted)
