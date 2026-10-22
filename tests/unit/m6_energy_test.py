"""Synthetic verdict bookkeeping; actual C++ physics/SDK are separate tests."""
import csv
import math
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/integration/someip'))
from energy_oracle import energy_oracle

class EnergyOracleTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
        self.rows=[]
        for i in range(25):
            n=i+1;t=1_000_000_000+n*10_000_000
            self.rows.append(dict(begin_ns=t-1_000_000,end_ns=t,input_ns=t-1_000_000,epoch=1,model_epoch=7,sequence=n,torque_nm=0,pressure_pa=100000,wheel_speed_rad_s=math.sqrt(2*(100-n)/1000)/.3,kinetic_j=100-n,motor_work_j=100,friction_j=n,road_j=0,electrical_mechanical_j=100,motor_loss_j=n*.2,battery_draw_j=100+n*.3,received_dc_j=0,auxiliary_j=n*.1,ohmic_j=0,capacitor_delta_j=0,circuit_loss_j=0,soc=.96,vehicle_balance_j=0,coupling_balance_j=0,combined_balance_j=0))
        self.feedback=[dict(ns=r['end_ns'],source_ns=r['begin_ns'],epoch=1,torque_nm=0,wheel_speed_rad_s=r['wheel_speed_rad_s'],capability_nm=0,charge_w=0,cap_present=1,charge_present=1) for r in self.rows]
        self.write()
    def write(self):
        for name,rs in [('energy.csv',self.rows),('central-1.energy-feedback.csv',self.feedback)]:
            with (self.p/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
        (self.p/'central-1.events.csv').write_text('ns,event\n1,accelerate\n2,coast\n3,brake\n4,hold\n')
    def verdict(self,case='command-loss',mode='nominal'):return energy_oracle(self.p,case,mode)
    def test_balanced_fault_ledger_passes_without_claiming_a_complete_cycle(self):self.assertTrue(self.verdict()['pass'])
    def test_no_charge_needs_actual_zero_limits_and_friction(self):self.assertTrue(self.verdict('normal','no-charge')['pass'])
    def test_encoded_zero_residual_cannot_hide_energy_corruption(self):
        self.rows[5]['battery_draw_j']+=.01;self.write();self.assertFalse(self.verdict()['pass'])
    def test_motion_and_coupling_are_independently_recomputed(self):
        for key in ('kinetic_j','electrical_mechanical_j'):
            with self.subTest(key=key):
                self.rows[5][key]+=1;self.write();self.assertFalse(self.verdict()['pass']);self.rows[5][key]-=1
    def test_future_dependency_and_nonfinite_are_failures(self):
        for key,value in [('input_ns',2_000_000_000),('soc',math.nan)]:
            with self.subTest(key=key):
                old=self.rows[5][key];self.rows[5][key]=value;self.write();self.assertFalse(self.verdict()['pass']);self.rows[5][key]=old
    def test_counter_reset_and_model_reset_are_failures(self):
        self.rows[5]['auxiliary_j']=0;self.rows[5]['battery_draw_j']=100+self.rows[5]['motor_loss_j'];self.write();self.assertFalse(self.verdict()['pass'])
        self.rows[5]['model_epoch']=8;self.write();self.assertFalse(self.verdict()['pass'])
    def test_missing_phase_is_a_normal_failure(self):
        (self.p/'central-1.events.csv').write_text('ns,event\n1,accelerate\n');self.assertFalse(self.verdict('normal','no-charge')['pass'])
    def test_permission_case_cannot_invent_zero_charge(self):
        self.feedback[3]['charge_w']=1;self.write();self.assertFalse(self.verdict('normal','no-charge')['pass'])
    def test_nominal_requires_both_regeneration_and_dc_receipt(self):self.assertFalse(self.verdict('normal')['pass'])
    def test_rejoin_requires_new_graph_feedback_and_missing_trace_fails(self):
        self.assertFalse(self.verdict('restart-live')['pass']);(self.p/'energy.csv').unlink();self.assertFalse(self.verdict()['pass'])

if __name__=='__main__':unittest.main()
