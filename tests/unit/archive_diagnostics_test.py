import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest import mock
import zlib

spec=importlib.util.spec_from_file_location('archive_diagnostics',Path(__file__).resolve().parents[2]/'tools/archive_diagnostics.py')
archive=importlib.util.module_from_spec(spec);spec.loader.exec_module(archive)


def seal(raw):return raw+struct.pack('<I',zlib.crc32(raw))


class ArchiveDiagnostics(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.store=self.root/'store';self.store.mkdir(mode=0o700);self.output=self.root/'saved.tar.gz'
        payload=b'\0\1\0' # opaque framing fixture; native semantic replay is explicitly not claimed
        frame=seal(b'SDDEVT\1\0'+struct.pack('<QI',1,len(payload))+payload)
        files={'manifest':seal(b'SDDMAN\1\0'+struct.pack('<QIIIII',123,512,64,128,64,4)),
               'commit':seal(b'SDDCMT\1\0'+struct.pack('<QQ',1,len(frame))),'journal':frame,'lock':b''}
        for name,data in files.items():
            p=self.store/name;p.write_bytes(data);p.chmod(0o600)

    def test_archive_and_restore_preserve_every_byte_and_capacity(self):
        before={p.name:p.read_bytes() for p in self.store.iterdir()};metadata=archive.archive_store(self.store,self.output)
        self.assertEqual(metadata['entries'],1);self.assertEqual(metadata['event_capacity'],512);self.assertFalse(metadata['semantic_replay_checked'])
        restored=self.root/'restored';self.assertEqual(archive.restore(self.output,restored),metadata)
        self.assertEqual({p.name:p.read_bytes() for p in restored.iterdir()},before)
        self.assertEqual({p.name:p.read_bytes() for p in self.store.iterdir()},before)
        self.assertEqual(self.output.stat().st_mode&0o777,0o600)

    def test_live_writer_lock_prevents_archive(self):
        with (self.store/'lock').open('rb') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):archive.archive_store(self.store,self.output)
        self.assertFalse(self.output.exists())

    def test_uncommitted_tail_and_incomplete_marker_survive_restore(self):
        with (self.store/'journal').open('ab') as f:f.write(b'uncommitted suffix')
        p=self.store/'incomplete';p.write_bytes(b'gap\n');p.chmod(0o600)
        metadata=archive.archive_store(self.store,self.output);self.assertEqual(metadata['uncommitted_bytes'],18);self.assertTrue(metadata['incomplete'])
        destination=self.root/'restored';archive.restore(self.output,destination)
        self.assertEqual((destination/'journal').read_bytes(),(self.store/'journal').read_bytes());self.assertTrue((destination/'incomplete').exists())

    def test_existing_archive_and_restore_destination_are_never_replaced(self):
        archive.archive_store(self.store,self.output);before=self.output.read_bytes()
        with self.assertRaises(FileExistsError):archive.archive_store(self.store,self.output)
        with self.assertRaises(FileExistsError):archive.restore(self.output,self.store)
        self.assertEqual(self.output.read_bytes(),before)

    def test_corrupt_committed_prefix_is_rejected_without_touching_source(self):
        p=self.store/'journal';data=p.read_bytes();p.write_bytes(data[:-1]+bytes([data[-1]^1]));before=p.read_bytes()
        with self.assertRaises(ValueError):archive.archive_store(self.store,self.output)
        self.assertEqual(p.read_bytes(),before);self.assertFalse(self.output.exists())

    def test_symlink_hardlink_and_public_file_are_rejected(self):
        p=self.store/'lock';p.unlink();p.symlink_to(self.store/'journal')
        with self.assertRaises(OSError):archive.archive_store(self.store,self.output)
        p.unlink();os.link(self.store/'journal',p)
        with self.assertRaises(ValueError):archive.archive_store(self.store,self.output)
        p.unlink();p.touch(mode=0o644)
        with self.assertRaises(ValueError):archive.archive_store(self.store,self.output)

    def test_forged_hash_and_unsafe_archive_path_are_rejected(self):
        archive.archive_store(self.store,self.output);metadata,files=archive.verify(self.output)
        for name in ('journal','../journal'):
            altered=self.root/('bad-'+str(len(name))+'.tar.gz')
            with tarfile.open(altered,'w:gz') as tar:
                for member,data in [('archive.json',json.dumps(metadata).encode()),*files.items()]:
                    if member=='journal':member=name;data+=b'forged'
                    info=tarfile.TarInfo(member);info.size=len(data);tar.addfile(info,io.BytesIO(data))
            with self.assertRaises(ValueError):archive.verify(altered)

    def test_unknown_file_is_not_silently_omitted(self):
        p=self.store/'unexpected';p.touch(mode=0o600)
        with self.assertRaises(ValueError):archive.archive_store(self.store,self.output)

    def test_pending_intent_with_no_data_tail_survives_archive_and_restore(self):
        p=self.store/'pending';p.write_bytes(b'interrupted intent');p.chmod(0o600)
        metadata=archive.archive_store(self.store,self.output)
        self.assertEqual(metadata['uncommitted_bytes'],0)
        restored=self.root/'restored';archive.restore(self.output,restored)
        self.assertEqual((restored/'pending').read_bytes(),p.read_bytes())

    def test_archive_sync_failure_preserves_source_and_publishes_only_verified_bytes(self):
        before={p.name:p.read_bytes() for p in self.store.iterdir()};real_sync=os.fsync
        for boundary in range(2):
            destination=self.root/f'archive-{boundary}.tar.gz';calls=0
            def fail(fd):
                nonlocal calls
                point=calls;calls+=1
                if point==boundary:raise OSError(5,'injected fsync failure')
                real_sync(fd)
            with mock.patch.object(archive.os,'fsync',side_effect=fail):
                with self.assertRaises(OSError):archive.archive_store(self.store,destination)
            self.assertEqual({p.name:p.read_bytes() for p in self.store.iterdir()},before)
            self.assertEqual(list(self.root.glob('.diagnostic-archive-*')),[])
            if destination.exists():self.assertEqual(archive.verify(destination)[1],before)

    def test_interrupted_restore_never_exposes_a_lock_before_all_content_is_synced(self):
        archive.archive_store(self.store,self.output);_,files=archive.verify(self.output);real_sync=os.fsync
        for boundary in range(9):
            destination=self.root/f'restored-{boundary}';calls=0
            def fail(fd):
                nonlocal calls
                point=calls;calls+=1
                if point==boundary:raise OSError(28,'injected storage failure')
                real_sync(fd)
            with mock.patch.object(archive.os,'fsync',side_effect=fail):
                with self.assertRaises(OSError):archive.restore(self.output,destination)
            if (destination/'lock').exists():
                self.assertGreaterEqual(boundary,6)
                self.assertEqual({p.name:p.read_bytes() for p in destination.iterdir()},files)
            else:self.assertLess(boundary,6)
            # Preserve the interrupted destination; no automatic repair/reuse.
            with self.assertRaises(FileExistsError):archive.restore(self.output,destination)


if __name__=='__main__':unittest.main()
