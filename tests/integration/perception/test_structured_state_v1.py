import unittest
from audit_structured_state_v1 import validate_self_check


class StructuredStateTests(unittest.TestCase):
    def test_only_complete_exact_before_start_check_is_accepted(self):
        check=dict(ok=True,finite_double_patterns=4096,exact_number_bits=True,
            actual_physics_equal=True,mutation_checks=True,
            nonfinite_cases=3,nonfinite_legacy_fallback=True,finite_direct_identity=True,
            internal_envelope_cases=9,internal_envelope_bound=True,internal_envelope_equal=True,
            oversize_noncanonical_fallback=True,
            scope='pre_native_START; no control service; bitwise JSON roundtrip and actual physics snapshot')
        validate_self_check(check)
        for key,value in [('ok',False),('finite_double_patterns',4095),('exact_number_bits',False),
                          ('actual_physics_equal',False),('mutation_checks',False),('scope','during live'),
                          ('nonfinite_cases',2),('nonfinite_legacy_fallback',False),('finite_direct_identity',False),
                          ('internal_envelope_cases',8),('internal_envelope_bound',False),
                          ('internal_envelope_equal',False),('oversize_noncanonical_fallback',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                validate_self_check(dict(check,**{key:value}))
        for key in check:
            partial=dict(check);del partial[key]
            with self.subTest(missing=key),self.assertRaises(ValueError):validate_self_check(partial)


if __name__=='__main__':unittest.main()
