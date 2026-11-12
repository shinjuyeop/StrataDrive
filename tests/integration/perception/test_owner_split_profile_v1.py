from types import SimpleNamespace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from owner_split_profile_v1 import configure_owner, validate_client
from run_carla_control_shadow_v1 import original_owner_runtime
from physical_ai.perception.world_async_v1 import ObservedWorldClock
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.async_native_2k_v1 import NativeResult
from control_shadow_capture_v1 import Capture


class OwnerSplitProfileTests(unittest.TestCase):
    def owner(self, **updates):
        fields=dict(execution_profile='owner5ms',cameras=False,camera_absent_control=True,
                    ticks=400,step_ms=5,hv_dependency_ms=30,warmup_ticks=150,fault='none')
        fields.update(updates)
        return SimpleNamespace(**fields)

    def test_owner_explicitly_disables_renderer_and_keeps_original_deadlines(self):
        validate_client(self.owner())
        command,client=configure_owner(['UE4Editor','-StrataM7SensorFrame5','-StrataM10ReadbackProfile'],['client','--ticks','200','--cameras','--camera-absent-control'],'owner5ms','absent')
        self.assertEqual(command,['UE4Editor','-StrataM7Wall5ms','-nullrhi','-norenderthread'])
        self.assertNotIn('--cameras',client)
        self.assertEqual(client[client.index('--ticks')+1],'400')
        self.assertEqual(client[-4:],['--execution-profile','owner5ms','--step-ms','5'])
        self.assertNotIn('--hv-dependency-ms',client)

    def test_mixed_camera_cadence_or_relaxed_deadline_is_rejected(self):
        for fields in ({'cameras':True},{'camera_absent_control':False},{'step_ms':10},
                       {'hv_dependency_ms':50},{'ticks':200},{'fault':'wall-gap'},
                       {'warmup_ticks':0},{'execution_profile':'unknown'}):
            with self.subTest(fields=fields),self.assertRaises(ValueError):
                validate_client(self.owner(**fields))
        with self.assertRaises(ValueError):configure_owner([],[],'owner5ms','2k')

    def test_existing_camera_and_absent_comparison_stay_ten_ms(self):
        for absent in (False,True):
            validate_client(self.owner(execution_profile='shadow10ms',cameras=True,
                                       camera_absent_control=absent,ticks=200,step_ms=10))
        command,client=['UE4Editor'],['client','--ticks','200','--cameras']
        self.assertEqual(configure_owner(command,client,'shadow10ms','2k'),(command,client))
        with self.assertRaises(ValueError):validate_client(self.owner(execution_profile='shadow10ms'))

    def test_original_four_libraries_must_be_bound_in_freeze(self):
        root=Path(__file__).resolve().parents[3]
        prior=json.loads((root/'docs/test-plan/evidence/m10_fence_compare_v1/build-02/manifest.json').read_text())
        pins={x['path']:x['original_sha256'] for x in prior['installed'].values()}
        module=Path(prior['installed']['module']['path'])
        source=module.parents[6]
        engine=Path(prior['installed']['executable']['path']).parents[3]
        profile=dict(external_files={},baseline_module_sha256=pins[str(module)])
        with tempfile.TemporaryDirectory() as temp,patch('run_carla_control_shadow_v1.sha',side_effect=lambda p:pins[str(p)]):
            freeze=Path(temp)/'freeze.json';freeze.write_text(json.dumps(dict(external=pins)))
            result=original_owner_runtime(freeze,source,engine,profile)
            self.assertIn(pins[str(module)],result.values())
            missing=dict(pins);del missing[prior['installed']['engine']['path']]
            freeze.write_text(json.dumps(dict(external=missing)))
            with self.assertRaises(ValueError):original_owner_runtime(freeze,source,engine,profile)

    def test_declared_five_ms_clock_preserves_original_source_and_gaps(self):
        clock=ObservedWorldClock(77,step_ns=5_000_000)
        self.assertEqual(clock.observe(77,20,100_000_000,5_000_000,1_000_000_000,1_000_000_001),'accepted')
        self.assertEqual(clock.observe(77,23,115_000_000,5_000_000,1_015_000_000,1_015_000_001),'accepted')
        self.assertEqual(clock.status()['counters']['missing'],2)
        self.assertEqual(clock.now(),115_000_000)
        self.assertFalse(clock.matches(FrameIdentity(1,77,22,110_000_000)))
        self.assertEqual(clock.observe(77,23,115_000_000,5_000_000,2_000_000_000,2_000_000_001),'duplicate')
        self.assertEqual(clock.status()['received_wall_ns'],1_015_000_000)
        with self.assertRaises(ValueError):clock.observe(77,24,125_000_000,10_000_000,2_001_000_000,2_001_000_001)
        self.assertTrue(clock.status()['failed'])

    def test_default_clock_stays_ten_ms_and_unknown_period_never_adapts(self):
        with self.assertRaises(ValueError):ObservedWorldClock(77).observe(77,20,100_000_000,5_000_000,1,2)
        for step in (True,0,5_000_000.0,20_000_000):
            with self.assertRaises(ValueError):ObservedWorldClock(77,step_ns=step)

    def test_first_five_ms_callback_reaches_real_prepared_worker_and_ipc_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            args=self.owner(detector=Path('model'),models=Path('models'),library=Path('library'),
                            wall_clock=9,output=Path(temp))
            capture=Capture(args);backend=Mock();backend.stages=[]
            backend.detector.session.get_providers.return_value=['test']
            backend.infer.side_effect=lambda packet:NativeResult(packet.identity)
            try:
                with patch('control_shadow_capture_v1.StagedKernelBackend',return_value=backend):
                    capture.attach(Mock(id=77),Mock(),Mock())
                snap=SimpleNamespace(id=77,frame=20,timestamp=SimpleNamespace(elapsed_seconds=.1,delta_seconds=.005))
                capture.observed(snap)
                self.assertEqual(capture.report['errors'],[])
                self.assertEqual(capture.report['world_step_ns'],5_000_000)
                self.assertEqual(capture.report['state'][0]['disposition'],'accepted')
                sample,frame=capture.worker.ipc_observation()
                self.assertEqual((frame,sample.source_ns),(20,100_000_000))
                self.assertEqual(sample.state_received_wall_ns,capture.report['state'][0]['begin_wall_ns'])
                self.assertIsNone(sample.publication)
                self.assertEqual(len(capture.report['preparation_calls']),3)
                self.assertEqual(capture.report['model_calls'],[])
            finally:
                capture.stop()


if __name__=='__main__':unittest.main()
