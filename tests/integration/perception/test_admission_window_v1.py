import copy
import unittest
from audit_admission_window_v1 import validate_receipt


class AdmissionWindowTests(unittest.TestCase):
    def fixture(self):
        return dict(structured_state=True, wall_preview_reserve_ns='2000000',
                    model_step_ns='5000000', admission_profile='whole-interval-v1',
                    original_actual=dict(admitted_actual=dict(empty_init=False, normal=True,
                        command_checked_through_ns='100000000', exclusive_expiry_ns='102000001',
                        oldest_actuator_ns='72000000')))

    def test_original_limits_and_exclusive_boundary(self):
        validate_receipt(self.fixture())

    def test_changed_profile_or_short_authority_is_rejected(self):
        for key, value in (('structured_state', False), ('wall_preview_reserve_ns', '0'),
                           ('model_step_ns', '10000000'), ('admission_profile', 'sampled-actual-v1'),
                           ('exclusive_expiry_ns', '102000000'), ('oldest_actuator_ns', '71999999')):
            with self.subTest(key=key):
                r = copy.deepcopy(self.fixture())
                target = r if key in r else r['original_actual']['admitted_actual']
                target[key] = value
                with self.assertRaises(ValueError): validate_receipt(r)
