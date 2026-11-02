"""Necessary ramp bounds and rejection before any runtime/server side effects."""
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
DIRECTORY=Path(__file__).resolve().parents[1]/'integration/carla'
sys.path.insert(0,str(DIRECTORY))
from m8_reference_feasibility import ramp_feasible,require_feasible_route
from m8_route_contract import load_route

class PropulsionFeasibilityTest(unittest.TestCase):
    def test_fixed_routes(self):
        for name in ('m8_combined_v2','m8_straight30_v1'):
            report=require_feasible_route(load_route(DIRECTORY/'scenarios'/(name+'.json')))
            self.assertEqual(report['status'],'PASS_NECESSARY_INERTIAL_BOUNDS')
            self.assertFalse(report['tracking_guaranteed'])
        with self.assertRaises(ValueError):
            require_feasible_route(load_route(DIRECTORY/'scenarios/m8_combined_v1.json'))
    def test_exact_bounds_and_invalid_values(self):
        self.assertTrue(ramp_feasible(0,1,1,100,.5,50,50))
        self.assertFalse(ramp_feasible(0,1,.999,100,.5,50,50))
        self.assertTrue(ramp_feasible(1,0,1,100,.5,50,50))
        self.assertFalse(ramp_feasible(1,0,.999,100,.5,50,50))
        for bad in (0,-1,math.inf,math.nan):
            self.assertFalse(ramp_feasible(0,1,bad))
        self.assertFalse(ramp_feasible(0,12,20))
        self.assertFalse(ramp_feasible(0,1,20,mass=0))
    def test_infeasible_cli_does_not_create_runtime_or_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cmd=[sys.executable,str(DIRECTORY/'m7_1o_run.py')]
            for key in ('engine','source','python','fixture','runtime','output'):
                cmd+=['--'+key,str(root/key)]
            cmd+=['--route-profile',str(DIRECTORY/'scenarios/m8_combined_v1.json'),'--propulsion-aware']
            result=subprocess.run(cmd,text=True,capture_output=True,timeout=5)
            self.assertEqual(result.returncode,2)
            self.assertIn('reference exceeds configured inertial torque capacity',result.stderr)
            self.assertEqual(list(root.iterdir()),[])

if __name__=='__main__':unittest.main()
