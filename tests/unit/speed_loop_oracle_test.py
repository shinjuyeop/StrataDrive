"""Corrupt complete synthetic evidence to exercise the independent M8 judge."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1]/'integration/longitudinal/check_speed_loop.py'
SPEC = importlib.util.spec_from_file_location('speed_loop_oracle', PATH)
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)


class SpeedLoopOracleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.origin = 1_782_000_000
        for name, value in {
            'config.json': dict(mode='nominal', duration_ns=92_000_000_000, injection_ns=25_000_000_000),
            'runtime.json': dict(passed=True, reason='', speed_origin_ns=self.origin, speed_fault=0),
            'logical-normal.json': dict(passed=True, first_fault_ns=0),
        }.items(): (self.root/name).write_text(json.dumps(value))
        self.control = []
        for i in range(4350):
            now = self.origin+i*20_000_000
            self.control.append(dict(now_ns=now, profile_ns=i*20_000_000, speed_source_ns=now-1_000_000,
                request_expiry_ns=now+29_000_001, epoch=1, sequence=i, target_mps=oracle.reference(i*.02),
                speed_mps=oracle.reference(i*.02), acceleration_mps2=0, integral=0))
        self.physical = []
        for i in range(9200):
            now = 1_001_000_000+i*10_000_000
            self.physical.append(dict(now_ns=now, speed_mps=oracle.reference(max(0, (now-self.origin)/1e9)),
                distance_m=i, torque_nm=0, pressure_pa=100000, bus_v=0, balance_j=0,
                model_epoch=7, model_sequence=i, contacts=0, command_source_ns=now,
                command_root_sequence=i//2, run_gate=1))

    def judge(self):
        for name, rows in [('control.csv', self.control), ('physical.csv', self.physical)]:
            with (self.root/name).open('w') as stream:
                writer=csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
        return oracle.judge(self.root)

    def test_complete_evidence_passes(self):
        self.assertTrue(self.judge()['pass'])

    def test_missing_control_fails(self):
        self.control.pop(100)
        self.assertFalse(self.judge()['pass'])

    def test_extended_expiry_fails(self):
        self.control[50]['request_expiry_ns'] += 1
        self.assertFalse(self.judge()['pass'])

    def test_frozen_acquisition_fails(self):
        self.control[50]['speed_source_ns'] = self.control[49]['speed_source_ns']
        self.control[50]['request_expiry_ns'] = self.control[49]['request_expiry_ns']
        self.assertFalse(self.judge()['pass'])

    def test_physical_overspeed_fails(self):
        self.physical[3000]['speed_mps'] = 10
        self.assertFalse(self.judge()['pass'])

    def test_nonfinite_control_fails(self):
        self.control[50]['integral'] = float('nan')
        self.assertFalse(self.judge()['pass'])

    def test_physical_reset_fails(self):
        self.physical[5000]['model_sequence'] = 0
        self.assertFalse(self.judge()['pass'])

    def test_truncated_duration_fails(self):
        self.physical.pop()
        self.assertFalse(self.judge()['pass'])


if __name__ == '__main__':
    unittest.main()
