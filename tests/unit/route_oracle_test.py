"""Analytic checks for the independent route measurements."""
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

DIRECTORY=Path(__file__).resolve().parents[1]/'integration/carla'
sys.path.insert(0,str(DIRECTORY))
from m8_route_contract import load_route
from m8_route_oracle import RouteOracle, rear_pose, route_metrics


class RouteOracleTest(unittest.TestCase):
    def test_frozen_route_and_corrupt_geometry(self):
        original=load_route(DIRECTORY/'scenarios/m8_curve30_v1.json')
        self.assertEqual(len(original['points']),721)
        for key,value in [('x',float('nan')),('junction',True),('width',2),('lane',-2)]:
            bad=copy.deepcopy(original);bad['points'][10][key]=value
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'route.json';p.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):load_route(p)

    def test_rear_axle_rotation_and_left_positive(self):
        state=dict(position_ue_m=[10,20,30],rotation_ue_deg=[0,0,90])
        pose=rear_pose(state,[-2,0,0])
        self.assertAlmostEqual(pose['x_m'],10)
        self.assertAlmostEqual(pose['y_m'],-18)
        self.assertAlmostEqual(pose['yaw_rad'],-math.pi/2)
        state['rotation_ue_deg']=[0,90,0]
        pose=rear_pose(state,[-2,0,1])
        self.assertAlmostEqual(pose['x_m'],9)

    def test_segment_projection_signed_errors(self):
        route=RouteOracle(dict(points=[dict(x=0,y=0,yaw=0),dict(x=10,y=0,yaw=0)]))
        q=route.project(dict(x_m=3,y_m=.2,yaw_rad=.03))
        self.assertAlmostEqual(q['progress_m'],3)
        self.assertAlmostEqual(q['cross_track_m'],.2)
        self.assertAlmostEqual(q['heading_error_rad'],.03)

    def test_nearest_rank_and_complete_sampling(self):
        states=[]
        for i in range(3601):
            states.append((i,i*10000000,dict(progress_m=i/10,cross_track_m=i/10000,
                heading_error_rad=i/100000,route_curvature=.005)))
        # Marker at36s leaves full [25,35) window.
        m=route_metrics(states,0,360)
        self.assertEqual(m['samples'],721)
        self.assertEqual(m['plateau_samples'],200)
        self.assertAlmostEqual(m['cross_track_p95_m'],.342)
        with self.assertRaises(ValueError):route_metrics(states[:1000],0,360)
        with self.assertRaises(ValueError):route_metrics(states[:500]+states[501:],0,360)


if __name__=='__main__':unittest.main()
