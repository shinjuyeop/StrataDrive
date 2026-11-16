import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from profile_host_clock_v1 import Counters
from audit_state_path_v1 import PHASES,join,hv_origin,hv_join


class StatePathTests(unittest.TestCase):
    def test_missing_capture_failure_is_independent_of_extraction_root(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);results=[]
            for name in ('original','restored'):
                output=root/(name+'.json')
                result=subprocess.run([sys.executable,str(Path(__file__).with_name('audit_state_path_v1.py')),
                    '--run',str(root/name),'--output',str(output)],capture_output=True,text=True)
                self.assertEqual(result.returncode,1);results.append(json.loads(output.read_text()))
            self.assertEqual(results[0],results[1]);self.assertIn('<run>/server.json',results[0]['error'])

    def test_join_rejects_restamped_acquisition_and_wrong_consumption(self):
        receipt=dict(frame='7',ticket='2',physics_acquisition_begin_ns='140',physics_acquisition_end_ns='150',
            wall_applied_ns='125',original_actual=dict(native=dict(normal=True)),
            state_path={name:dict(wall_ns=100+i*10,cpu_ns=50+i*5) for i,name in enumerate(PHASES)})
        receipt['state_path'].update(max_pump_gap_ns='20',max_rpc_ns='15')
        native=dict(frame=7,acquired_begin_ns=140,read_begin_ns=181,read_end_ns=185,service_begin_ns=186,
                    service_end_ns=190,proof_publish_ns=195,cpu_begin_ns=100,cpu_end_ns=105)
        path=receipt.pop('state_path')
        original=json.dumps(receipt,sort_keys=True)
        self.assertEqual(join(receipt,native,path)['publication_to_native_upper_ns'],5)
        self.assertEqual(json.dumps(receipt,sort_keys=True),original)
        for change in ({'frame':8},{'acquired_begin_ns':141},{'read_end_ns':179},{'service_end_ns':180}):
            with self.assertRaises(ValueError):join(receipt,dict(native,**change),path)
        receipt['physics_acquisition_begin_ns']='141'
        with self.assertRaises(ValueError):join(receipt,native,path)

    def test_hv_depends_on_original_actuator_and_coil_not_acquisition(self):
        receipt=dict(frame='7',wall_applied_ns='125',physics_acquisition_begin_ns='140',
            coil_source_ns='115',original_actual=dict(admitted_actual=dict(oldest_actuator_ns='110')))
        origin=hv_origin(receipt)
        native=dict(energy_end=500,hv_source=140,hv_dependency=110,now=200)
        self.assertEqual(hv_join(native,{500:origin})['dependency_ns'],110)
        for change in ({'energy_end':501},{'hv_source':141},{'hv_dependency':140},{'hv_dependency':115},{'now':139}):
            with self.assertRaises(ValueError):hv_join(dict(native,**change),{500:origin})
        receipt['coil_source_ns']='105'
        self.assertEqual(hv_origin(receipt)['dependency_ns'],105)
        receipt['coil_source_ns']='0';receipt['original_actual']['admitted_actual']['oldest_actuator_ns']='0'
        self.assertEqual(hv_origin(receipt)['dependency_ns'],125)
        self.assertIsNone(hv_join(dict(native,hv_source=0,hv_dependency=0),{}))

    def test_counter_reads_new_value_and_preserves_missing_invalid_errors(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);value=root/'value';bad=root/'bad';missing=root/'missing'
            value.write_text('800000\n');bad.write_text('not-a-counter')
            reader=Counters([value,bad,missing])
            try:
                self.assertEqual(reader.sample(),({str(value):800000},{}))
                self.assertEqual(set(reader.unavailable),{str(bad),str(missing)})
                value.write_text('3900000\n');self.assertEqual(reader.sample()[0][str(value)],3900000)
                value.write_text('bad');values,errors=reader.sample()
                self.assertNotIn(str(value),values);self.assertIn(str(value),errors)
            finally:reader.close()

    def test_fast_sampler_stops_with_owned_root_and_records_its_cost(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(.5)'])
            try:
                subprocess.run([sys.executable,str(Path(__file__).with_name('profile_host_clock_v1.py')),
                    '--pid',str(child.pid),'--seconds','1','--output',str(root/'clock.jsonl')],
                    stdout=subprocess.DEVNULL,check=True,timeout=3)
                result=json.loads((root/'clock.summary.json').read_text())
                self.assertGreater(result['samples'],0);self.assertGreater(result['monitor_cpu_seconds'],0)
                self.assertLess(result['wall_seconds'],.9)
                rows=[json.loads(x) for x in (root/'clock.jsonl').read_text().splitlines()]
                self.assertTrue(all(r['end_ns']>=r['wall_ns'] for r in rows))
            finally:child.wait(timeout=2)


if __name__ == '__main__':unittest.main()
