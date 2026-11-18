import hashlib
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from endurance_recording_v1 import ShardRecorder, RawReader
from recording_cache_v1 import CacheRelease, release
from owner_split_profile_v1 import validate_client
import test_owner_split_profile_v1 as owner_tests


class RecordingCacheTests(unittest.TestCase):
    def test_real_cache_release_preserves_bytes_and_inode(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'closed.tar';data=bytes(range(256))*16384
            path.write_bytes(data);before=path.stat()
            report=release(path);after=path.stat()
            self.assertEqual(report['status'],'HINT_APPLIED')
            self.assertEqual(report['bytes'],len(data))
            self.assertEqual((before.st_ino,before.st_mtime_ns),(after.st_ino,after.st_mtime_ns))
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),hashlib.sha256(data).digest())
            self.assertLessEqual(report['resident_pages_after'],report['resident_pages_before'])

    def test_closed_shards_including_last_remain_readable(self):
        with tempfile.TemporaryDirectory() as folder:
            recorder=ShardRecorder(folder,3,1024*1024,encoding='bgra',shard_bytes=100,release_cache=True)
            raw={i:bytes([i])*64 for i in range(1,4)}
            for i,data in raw.items():recorder.offer(dict(frame=i,width=4,height=4),data)
            recorder.queue.join();recorder.cache.queue.join()
            self.assertTrue(recorder.close());self.assertFalse(recorder.failed())
            report=recorder.report();cache=report['cache_release']
            self.assertTrue(cache['stopped']);self.assertEqual(cache['errors'],[])
            self.assertEqual(set(report['archives']),{r['archive'] for r in cache['records']})
            reader=RawReader(folder)
            try:
                for row in report['records']:self.assertEqual(reader.read(row),raw[row['frame']])
            finally:reader.close()

    def test_hint_failure_marks_run_failed_without_discarding_frame(self):
        with tempfile.TemporaryDirectory() as folder,patch('recording_cache_v1.release',side_effect=OSError('fixture')):
            recorder=ShardRecorder(folder,1,10000,encoding='bgra',release_cache=True)
            recorder.offer(dict(frame=1,width=4,height=4),bytes(64))
            self.assertTrue(recorder.close());self.assertTrue(recorder.failed())
            report=recorder.report();self.assertEqual(len(report['records']),1)
            self.assertIn('fixture',report['cache_release']['errors'][0])
            self.assertTrue((Path(folder)/report['archives'][0]).is_file())

    def test_queue_is_bounded_and_close_keeps_deadline(self):
        entered=threading.Event();finish=threading.Event()
        def held(path):entered.set();finish.wait(3);return dict(archive=path.name)
        with patch('recording_cache_v1.release',side_effect=held):
            worker=CacheRelease()
            try:
                worker.offer('a');self.assertTrue(entered.wait(2))
                worker.offer('b');worker.offer('c');worker.offer('d')
                self.assertTrue(worker.errors)
                begin=time.monotonic();self.assertFalse(worker.close(begin+.01))
                self.assertLess(time.monotonic()-begin,.5)
            finally:
                finish.set();self.assertTrue(worker.close(time.monotonic()+3))

    def test_symlink_never_targets_unrelated_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source';path.write_bytes(b'original')
            link=Path(folder)/'link';link.symlink_to(path)
            with self.assertRaises(OSError):release(link)
            self.assertEqual(path.read_bytes(),b'original')


class ExplicitHvPolicyTests(unittest.TestCase):
    def test_adr0066_requires_matching_explicit_endurance_profile(self):
        factory=owner_tests.OwnerSplitProfileTests().owner
        for seconds in (30,300):
            args=dict(endurance_seconds=seconds,ticks=seconds*200,paired_renderer_port=2300,
                      paired_condition='normal',paired_export_hz=20)
            validate_client(factory(**args,wall_profile='wall5-hv50-v1',hv_dependency_ms=50))
            for extra in (dict(wall_profile='wall5-hv30-v1',hv_dependency_ms=50),
                          dict(wall_profile='wall5-hv50-v1',hv_dependency_ms=30),
                          dict(wall_profile='unknown',hv_dependency_ms=50)):
                with self.assertRaises(ValueError):validate_client(factory(**args,**extra))
        with self.assertRaises(ValueError):validate_client(factory(wall_profile='wall5-hv50-v1',hv_dependency_ms=50))

    def test_audit_requires_matching_policy_complete_closed_shards_and_no_errors(self):
        import copy
        from audit_hv50_cache_v1 import validate
        server=dict(wall_profile='wall5-hv50-v1',release_recording_cache=True)
        capture=dict(wall_profile='wall5-hv50-v1',hv_dependency_ns=50_000_000,
                     native_initial=dict(hv_dependency_ns=50_000_000),model_step_ns=5_000_000)
        renderer=dict(recorder=dict(mode='bounded-bgra-shards',archives=['a.tar'],cache_release=dict(
            enabled=True,workers=1,capacity=2,stopped=True,errors=[],records=[dict(
                archive='a.tar',bytes=100,begin_ns=20,synced_ns=30,end_ns=40,status='HINT_APPLIED')])),
            raw=[dict(archive='a.tar',write_end_ns=10)])
        validate(server,capture,renderer)
        for mutation in ('missing','open','error','policy','step'):
            s,c,r=copy.deepcopy((server,capture,renderer))
            if mutation=='missing':r['recorder']['archives'].append('b.tar')
            if mutation=='open':r['raw'][0]['write_end_ns']=21
            if mutation=='error':r['recorder']['cache_release']['errors']=['sync error']
            if mutation=='policy':c['hv_dependency_ns']=30_000_000
            if mutation=='step':c['model_step_ns']=10_000_000
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):validate(s,c,r)


if __name__=='__main__':unittest.main()
