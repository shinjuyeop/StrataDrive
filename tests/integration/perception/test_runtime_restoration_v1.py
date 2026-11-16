import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from runtime_restoration_v1 import restore_component, sha


class RestorationTests(unittest.TestCase):
    def test_restore_once_then_skip_exact_original(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'runtime'
            path.write_bytes(b'original'); original = sha(path)
            path.write_bytes(b'candidate'); candidate = sha(path)
            def restore():
                path.write_bytes(b'original')
                return 0
            call = Mock(side_effect=restore)
            self.assertEqual(restore_component(path, original, candidate, call)['status'], 'RESTORED')
            self.assertEqual(restore_component(path, original, candidate, call)['status'], 'ALREADY_ORIGINAL')
            call.assert_called_once()

    def test_unknown_identity_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'runtime'; path.write_bytes(b'unknown'); call = Mock()
            with self.assertRaises(ValueError): restore_component(path, 'original', 'candidate', call)
            call.assert_not_called(); self.assertEqual(path.read_bytes(), b'unknown')

    def test_success_exit_cannot_hide_bad_restoration(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'runtime'; path.write_bytes(b'candidate')
            with self.assertRaises(RuntimeError): restore_component(path, 'original', sha(path), lambda: 0)
