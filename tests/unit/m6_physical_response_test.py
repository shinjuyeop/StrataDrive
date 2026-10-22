"""Synthetic evidence/oracle regression. Not an SDK or physical runtime execution."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/integration/someip'))
from physical_response import contract,response_oracle
class PhysicalResponseOracle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
        self.c=contract();self.base=1_000_000_000;self.selection=self.base+20_000_000
        self.result={'case':'command-loss','fault_target':'rear','physical_response':self.c,'processes':[{'role':r,'summary':{'pre_shutdown_protection':self.selection,'selected_ns':self.selection+100}} for r in ('front','rear')]}
        (self.p/'inject').write_text(str(self.base));(self.p/'physical-response-contract.json').write_text(json.dumps(self.c))
        model={k:self.c[k] for k in ('minimum_torque_nm','maximum_torque_nm','zero_rate_nm_s','normal_delay_ns','brake_initial_pa','brake_rise_pa_s')};model['brake_maximum_pa']=1500000
        (self.p/'response-model.json').write_text(json.dumps(model))
        (self.p/'rear-1.leaf-events.csv').write_text(f'ns,event,owner,epoch,source,deadline,value,detail\n{self.base-1000000},valid-input,4,1,{self.base-2000000},{self.selection},0,1\n{self.selection},command-expired,4,1,{self.base-2000000},{self.selection},{self.selection},0\n')
        self.rows=[]
        for i in range(211):
            t=self.selection+i*1_000_000
            self.rows.append(dict(before_ns=t,after_ns=t+1000,model_ns=t+500,torque_nm=max(0,300-i*2),pressure_pa=min(1000000,i*5000),drive_source=self.selection,drive_selected=self.selection,drive_applied=self.selection,drive_zero=1,brake_source=self.selection,brake_selected=self.selection,brake_applied=self.selection,brake_protect=1,epoch=1))
        for role in ('front','rear'):
            (self.p/(role+'-1.events.csv')).write_text(f'ns,event,value,deadline\n{self.selection},local-protection-service,{self.selection-1000},{self.selection}\n')
        self.write()
    def write(self):
        with (self.p/'physical-response.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(self.rows[0]));w.writeheader();w.writerows(self.rows)
        (self.p/'physical.csv').write_text(f'ns,torque,pressure\n{self.selection+210000000},0,1000000\n')
    def verdict(self):return response_oracle(self.p,self.result)
    def test_valid_maximum_model_response(self):self.assertTrue(self.verdict()['pass'],self.verdict())
    def test_budget_comes_from_parallel_worst_case(self):self.assertEqual(self.c['selection_to_observed_complete_ns'],230000000)
    def test_negative_torque_is_not_complete_merely_because_below_positive_one(self):
        for r in self.rows:r['torque_nm']=-200
        self.write();self.assertFalse(self.verdict()['pass'])
    def test_pressure_target_alone_is_not_actual_response(self):
        for r in self.rows:r['pressure_pa']=0
        self.write();self.assertFalse(self.verdict()['pass'])
    def test_late_actual_completion_fails(self):
        for i in range(31):
            r=dict(self.rows[-1]);r.update(before_ns=r['before_ns']+(i+1)*1000000,after_ns=r['after_ns']+(i+1)*1000000,model_ns=r['model_ns']+(i+1)*1000000);self.rows.append(r)
        for r in self.rows[:-1]:r['pressure_pa']=999999
        self.write();self.assertFalse(self.verdict()['pass'])
    def test_selection_may_precede_post_service_observation_but_not_service_entry(self):
        for r in self.rows:r['brake_selected']-=500
        self.write();self.assertTrue(self.verdict()['pass'],self.verdict())
        for r in self.rows:r['brake_selected']-=5000
        self.write();self.assertFalse(self.verdict()['pass'])
    def test_missing_samples_fails(self):
        (self.p/'physical-response.csv').unlink();self.assertFalse(self.verdict()['pass'])
    def test_model_gap_and_nonfinite_fail(self):
        self.rows[5]['model_ns']+=5000000;self.write();self.assertFalse(self.verdict()['pass'])
        self.rows[5]['torque_nm']=float('nan');self.write();self.assertFalse(self.verdict()['pass'])
    def test_unapplied_protection_and_late_local_selection_fail(self):
        for r in self.rows:r['drive_applied']=0
        self.write();self.assertFalse(self.verdict()['pass'])
        for r in self.rows:r['drive_selected']+=5000000
        self.write();self.assertFalse(self.verdict()['pass'])
    def test_missing_valid_rx_or_original_expiry_fails(self):
        (self.p/'rear-1.leaf-events.csv').write_text('ns,event,owner,source,deadline,detail\n');self.assertFalse(self.verdict()['pass'])
    def test_mismatched_config_and_model_fail(self):
        self.result['physical_response']={};self.assertFalse(self.verdict()['pass']);self.result['physical_response']=self.c
        (self.p/'response-model.json').write_text('{}');self.assertFalse(self.verdict()['pass'])
if __name__=='__main__':unittest.main()
