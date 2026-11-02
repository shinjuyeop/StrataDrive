import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

DIRECTORY=Path(__file__).resolve().parents[1]/'integration/carla'
sys.path.insert(0,str(DIRECTORY))
from m8_route_contract import load_route
from m8_stop30_oracle import plateau_samples

class Stop30ContractTest(unittest.TestCase):
    def test_separate_frozen_identity_keeps_original_straight_geometry(self):
        new=load_route(DIRECTORY/'scenarios/m8_stop30_v1.json')
        old=load_route(DIRECTORY/'scenarios/m8_straight30_v1.json')
        self.assertEqual(new['points'],old['points'])
        self.assertEqual(new['stop_configuration']['braking_timeout_ns'],10_000_000_000)
        self.assertEqual(new['stop_trigger_ns'],35_000_000_000)
        self.assertNotIn('stop_configuration',old)
    def test_stop_budget_target_geometry_and_event_cannot_be_mutated(self):
        original=load_route(DIRECTORY/'scenarios/m8_stop30_v1.json')
        changes=[lambda r:r['stop_configuration'].update(braking_timeout_ns=5_000_000_000),
                 lambda r:r['stop_configuration'].update(deceleration_mps2=2),
                 lambda r:r.update(stop_trigger_ns=40_000_000_000),
                 lambda r:r['points'][10].update(x=0),lambda r:r.update(ticks=8000)]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'changed.json'
            for change in changes:
                with self.subTest(change=changes.index(change)):
                    r=copy.deepcopy(original);change(r);p.write_text(json.dumps(r))
                    with self.assertRaises(ValueError):load_route(p)

    def test_plateau_uses_last_original_acquisition_after_final_pi(self):
        origin=1_000_000_000
        samples={origin+25_008_000_000+i*10_000_000:30/3.6/.355 for i in range(1000)}
        # The last slot is after the final PI input but still before the35s event.
        samples[origin+34_988_000_000]=29.5/3.6/.355
        errors=plateau_samples(samples,samples,origin)
        self.assertEqual(len(errors),500)
        self.assertAlmostEqual(errors[-1],.5)

    def test_plateau_rejects_missing_final_acquisition_and_physics_mismatch(self):
        origin=1_000_000_000
        samples={origin+25_008_000_000+i*10_000_000:30/3.6/.355 for i in range(1000)}
        incomplete=dict(samples);del incomplete[max(incomplete)]
        with self.assertRaises(ValueError):plateau_samples(incomplete,samples,origin)
        changed=dict(samples);changed[max(changed)]+=1
        with self.assertRaises(ValueError):plateau_samples(changed,samples,origin)
