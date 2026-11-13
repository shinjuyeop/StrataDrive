import copy
import errno
import json
import os
import resource
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from endurance_host_v1 import ENV,command,validate,owner_command,check_owner


class HostTests(unittest.TestCase):
    def test_owner_scheduler_is_explicit_and_verified(self):
        resources=dict(owner_scheduler=dict(policy='SCHED_RR',priority=8))
        self.assertEqual(owner_command({},['server']),['server'])
        self.assertEqual(owner_command(resources,['server']),['chrt','-r','8','server'])
        with patch('endurance_host_v1.os.sched_getscheduler',return_value=os.SCHED_OTHER):
            with self.assertRaises(ValueError):check_owner(resources,os.getpid())

    @unittest.skipUnless(resource.getrlimit(resource.RLIMIT_RTPRIO)[0]>=8,'host does not grant owned RR8')
    def test_optional_owned_realtime_exec(self):
        resources=dict(owner_scheduler=dict(policy='SCHED_RR',priority=8))
        command=owner_command(resources,[sys.executable,'-c','import os,json;print(json.dumps([os.sched_getscheduler(0),os.sched_getparam(0).sched_priority]))'])
        self.assertEqual(json.loads(subprocess.check_output(command,text=True)),[os.SCHED_RR,8])

    def test_roles_cannot_share_a_core_even_through_smt(self):
        plan=dict(owner=[0,4],native=[1,5],renderer=[2,6],observer=[3,7])
        topology={c:(0,c%4) for c in range(8)}
        self.assertEqual(validate(plan,set(range(8)),topology),plan)
        for invalid in (dict(plan,observer=[4]),dict(plan,observer=[3,6]),
                        dict(plan,observer=[8]),dict(plan,observer=[])):
            with self.assertRaises(ValueError):validate(invalid,set(range(8)),topology)
        invalid=copy.deepcopy(plan);del invalid['native']
        with self.assertRaises(ValueError):validate(invalid,set(range(8)),topology)

    def test_exec_placement_preserves_arguments_and_applies_affinity(self):
        cpu=min(os.sched_getaffinity(0));argv=[sys.executable,'-c','import os;print(sorted(os.sched_getaffinity(0)))']
        with patch.dict(os.environ,{ENV:json.dumps(dict(native=[cpu]))}):
            actual=command('native',argv)
            self.assertEqual(actual[3:],argv)
            self.assertEqual(json.loads(subprocess.check_output(actual,text=True)),[cpu])
        with patch.dict(os.environ,{},clear=True):self.assertEqual(command('native',argv),argv)

    def test_cross_device_seal_verifies_and_retains_original(self):
        from endurance_recording_v1 import ShardRecorder
        from seal_endurance_v1 import seal
        from check_endurance_archive_v1 import checked_members
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=root/'run';folder=run/'capture/paired/renderer'
            recorder=ShardRecorder(folder,2,1_000_000)
            recorder.offer(dict(frame=1,width=4,height=4),bytes(64));self.assertTrue(recorder.close())
            (folder/'result.json').write_text(json.dumps(dict(raw=recorder.report()['records'])))
            prior=root/'prior.json';prior.write_text(json.dumps(dict(count=0,rgb_sha256=[])))
            bundle=root/'bundle'
            with patch('seal_endurance_v1.os.link',side_effect=OSError(errno.EXDEV,'fixture')):
                self.assertEqual(seal(run,bundle,prior)['raw_packets'],1)
            manifest=json.loads((bundle/'raw-manifest.json').read_text())['archives'][0]
            source=run/manifest['original'];target=bundle/manifest['archive']
            self.assertNotEqual(source.stat().st_ino,target.stat().st_ino)
            self.assertEqual(source.read_bytes(),target.read_bytes());checked_members(target,manifest)


if __name__=='__main__':unittest.main()
