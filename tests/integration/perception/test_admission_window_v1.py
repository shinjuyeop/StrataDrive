import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from audit_admission_window_v1 import audit, validate_profile, validate_receipt


class AdmissionWindowTests(unittest.TestCase):
    def fixture(self):
        return dict(model_step_ns='5000000', admission_profile='whole-interval-v1',
                    original_actual=dict(admitted_actual=dict(empty_init=False, normal=True,
                        command_checked_through_ns='100000000', exclusive_expiry_ns='102000001',
                        oldest_actuator_ns='72000000')))

    def test_original_limits_and_exclusive_boundary(self):
        validate_receipt(self.fixture())

    def test_explicit_one_ms_reserve_keeps_same_age_and_exclusive_expiry(self):
        profile=self.profile();profile['wall_preview_reserve_ns']='1000000'
        validate_profile(profile,1_000_000)
        with self.assertRaises(ValueError):validate_profile(profile)
        receipt=self.fixture();out=receipt['original_actual']['admitted_actual']
        out.update(exclusive_expiry_ns='101000001',oldest_actuator_ns='71000000')
        validate_receipt(receipt,1_000_000)
        for key,value in [('exclusive_expiry_ns','101000000'),('oldest_actuator_ns','70999999')]:
            bad=copy.deepcopy(receipt);bad['original_actual']['admitted_actual'][key]=value
            with self.assertRaises(ValueError):validate_receipt(bad,1_000_000)

    def test_changed_profile_or_short_authority_is_rejected(self):
        for key, value in (('model_step_ns', '10000000'), ('admission_profile', 'sampled-actual-v1'),
                           ('exclusive_expiry_ns', '102000000'), ('oldest_actuator_ns', '71999999')):
            with self.subTest(key=key):
                r = copy.deepcopy(self.fixture())
                target = r if key in r else r['original_actual']['admitted_actual']
                target[key] = value
                with self.assertRaises(ValueError): validate_receipt(r)

    def profile(self):
        return dict(structured_state=True, wall_preview_reserve_ns='2000000',
                    model_step_ns='5000000', admission_profile='whole-interval-v1')

    def test_configuration_is_required_on_server_responses(self):
        validate_profile(self.profile())
        for key in self.profile():
            with self.subTest(key=key):
                bad=self.profile();del bad[key]
                with self.assertRaises(ValueError): validate_profile(bad)
        for value in ('0', '4000000'):
            bad=self.profile();bad['wall_preview_reserve_ns']=value
            with self.assertRaises(ValueError): validate_profile(bad)

    def test_real_record_shape_has_separate_configuration_and_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);capture=run/'capture';capture.mkdir()
            result=dict(binding=self.profile(),final_server=self.profile(),requested_intervals=1)
            with gzip.open(capture/'trace.jsonl.gz','wt') as stream:
                stream.write(json.dumps(dict(receipt=self.fixture()))+'\n')
            path=capture/'result.json';path.write_text(json.dumps(result))
            self.assertEqual(audit(run)['status'],'PASS_ADMISSION_WINDOW_INTEGRITY')
            for side in ('binding','final_server'):
                bad=copy.deepcopy(result);bad[side]['wall_preview_reserve_ns']='4000000'
                path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError): audit(run)
            bad=copy.deepcopy(result);bad['requested_intervals']=2
            path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'complete original'):audit(run)
