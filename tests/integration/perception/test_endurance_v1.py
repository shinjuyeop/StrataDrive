import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from endurance_recording_v1 import ShardRecorder,RawReader,Zstd
from endurance_profile_v1 import limits,camera_pacing
from owner_split_profile_v1 import validate_client
import test_owner_split_profile_v1 as owner_tests


class EnduranceTests(unittest.TestCase):
    def test_readback_pump_can_be_faster_than_camera_without_unbounding_raw_rate(self):
        self.assertEqual(camera_pacing(10,50,True),10)
        self.assertEqual(camera_pacing(20,100,True),10)
        self.assertEqual(camera_pacing(20,50),20)
        for args in ((20,50,True),(0,50,True),(10,100,False),(20,25,False),(30,100,False)):
            with self.assertRaises(ValueError):camera_pacing(*args)

    def test_uncompressed_spool_preserves_alpha_and_rejects_changed_size_or_codec(self):
        with tempfile.TemporaryDirectory() as d:
            raw=bytes(range(64));recorder=ShardRecorder(d,2,1_000_000,encoding='bgra')
            recorder.offer(dict(frame=1,width=4,height=4),raw);self.assertTrue(recorder.close())
            report=recorder.report();self.assertEqual(report['mode'],'bounded-bgra-shards')
            row=report['records'][0];self.assertEqual(row['stored_sha256'],row['bgra_sha256'])
            reader=RawReader(d)
            try:
                self.assertEqual(reader.read(row),raw)
                for fields in ({'codec':'jpeg'},{'raw_bytes':63},{'stored_sha256':'0'*64}):
                    with self.assertRaises(ValueError):reader.read(dict(row,**fields))
            finally:reader.close()

    def test_only_declared_long_normal_profile_keeps_original_guards(self):
        factory=owner_tests.OwnerSplitProfileTests().owner
        for duration in (30,300):
            args=factory(endurance_seconds=duration,ticks=duration*200,paired_renderer_port=2300,
                         paired_condition='normal',paired_export_hz=20)
            validate_client(args)
            for changes in ({'hv_dependency_ms':50},{'step_ms':10},{'paired_export_hz':50},
                            {'ticks':400},{'paired_condition':'stall-crash'},{'paired_renderer_port':None}):
                bad=copy.copy(args)
                for k,v in changes.items():setattr(bad,k,v)
                with self.assertRaises(ValueError):validate_client(bad)
        for value in (True,31,301,30.0):
            with self.assertRaises(ValueError):limits(value)

    def test_lossless_shards_keep_all_frames_and_exact_rgb_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            recorder=ShardRecorder(d,12,1_000_000,capacity=8,shard_bytes=200)
            raw={frame:bytes([frame])+(bytes(range(256))*16)[1:] for frame in range(1,7)}
            try:
                for frame in range(1,7):
                    self.assertTrue(recorder.offer(dict(frame=frame,width=32,height=32),raw[frame]))
            finally:self.assertTrue(recorder.close())
            report=recorder.report();self.assertEqual(report['errors'],[]);self.assertEqual(report['overflow'],[])
            self.assertEqual(report['offered'],6);self.assertGreater(len(report['archives']),1)
            reader=RawReader(d)
            try:
                for row in report['records']:self.assertEqual(reader.read(row),raw[row['frame']])
                bad=copy.deepcopy(report['records'][0]);bad['stored_sha256']='f'*64
                with self.assertRaises(ValueError):reader.read(bad)
            finally:reader.close()

    def test_overflow_is_failure_but_original_frame_is_still_retained(self):
        with tempfile.TemporaryDirectory() as d:
            recorder=ShardRecorder(d,1,1_000_000)
            try:
                self.assertTrue(recorder.offer(dict(frame=1,width=4,height=4),bytes(64)))
                self.assertFalse(recorder.offer(dict(frame=2,width=4,height=4),bytes([1])*64))
            finally:self.assertTrue(recorder.close())
            self.assertTrue(recorder.failed())
            self.assertEqual([r['frame'] for r in recorder.report()['records']],[1,2])
            self.assertEqual(recorder.report()['overflow'],[2])

    def test_byte_limit_and_corrupt_compressed_input_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            recorder=ShardRecorder(d,2,1)
            recorder.offer(dict(frame=1,width=4,height=4),bytes(64));self.assertTrue(recorder.close())
            self.assertTrue(recorder.report()['errors']);self.assertEqual(len(recorder.report()['records']),1)
        codec=Zstd()
        with self.assertRaises(ValueError):codec.decompress(b'invalid',64)
        with self.assertRaises(ValueError):codec.decompress(codec.compress(bytes(64)),63)

    def test_seal_links_exact_shards_and_chains_all_raw_exclusions(self):
        from seal_endurance_v1 import seal
        from check_endurance_archive_v1 import checked_members
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=root/'run';folder=run/'capture/paired/renderer'
            recorder=ShardRecorder(folder,2,1_000_000)
            recorder.offer(dict(frame=1,width=4,height=4),bytes(64));self.assertTrue(recorder.close())
            raw=recorder.report()['records'];(folder/'result.json').write_text(json.dumps(dict(raw=raw)))
            prior=root/'prior.json';prior.write_text(json.dumps(dict(count=1,rgb_sha256=['a'*64])))
            bundle=root/'bundle';summary=seal(run,bundle,prior)
            self.assertEqual(summary['raw_packets'],1);self.assertEqual(summary['future_exclusion'],2)
            manifest=json.loads((bundle/'raw-manifest.json').read_text())['archives'][0]
            self.assertEqual((bundle/manifest['archive']).stat().st_ino,(folder/manifest['archive']).stat().st_ino)
            checked_members(bundle/manifest['archive'],manifest)
            manifest['members'][raw[0]['path']]['sha256']='f'*64
            with self.assertRaises(AssertionError):checked_members(bundle/manifest['archive'],manifest)

    def test_full_worker_queue_records_emergency_frame_and_reports_failure(self):
        entered=threading.Barrier(3);release=threading.Event();codec=Zstd()
        class HeldCodec:
            def compress(self,raw):
                if raw[0]<2:entered.wait(timeout=3)
                if not release.wait(3):raise RuntimeError('fixture release timeout')
                return codec.compress(raw)
        with tempfile.TemporaryDirectory() as d:
            recorder=ShardRecorder(d,8,1_000_000,capacity=1,codec=HeldCodec())
            try:
                recorder.offer(dict(frame=1,width=4,height=4),bytes(64))
                while recorder.queue.qsize():time.sleep(.001)
                recorder.offer(dict(frame=2,width=4,height=4),bytes([1])*64)
                entered.wait(timeout=3)
                self.assertTrue(recorder.offer(dict(frame=3,width=4,height=4),bytes([2])*64))
                timer=threading.Timer(.03,release.set);timer.start()
                self.assertFalse(recorder.offer(dict(frame=4,width=4,height=4),bytes([3])*64));timer.join()
            finally:release.set();self.assertTrue(recorder.close())
            self.assertEqual(recorder.report()['overflow'],[4]);self.assertEqual(len(recorder.report()['records']),4)


if __name__=='__main__':unittest.main()
