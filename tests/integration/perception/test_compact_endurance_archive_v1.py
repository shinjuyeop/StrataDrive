import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from compact_endurance_archive_v1 import compact,file_identity
from check_endurance_archive_v1 import checked_members
from endurance_recording_v1 import RawReader


class ArchiveCompaction(unittest.TestCase):
    def fixture(self,root):
        raw=bytes(range(256))*16;path=root/'raw-camera-000.tar'
        with tarfile.open(path,'w') as tar:
            info=tarfile.TarInfo('1.bgra');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
        sha=hashlib.sha256(raw).hexdigest()
        row=dict(archive=path.name,original='raw/'+path.name,**file_identity(path),
                 members={'1.bgra':dict(bytes=len(raw),sha256=sha)})
        manifest=root/'raw-manifest.json';manifest.write_text(json.dumps(dict(archives=[row])))
        return path,raw,sha,manifest

    def test_roundtrip_preserves_full_tar_and_raw_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,raw,sha,manifest=self.fixture(root);before=manifest.read_bytes()
            run=root/'checked';(run/'raw').mkdir(parents=True);link=run/'raw'/path.name;link.symlink_to(path)
            result=compact(root,run);self.assertEqual(result['status'],'PASS');self.assertFalse(path.exists())
            self.assertEqual((root/'raw-manifest-uncompressed.json').read_bytes(),before)
            archived=json.loads(manifest.read_text())['archives'][0];checked_members(root/archived['archive'],archived)
            self.assertTrue(link.is_file());reader=RawReader(link.parent)
            try:self.assertEqual(reader.read(dict(archive=path.name,path='1.bgra',codec='bgra',raw_bytes=len(raw),stored_bytes=len(raw),stored_sha256=sha)),raw)
            finally:reader.close()
            with self.assertRaisesRegex(ValueError,'already declared'):compact(root,run)

    def test_corrupt_original_leaves_original_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,raw,sha,manifest=self.fixture(root);before=manifest.read_bytes()
            with path.open('ab') as out:out.write(b'changed')
            with self.assertRaisesRegex(ValueError,'original archive identity'):compact(root)
            self.assertTrue(path.exists());self.assertEqual(manifest.read_bytes(),before)
            self.assertFalse(path.with_suffix('.tar.gz').exists())

    def test_foreign_link_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,raw,sha,manifest=self.fixture(root)
            run=root/'checked';(run/'raw').mkdir(parents=True);link=run/'raw'/path.name
            foreign=root/'foreign';foreign.write_bytes(b'keep');link.symlink_to(foreign)
            with self.assertRaisesRegex(ValueError,'link identity'):compact(root,run)
            self.assertEqual(link.read_bytes(),b'keep');self.assertTrue(path.exists())


if __name__=='__main__':unittest.main()
