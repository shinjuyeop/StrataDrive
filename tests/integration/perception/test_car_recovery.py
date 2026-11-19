import unittest
from car_recovery import add


class CarRecoveryTest(unittest.TestCase):
    def test_confirmation_keeps_parent_and_only_adds_one_car(self):
        truck = dict(class_id=7, score=0.8, box=[0, 0, 10, 10])
        car = dict(class_id=2, score=0.7, box=[0, 0, 10, 10], support=0.62)
        extra = dict(car, box=[40, 40, 50, 50], support=0.4)
        result = add([truck], [extra, car, car], 0.6)
        self.assertEqual(
            result, [truck, {k: car[k] for k in ("class_id", "box", "score")}]
        )
