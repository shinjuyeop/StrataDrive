import unittest
from evidence_reproduction_v1 import require_reproduction


class ReproductionTests(unittest.TestCase):
    def failure(self, path):
        return dict(status='FAIL', error="[Errno 2] No such file or directory: '" + path + "'")

    def test_same_missing_member_survives_relocation(self):
        require_reproduction(self.failure('/tmp/run/capture/native.json'),
            self.failure('/d/checked/run/capture/native.json'), '/tmp/run', '/d/checked/run')

    def test_different_member_sibling_and_other_fields_are_rejected(self):
        original = self.failure('/tmp/run/capture/native.json')
        for actual in [self.failure('/d/checked/run/capture/native.csv'),
                       self.failure('/d/checked/run-other/capture/native.json'),
                       dict(self.failure('/d/checked/run/capture/native.json'), extra=True),
                       dict(status='FAIL', error='another error')]:
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                require_reproduction(original, actual, '/tmp/run', '/d/checked/run')

    def test_pass_values_are_exact(self):
        with self.assertRaises(ValueError):
            require_reproduction(dict(status='PASS', count=1), dict(status='PASS', count=2), '/a', '/b')
