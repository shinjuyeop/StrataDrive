"""Source fingerprints follow build inputs, independent of Git staging state."""
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
fingerprint=runpy.run_path(str(ROOT/'tests/integration/runtime/check_m4_async.py'))['fingerprint']


class SourceFingerprintTest(unittest.TestCase):
    def test_deleted_tracked_input_changes_digest_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def git(*args):subprocess.run(['git',*args],cwd=root,check=True,capture_output=True)
            git('init');(root/'central').mkdir();source=root/'central/input.cpp';source.write_text('original')
            git('add','central/input.cpp')
            with patch.dict(fingerprint.__globals__,ROOT=root):
                before=fingerprint();source.unlink();deleted=fingerprint()
                self.assertNotEqual(before,deleted)
                git('add','-u');self.assertEqual(deleted,fingerprint())

    def test_untracked_cmake_module_and_changes_are_measured(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);subprocess.run(['git','init'],cwd=root,check=True,capture_output=True)
            (root/'cmake').mkdir();source=root/'cmake/CoreTargets.cmake'
            with patch.dict(fingerprint.__globals__,ROOT=root):
                empty=fingerprint();source.write_text('first');first=fingerprint()
                source.write_text('second');second=fingerprint()
                self.assertEqual(len({empty,first,second}),3)
                (root/'unrelated.log').write_text('runtime');self.assertEqual(second,fingerprint())


if __name__=='__main__':unittest.main()
