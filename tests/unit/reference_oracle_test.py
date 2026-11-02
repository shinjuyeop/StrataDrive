"""Independent reference timeline, frozen geometry and complete-window checks."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

DIRECTORY=Path(__file__).resolve().parents[1]/'integration/carla'
sys.path.insert(0,str(DIRECTORY))
from m8_route_contract import load_route
from m8_reference_oracle import Reference
from audit_m8_route import target
from m8_route_oracle import RouteOracle


class ReferenceOracleTest(unittest.TestCase):
    def test_v2_uses_extended_straight_and_feasible_startup(self):
        definition=load_route(DIRECTORY/'scenarios/m8_combined_v2.json')
        route=RouteOracle(definition)
        curve=[s for s in route.segments if s[-1]>=.001]
        self.assertEqual(len(definition['points']),779)
        self.assertGreater(curve[0][5],280)
        self.assertLess(curve[-1][5]+curve[-1][4],381)
        self.assertEqual(definition['completion_m'],395)
        self.assertLess(1696*.355*(30/3.6/20),300)
        self.assertGreater(1696*.355*(30/3.6/10),300)
        r=Reference('S03','v2')
        self.assertAlmostEqual(r.observe(10000000000,20),15/3.6)
        r.observe(35000000000,229.999);self.assertIsNone(r.slow_ns)
        self.assertAlmostEqual(r.observe(38000000000,230),30/3.6)
        self.assertAlmostEqual(r.observe(41000000000,250),25/3.6)
        r.observe(63000000000,379.999);self.assertIsNone(r.stop_ns)
        self.assertAlmostEqual(r.observe(64000000000,380),20/3.6)
        self.assertAlmostEqual(r.observe(68000000000,395),10/3.6)
        self.assertEqual(r.windows(),([(25.,35.,30.),(49.,59.,20.)],(74.,76.)))
        for hz in (20,50,100):
            samples=[(i/hz,r.target(i/hz)) for i in range(80*hz)]
            self.assertLess(r.metrics(samples,10*hz,2*hz)['max_plateau_error_kmh'],1e-12)

    def test_fixed_routes_and_identity_rejections(self):
        for name,scenario,count in [('straight30','S01',721),('combined','S03',679)]:
            original=load_route(DIRECTORY/f'scenarios/m8_{name}_v1.json')
            self.assertEqual((original['scenario'],len(original['points'])),(scenario,count))
            for mutation in [lambda r:r.update(ticks=6001),lambda r:r['points'][10].update(lane_type='Shoulder'),
                             lambda r:r['points'][100].update(x=r['points'][100]['x']+.001),
                             lambda r:r.update(completion_m=100),lambda r:r.update(scenario='S02')]:
                bad=copy.deepcopy(original);mutation(bad)
                with tempfile.TemporaryDirectory() as d:
                    p=Path(d)/'route.json';p.write_text(json.dumps(bad))
                    with self.assertRaises(ValueError):load_route(p)

    def test_approved_geometry_has_required_segments(self):
        straight=RouteOracle(load_route(DIRECTORY/'scenarios/m8_straight30_v1.json'))
        self.assertEqual(max(s[-1] for s in straight.segments),0)
        combined=RouteOracle(load_route(DIRECTORY/'scenarios/m8_combined_v1.json'))
        curve=[s for s in combined.segments if s[-1]>=.001]
        self.assertGreater(curve[0][5],230)
        self.assertLess(curve[-1][5]+curve[-1][4],331)
        self.assertLess(max(s[-1] for s in curve),.0225)
        self.assertGreater(combined.distances[-1],358)

    def test_markers_exact_threshold_once_and_history_not_backdated(self):
        r=Reference('S03')
        self.assertAlmostEqual(r.observe(0,0),0)
        self.assertAlmostEqual(r.observe(25000000000,179.999),30/3.6)
        self.assertIsNone(r.slow_ns)
        self.assertAlmostEqual(r.observe(27000000000,180),30/3.6)
        self.assertAlmostEqual(r.observe(30000000000,179.9),25/3.6)
        self.assertAlmostEqual(r.observe(33000000000,225),20/3.6)
        r.observe(53000000000,329.999);self.assertIsNone(r.stop_ns)
        self.assertAlmostEqual(r.observe(54000000000,330),20/3.6)
        self.assertAlmostEqual(r.observe(58000000000,329.9),10/3.6)
        self.assertAlmostEqual(r.observe(62000000000,352),0)
        self.assertEqual(r.slow_ns,27000000000);self.assertEqual(r.stop_ns,54000000000)
        self.assertAlmostEqual(r.target(25),30/3.6)
        self.assertAlmostEqual(r.target(30),25/3.6)
        self.assertAlmostEqual(r.target(53),20/3.6)
        self.assertEqual(r.windows(),([(15.,25.,30.),(38.,48.,20.)],(64.,66.)))

    def test_s01_preserves_s02_timeline(self):
        r=Reference('S01')
        for i in range(-100,6001):self.assertAlmostEqual(r.target(i*.01),target(i*.01),places=12)

    def test_missing_markers_or_overlapping_windows_rejected(self):
        r=Reference('S03')
        with self.assertRaises(ValueError):r.windows()
        r.observe(24000000000,180);r.observe(50000000000,330)
        with self.assertRaises(ValueError):r.windows()
        r=Reference('S03');r.observe(27000000000,180);r.observe(47000000000,330)
        with self.assertRaises(ValueError):r.windows()

    def test_all_rates_and_missing_sample_fail(self):
        r=Reference('S03');r.observe(27000000000,180);r.observe(54000000000,330)
        for hz in (20,50,100):
            samples=[(i/hz,r.target(i/hz)) for i in range(80*hz)]
            result=r.metrics(samples,10*hz,2*hz)
            self.assertEqual(result['max_positive_target_overspeed_percent'],0)
            self.assertLess(result['max_plateau_error_kmh'],1e-12)
            missing=[(t,v) for t,v in samples if t!=40]
            with self.assertRaises(ValueError):r.metrics(missing,10*hz,2*hz)
            fast=[(t,v+.4 if t==40 else v) for t,v in samples]
            self.assertGreater(r.metrics(fast,10*hz,2*hz)['max_plateau_error_kmh'],1)


if __name__=='__main__':unittest.main()
