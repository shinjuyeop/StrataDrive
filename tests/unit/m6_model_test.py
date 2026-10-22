#!/usr/bin/env python3
"""Model and verdict contracts; SDK runtime is tested separately."""
import csv
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'models/longitudinal'),str(ROOT/'tests/integration/someip')]
from model import SpeedPI,Sample
from mil import judge
from vehicle_oracle import vehicle_oracle

class ModelTest(unittest.TestCase):
    def new(self):
        c=SpeedPI();self.assertTrue(c.initialize(1));return c
    def test_saturation_slew_and_unwind(self):
        c=self.new();last=0.;maximum=0.
        for tick in range(1000):
            t=tick*c.period_ns
            out=c.step(t,40/3.6 if tick<500 else 0,Sample(1,tick,t,0 if tick<500 else 5),True)
            self.assertTrue(out.valid);self.assertLessEqual(abs(out.acceleration-last),.04000000001)
            self.assertGreaterEqual(out.acceleration,-5);self.assertLessEqual(out.acceleration,2)
            maximum=max(maximum,abs(out.integral));last=out.acceleration
        self.assertLess(maximum,.1);self.assertLess(last,-4.9)
    def test_original_source_age_is_not_refreshed(self):
        c=self.new();s=Sample(1,0,0,1.)
        for t in (0,20_000_000,40_000_000,60_000_000):self.assertTrue(c.step(t,1.,s,True).valid)
        out=c.step(80_000_000,1.,s,True);self.assertFalse(out.valid);self.assertEqual(out.reason,'source-age');self.assertIsNone(out.acceleration)
    def test_permission_loss_latches_until_new_init(self):
        c=self.new();self.assertTrue(c.step(0,1,Sample(1,0,0,0),True).valid)
        self.assertFalse(c.step(20_000_000,1,Sample(1,1,20_000_000,0),False).valid)
        self.assertFalse(c.step(40_000_000,1,Sample(1,2,40_000_000,0),True).valid)
        self.assertFalse(c.initialize(1));self.assertTrue(c.initialize(2));self.assertEqual(c.integral,0)
        self.assertTrue(c.step(60_000_000,1,Sample(2,0,60_000_000,0),True).valid)
    def test_invalid_nan_old_epoch_future_and_identity(self):
        for sample,reason in [(None,'invalid-speed'),(Sample(1,0,0,math.nan),'invalid-speed'),(Sample(0,0,0,0),'epoch'),(Sample(1,0,1,0),'source-age')]:
            with self.subTest(reason=reason):self.assertEqual(self.new().step(0,0,sample,True).reason,reason)
        c=self.new();c.step(0,0,Sample(1,0,0,0),True)
        self.assertEqual(c.step(20_000_000,0,Sample(1,0,0,.1),True).reason,'identity')
    def test_missed_model_job_is_not_normal_completion(self):
        c=self.new();c.step(0,0,Sample(1,0,0,0),True)
        self.assertEqual(c.step(40_000_000,0,Sample(1,1,40_000_000,0),True).reason,'sample-time')
    def test_zero_target_does_not_divide_by_zero(self):
        rows=[dict(time_s=i*.05,reference_mps=0.,speed_mps=0.,acceleration_demand=0.) for i in range(1741)]
        # Include the defined positive plateaus; exact samples, fixed 200 denominators.
        for r in rows:
            if 20<=r['time_s']<35:r['reference_mps']=r['speed_mps']=30/3.6
            if 43<=r['time_s']<58:r['reference_mps']=r['speed_mps']=20/3.6
        self.assertTrue(judge(rows)['pass'])
        rows.pop(600);self.assertFalse(judge(rows)['pass'])
    def test_vehicle_oracle_missing_and_reset_fail(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(vehicle_oracle(d,'command-loss')['pass'])
            rows=[dict(ns=i+1,model_epoch=7,model_sequence=i,speed_mps=.1,distance_m=.01*i,x_m=.01*i,y_m=0,yaw_rad=0,vehicle_balance_j=0) for i in range(12)]
            def write():
                with (Path(d)/'physical.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
            (Path(d)/'central-1.json').write_text(json.dumps({'max_validated_wheel_speed':.3,'wheel_speed_samples':12}))
            write();self.assertTrue(vehicle_oracle(d,'command-loss')['pass'])
            rows[7]['distance_m']=0;write();self.assertFalse(vehicle_oracle(d,'command-loss')['pass'])
    def test_vehicle_oracle_requires_normal_stop_actual(self):
        with tempfile.TemporaryDirectory() as d:
            rows=[dict(ns=i+1,model_epoch=7,model_sequence=i,speed_mps=.2,distance_m=.01*i,x_m=0,y_m=0,yaw_rad=0,vehicle_balance_j=0) for i in range(12)]
            with (Path(d)/'physical.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
            (Path(d)/'central-1.json').write_text(json.dumps({'normal_stop_complete':8}))
            self.assertFalse(vehicle_oracle(d,'normal')['pass'])

if __name__=='__main__':unittest.main()
