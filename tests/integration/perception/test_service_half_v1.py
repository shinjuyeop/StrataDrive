import copy
import unittest
from audit_service_half_v1 import validate


class ServiceCadenceTests(unittest.TestCase):
    def fixture(self):
        initial=1_000_000_000
        server=dict(native_service_us=500,profile_state_path=True)
        capture=dict(native_service_us=500,profile_state_path=True,native_initial=dict(service_period_ns=500_000))
        meta=dict(initial=initial,service_period_ns=500_000)
        paths=[dict(wake_ns=initial+slot*500_000,read_begin_ns=initial+slot*500_000+10_000,
                    proof_publish_ns=initial+slot*500_000+60_000) for slot in (1,2,5)]
        return server,capture,meta,paths

    def test_observed_absolute_slots_allow_skips_without_catchup(self):
        result=validate(*self.fixture())
        self.assertEqual((result['observed_calls'],result['skipped_slots']),(3,2))

    def test_mismatch_historical_service_missing_and_off_grid_rejected(self):
        for change in ('server','capture','initial','meta','profile','grid','early','catchup','first','missing'):
            s,c,m,p=copy.deepcopy(self.fixture())
            if change=='server':s['native_service_us']=1000
            if change=='capture':c['native_service_us']=1000
            if change=='initial':c['native_initial']['service_period_ns']=1_000_000
            if change=='meta':m['service_period_ns']=1_000_000
            if change=='profile':s['profile_state_path']=False
            if change=='grid':p[1]['wake_ns']+=1
            if change=='early':p[1]['read_begin_ns']=p[1]['wake_ns']-1
            if change=='catchup':p[0]['proof_publish_ns']=p[1]['wake_ns']+1
            if change=='first':p=p[1:]
            if change=='missing':p=[]
            with self.subTest(change=change),self.assertRaises(ValueError):validate(s,c,m,p)


if __name__=='__main__':unittest.main()
