import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from audit_fence_compare_v1 import coverage, reader
from control_shadow_capture_v1 import Capture
from run_carla_control_shadow_v1 import timing_runtime, sha

ROOT=Path(__file__).resolve().parents[3]


class FenceCompareTests(unittest.TestCase):
    def test_union_clips_and_never_double_counts_nested_spans(self):
        rows=[dict(stage='event_wait',begin=a,end=b) for a,b in ((0,15),(12,25),(28,40))]
        self.assertEqual(coverage(rows,'event_wait',10,30),17)
        self.assertEqual(coverage(rows,'other',10,30),0)

    def test_all_four_journals_required_and_route_is_preserved(self):
        lines=[]
        for component,stage in [('launch','frame_sync'),('carla','post_tick'),('engine_fence','fence_wait'),('render_fence','route_render_only')]:
            lines += [reader.PREFIX+json.dumps(dict(component=component,stage=stage,frame=3,begin=10,end=20,cpu_begin=2,cpu_end=5)),
                      reader.END+json.dumps(dict(component=component,rows=1,overflow=0))]
        self.assertEqual(reader.parse('\n'.join(lines))[-1]['stage'],'route_render_only')
        with self.assertRaises(ValueError):reader.parse('\n'.join(lines[:-2]))

    def test_camera_absence_preserves_preparation_and_state_observer(self):
        with tempfile.TemporaryDirectory() as temp:
            args=SimpleNamespace(detector=Path('model'),models=Path('models'),library=Path('kernel'),wall_clock=9,output=Path(temp),camera_absent_control=True)
            capture=Capture(args);world=Mock(id=7);actor=Mock();carla=Mock()
            worker=Mock();worker.prepare.return_value=True;worker.wait_prepared.return_value=True;worker.preparation_status.return_value={'state':'READY'}
            try:
                with patch('control_shadow_capture_v1.StagedKernelBackend') as backend,patch('control_shadow_capture_v1.IpcWorldPerception',return_value=worker):
                    capture.attach(world,actor,carla)
                backend.assert_called_once();worker.prepare.assert_called_once();worker.wait_prepared.assert_called_once_with(10)
                world.on_tick.assert_called_once_with(capture.observed);world.spawn_actor.assert_not_called();world.get_blueprint_library.assert_not_called()
                self.assertIsNone(capture.sensor);self.assertEqual(capture.report['camera_condition'],'absent')
                self.assertEqual(capture.report['camera'],[])
            finally:capture.tx.close();capture.rx.close()

    def test_preparation_failure_never_spawns_sensor_or_observer(self):
        with tempfile.TemporaryDirectory() as temp:
            capture=Capture(SimpleNamespace(detector=Path('model'),models=Path('models'),library=Path('kernel'),wall_clock=9,output=Path(temp),camera_absent_control=True))
            world=Mock(id=7);worker=Mock();worker.prepare.return_value=False
            try:
                with patch('control_shadow_capture_v1.StagedKernelBackend'),patch('control_shadow_capture_v1.IpcWorldPerception',return_value=worker),self.assertRaises(RuntimeError):
                    capture.attach(world,Mock(),Mock())
                world.on_tick.assert_not_called();world.spawn_actor.assert_not_called()
            finally:capture.tx.close();capture.rx.close()

    def test_fence_libraries_must_match_frozen_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);module='Unreal/CarlaUE4/Plugins/Carla/Binaries/Linux/libUE4Editor-Carla.so'
            paths=dict(module=base/module,executable=base/'Engine/Binaries/Linux/UE4Editor',engine=base/'Engine/Binaries/Linux/libUE4Editor-Engine.so',rendercore=base/'Engine/Binaries/Linux/libUE4Editor-RenderCore.so')
            for p in paths.values():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'pinned')
            data=dict(schema='m10-fence-compare-build-v1',installed={k:dict(path=str(p),original_sha256='base',instrumented_sha256=sha(p)) for k,p in paths.items()})
            manifest=base/'manifest.json';manifest.write_text(json.dumps(data));freeze=base/'freeze.json'
            external={str(manifest):sha(manifest),**{str(p):sha(p) for p in paths.values()}};freeze.write_text(json.dumps(dict(external=external)))
            profile=dict(baseline_module_sha256='base',external_files={module:'previous'})
            timing_runtime(manifest,freeze,base,base,profile)
            del external[str(paths['rendercore'])];freeze.write_text(json.dumps(dict(external=external)))
            with self.assertRaises(ValueError):timing_runtime(manifest,freeze,base,base,profile)

    def test_engine_patch_preserves_fence_and_task_calls(self):
        spec=importlib.util.spec_from_file_location('fence_builder',ROOT/'tools/carla/m10_fence_compare_v1/build.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        tasks='FTaskGraphInterface::Get().ProcessThreadUntilIdle(ENamedThreads::GameThread);'
        text='void FFrameEndSync::Sync( bool bAllowOneFrameThreadLag )\n{\nFence[EventIndex].BeginFence(true);\n'+tasks+'\n'+tasks+'\nProcessAsyncLoading(true, false, TimeLimit);\nFence[EventIndex].Wait(bEmptyGameThreadTasks);\n}\nFString appGetStartupMap('
        result=builder.patch_engine(text)
        self.assertEqual(result.count(tasks),2);self.assertEqual(result.count('Fence[EventIndex].Wait(bEmptyGameThreadTasks);'),1)
        self.assertEqual(result.count('Fence[EventIndex].BeginFence(true);'),1)
        with self.assertRaises(ValueError):builder.patch_engine(text+text)


if __name__=='__main__':unittest.main()
