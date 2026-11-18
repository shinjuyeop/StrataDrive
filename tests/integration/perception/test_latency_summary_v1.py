import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('latency_summary',ROOT/'tools/m10_summarize_latency.py')
latency=importlib.util.module_from_spec(spec);spec.loader.exec_module(latency)


class LatencySummaryTests(unittest.TestCase):
    def row(self, acquired,callback,completed):
        return dict(original_acquisition_ns=acquired,callback_ns=callback,end_ns=completed)

    def test_result_at_original_scene_deadline_has_no_availability(self):
        result=latency.coverage([self.row(1,90_000_001,100_000_001)],1,200_000_001)
        self.assertEqual(result['available_ns'],0)
        self.assertEqual(result['maximum_unavailable_gap_ms'],200)

    def test_union_clipping_errors_and_duplicate_overlap(self):
        rows=[self.row(1,10_000_001,20_000_001),self.row(1,10_000_001,30_000_001),
              self.row(100_000_001,110_000_001,120_000_001),dict(error='inference failed')]
        result=latency.coverage(rows,25_000_001,150_000_001)
        self.assertEqual(result['available_ns'],105_000_000)
        self.assertEqual(result['maximum_unavailable_gap_ms'],20)
        self.assertEqual(result['merged_intervals'],2)
        self.assertFalse(result['control_acceptance_proven'])

    def test_new_callback_cannot_renew_old_scene(self):
        result=latency.coverage([self.row(1,99_000_001,99_500_001)],1,200_000_001)
        self.assertEqual(result['available_ns'],500_000)
        with self.assertRaises(ValueError):
            latency.coverage([self.row(2,1,3)],1,10)


if __name__=='__main__':unittest.main()
