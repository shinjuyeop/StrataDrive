import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
import packaged_renderer_v1 as packaged
import owner_code_prefetch_v1 as code
import audit_packaged_renderer_v1 as audit


class PackagedRendererTests(unittest.TestCase):
    def test_frozen_executable_and_no_editor_feature_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'CarlaUE4-Linux-Shipping';binary.write_bytes(b'sealed executable')
            editor=['/UE4Editor','project','Town03_Opt','-carla-rpc-port=2300','-RenderOffscreen',
                    '-StrataIdleWait','-ExecCmds=t.MaxFPS 60','-ini:Engine:override']
            original=editor[:];freeze=dict(external={str(binary):hashlib.sha256(binary.read_bytes()).hexdigest()})
            argv,info=packaged.command(editor,binary,freeze)
            self.assertEqual(argv,[str(binary),'CarlaUE4','Town03_Opt','-carla-rpc-port=2300','-RenderOffscreen'])
            self.assertEqual(editor,original)
            self.assertFalse(info['editor_idle_wait']);self.assertIsNone(info['viewport_fps_cap'])
            binary.write_bytes(b'changed executable')
            with self.assertRaisesRegex(ValueError,'frozen'):packaged.command(editor,binary,freeze)

    def test_exhausted_original_startup_deadline_does_not_load_world(self):
        with patch.object(packaged.time,'monotonic_ns',return_value=180_000_000_001),patch.object(packaged.subprocess,'run') as run:
            with self.assertRaises(TimeoutError):packaged.prepare('python',0,{})
            run.assert_not_called()

    def test_unpark_failure_does_not_hide_shutdown_or_grant_more_time(self):
        process=Mock(pid=123,returncode=130);process.poll.return_value=None
        with (patch.object(packaged.subprocess,'run',side_effect=subprocess.TimeoutExpired('sdk',5)),
              patch.object(packaged.os,'killpg') as kill,
              patch.object(packaged.time,'monotonic',side_effect=[100,105])):
            result=packaged.stop(process,'python',{})
        self.assertEqual(result['unpark_error'],'TimeoutExpired')
        process.wait.assert_called_once_with(timeout=25)
        kill.assert_called_once_with(123,packaged.signal.SIGINT)

    def fixture(self):
        info=dict(executable='/stock/CarlaUE4-Linux-Shipping',editor_idle_wait=False,viewport_fps_cap=None,
            original_ini_sha256=None,restored_ini_sha256=None,
            preparation=dict(version=packaged.VERSION,map=packaged.MAP,xodr_sha256=packaged.XODR,parked=True,
                empty={'vehicle.*':0,'walker.*':0,'sensor.*':0},completed_ns=50))
        server=dict(packaged_renderer=info,argv=dict(renderer=[info['executable'],'-carla-rpc-port=2300']),
            process_started_ns=dict(renderer=1),client_completed_ns=1000,prefetch_owner_code=True,pids=dict(owner=123),
            shutdown=dict(renderer=dict(server_exit=130,begin_wall_ns=1001,end_wall_ns=2000,
                unpark=dict(completed_ns=1002,synchronous_after=False))))
        capture=dict(native_initial=dict(initial=100),owner_code_prefetch=dict(status='PREPARED_BEFORE_NATIVE_START',
            control_writes=0,limit_bytes=code.MAX_BYTES,limit_seconds=code.MAX_SECONDS,begin_ns=60,end_ns=70,
            read_bytes=10,files=[dict(read_bytes=10)],owner=dict(pid=123)))
        renderer=dict(quiescent_cleanup=dict(end_wall_ns=999))
        return server,capture,renderer

    def test_capture_sealed_before_shutdown_and_code_read_before_start(self):
        server,capture,renderer=self.fixture()
        self.assertEqual(audit.validate(server,capture,renderer)['owner_code_read_bytes'],10)
        for mutate in (
            lambda s,c,r:s['shutdown']['renderer'].update(begin_wall_ns=998),
            lambda s,c,r:s['shutdown']['renderer'].update(forced_stop=True),
            lambda s,c,r:s['packaged_renderer'].update(restored_ini_sha256='changed'),
            lambda s,c,r:s['packaged_renderer']['preparation'].update(xodr_sha256='wrong map'),
            lambda s,c,r:c['owner_code_prefetch'].update(end_ns=100),
            lambda s,c,r:c['owner_code_prefetch']['owner'].update(pid=124)):
            values=copy.deepcopy((server,capture,renderer));mutate(*values)
            with self.assertRaises(ValueError):audit.validate(*values)

    def test_original_physical_audit_failure_cannot_be_promoted(self):
        with patch.object(audit,'visual_audit',side_effect=ValueError('original physical gate')):
            with self.assertRaisesRegex(ValueError,'original physical gate'):audit.audit(Path('/unused'))


class OwnerCodePreparationTests(unittest.TestCase):
    def test_mapping_selection_uses_offsets_merges_overlap_and_excludes_mutable_data(self):
        maps='\n'.join([
            '1000-3000 r--p 00000000 08:01 7 /engine file',
            '3000-5000 r-xp 00001000 08:01 7 /engine file',
            '5000-6000 rw-p 00003000 08:01 7 /engine file',
            '6000-7000 r--p 00000000 08:01 8 /asset',
            '7000-8000 rw-p 00000000 00:00 0 [heap]'])
        result=code.ranges(maps)
        self.assertEqual(len(result),1);self.assertEqual(result[0]['spans'],[[0,0x3000]])

    def test_deleted_or_replaced_mapping_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'deleted'):
            code.ranges('1000-2000 r-xp 0 08:01 7 /engine (deleted)')
        with self.assertRaisesRegex(ValueError,'identity'):
            code.ranges('1000-2000 r-xp 0 08:01 7 /engine\n2000-3000 r--p 0 08:01 8 /engine')

    def test_real_process_guard_rejects_non_owner(self):
        with self.assertRaisesRegex(ValueError,'physical owner'):code.owner_identity(os.getpid())

    def test_real_mapped_file_reads_and_pre_io_size_rejection(self):
        # Exercise real proc mappings/offsets/EOF handling, with only the dedicated
        # engine identity replaced. This test never starts an engine or native ECU.
        # Other integration tests dlopen temporary libraries and then delete
        # them. A fresh process tests ordinary mappings without weakening the
        # deliberate rejection of a deleted executable mapping.
        script='''import os
import owner_code_prefetch_v1 as code
code.owner_identity=lambda pid:dict(pid=pid)
result=code.prefetch(os.getpid())
assert result['read_bytes']>0
assert result['read_bytes']==sum(f['read_bytes'] for f in result['files'])
code.MAX_BYTES=0
try:code.prefetch(os.getpid())
except ValueError as error:assert '2GiB' in str(error)
else:raise AssertionError('pre-I/O size bound was not enforced')
'''
        subprocess.run([sys.executable,'-c',script],env=dict(os.environ,
            PYTHONPATH=str(Path(code.__file__).parent)),check=True,timeout=15)


if __name__=='__main__':unittest.main()
