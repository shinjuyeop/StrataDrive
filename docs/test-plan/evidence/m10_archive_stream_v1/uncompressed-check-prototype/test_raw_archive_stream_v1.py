import copy
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from endurance_recording_v1 import ShardRecorder
from raw_archive_stream_v1 import inspect,DigestingReader


class StreamArchiveTests(unittest.TestCase):
    def fixture(self,root,codec='bgra'):
        recorder=ShardRecorder(root,2,100000,encoding=codec)
        for n in (1,2):recorder.offer(dict(frame=n,width=4,height=4),bytes([n])*64)
        self.assertTrue(recorder.close());self.assertFalse(recorder.failed())
        report=recorder.report();return root/report['archives'][0],report['records']

    def test_full_copy_and_both_raw_encodings_are_identical(self):
        for codec in ('bgra','zstd1'):
            with self.subTest(codec=codec),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);path,rows=self.fixture(root,codec)
                with (root/'copy.tar').open('xb') as output:manifest=inspect(path,destination=output,frames=rows)
                self.assertEqual(manifest['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(path.read_bytes(),(root/'copy.tar').read_bytes())
                self.assertEqual(inspect(root/'copy.tar',manifest,frames=rows),manifest)

    def test_member_padding_and_trailing_bytes_all_remain_authenticated(self):
        for position in (0,512,1023,-1):
            with self.subTest(position=position),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);path,_=self.fixture(root);manifest=inspect(path)
                data=bytearray(path.read_bytes());data[position]^=1;path.write_bytes(data)
                with self.assertRaises((ValueError,tarfile.TarError)):inspect(path,manifest)

    def test_stored_bgra_rgb_and_inventory_checks_are_all_required(self):
        with tempfile.TemporaryDirectory() as folder:
            path,rows=self.fixture(Path(folder));manifest=inspect(path)
            for key in ('stored_sha256','bgra_sha256','rgb_sha256','raw_bytes','codec'):
                changed=copy.deepcopy(rows);changed[0][key]=0 if key=='raw_bytes' else 'wrong'
                with self.subTest(key=key),self.assertRaises(ValueError):inspect(path,manifest,frames=changed)
            for changed in (rows[:1],rows+[rows[0]],[]):
                with self.assertRaises(ValueError):inspect(path,manifest,frames=changed)
            changed=copy.deepcopy(manifest);changed['members'].pop(next(iter(changed['members'])))
            with self.assertRaises(ValueError):inspect(path,changed)

    def test_unsafe_duplicate_and_nonregular_members_rejected(self):
        for names in (['../outside'],['/absolute'],['a','a'],['link']):
            with self.subTest(names=names),tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'bad.tar'
                with tarfile.open(path,'w') as tar:
                    for name in names:
                        item=tarfile.TarInfo(name);item.size=1
                        if name=='link':item.type=tarfile.SYMTYPE;item.linkname='/outside';item.size=0
                        tar.addfile(item,io.BytesIO(b'x'))
                with self.assertRaises(ValueError):inspect(path)

    def test_mutating_original_during_read_cannot_seal(self):
        with tempfile.TemporaryDirectory() as folder:
            path,_=self.fixture(Path(folder));real=DigestingReader.read;changed=[]
            def read(reader,size=-1):
                value=real(reader,size)
                if not changed:
                    changed.append(True)
                    with path.open('ab') as stream:stream.write(b'changed')
                return value
            with patch.object(DigestingReader,'read',read),self.assertRaises(ValueError):inspect(path)

    def test_cross_device_seal_rechecks_destination_and_preserves_original(self):
        import seal_endurance_v1 as seal
        for corrupt in (False,True):
            with self.subTest(corrupt=corrupt),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);run=root/'run';images=run/'capture/paired/renderer'
                path,rows=self.fixture(images);original=path.read_bytes()
                (images/'result.json').write_text(json.dumps(dict(raw=rows)))
                prior=root/'prior.json';prior.write_text(json.dumps(dict(count=0,rgb_sha256=[])))
                real_fsync=os.fsync
                def sync(fd):
                    real_fsync(fd)
                    if corrupt:os.pwrite(fd,b'X',512)
                with patch.object(seal.os,'link',side_effect=OSError(errno.EXDEV,'fixture')),patch.object(seal.os,'fsync',sync):
                    if corrupt:
                        with self.assertRaises(ValueError):seal.seal(run,root/'bundle',prior)
                        self.assertFalse((root/'bundle/raw-manifest.json').exists())
                    else:
                        seal.seal(run,root/'bundle',prior)
                        self.assertEqual((root/'bundle'/path.name).read_bytes(),original)
                self.assertEqual(path.read_bytes(),original)


if __name__=='__main__':unittest.main()
