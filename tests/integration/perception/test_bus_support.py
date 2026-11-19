import unittest

from bus_support import add


class BusSupportTests(unittest.TestCase):
    def test_recheck_bus_overlapping_truck(self):
        truck = dict(class_id=7, score=0.62, box=[40, 30, 100, 90])
        bus = dict(
            class_id=5, score=0.57, box=[41, 29, 101, 89], appearance=0.91, crop_bus=0.6
        )
        policy = dict(full=0.45, appearance=0.75, crop=0.4)
        self.assertEqual([d["class_id"] for d in add([truck], [bus], policy)], [7, 5])
        self.assertEqual(add([truck], [dict(bus, appearance=0.6)], policy), [truck])

    def test_existing_bus_suppresses_partial_duplicate(self):
        parent = dict(class_id=5, score=0.8, box=[20, 30, 100, 110])
        part = dict(
            class_id=5, score=0.8, box=[40, 50, 70, 70], appearance=0.8, crop_bus=0.8
        )
        self.assertEqual(
            add([parent], [part], dict(full=0.4, appearance=0.4, crop=0.4)), [parent]
        )
