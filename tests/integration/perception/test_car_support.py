import unittest
from car_support import add, controls


class CarSupportTest(unittest.TestCase):
    def test_nested_subbox_cannot_generate_second_car(self):
        car = dict(class_id=2, box=[0, 0, 50, 40], score=0.95)
        d = dict(car, box=[3, 3, 13, 12], crop_car=0.95)
        self.assertEqual(add([car], [d], dict(full=0.35, crop=0.2)), [car])

    def test_omission_uses_alternate_prediction(self):
        car = dict(class_id=2, box=[5, 8, 25, 30], score=0.95)
        extra = dict(car, score=0.61, crop_car=0.83)
        r = dict(gt=[car], parent=[car], candidates=[extra])
        self.assertEqual(controls([r]), [[extra]])
        self.assertEqual(
            add([], [extra], dict(full=0.35, crop=0.2)), [dict(car, score=0.61)]
        )
