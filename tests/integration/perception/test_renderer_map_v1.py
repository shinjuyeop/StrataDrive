import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('renderer_map',Path(__file__).resolve().parents[3]/'tools/m10_renderer_map.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class RendererMapTests(unittest.TestCase):
    def test_exact_single_field_roundtrip_and_original_inode(self):
        original=b'[Map]\n'+module.OLD+b'\nUnrelated=retained\n'
        with tempfile.TemporaryDirectory() as folder,patch.object(module,'ORIGINAL',module.digest(original)),patch.object(module,'stopped'):
            path=Path(folder)/'DefaultEngine.ini';path.write_bytes(original);inode=path.stat().st_ino
            declaration=module.declare(path);module.install(declaration)
            self.assertEqual(path.read_bytes(),original.replace(module.OLD,module.NEW))
            with self.assertRaises(ValueError):module.install(declaration)
            report=module.restore(declaration);self.assertTrue(report['original_inode_retained'])
            self.assertEqual(path.stat().st_ino,inode);self.assertEqual(path.read_bytes(),original)
            self.assertEqual(module.restore(declaration)['status'],'PASS_ORIGINAL_CONFIG')

    def test_restore_recovers_rename_gap_but_preserves_unexpected_edit(self):
        original=module.OLD+b'\n'
        with tempfile.TemporaryDirectory() as folder,patch.object(module,'ORIGINAL',module.digest(original)),patch.object(module,'stopped'):
            path=Path(folder)/'DefaultEngine.ini';path.write_bytes(original);declaration=module.declare(path)
            backup=path.with_name(path.name+'.stratadrive-original');path.rename(backup)
            module.restore(declaration);self.assertEqual(path.read_bytes(),original)
            module.install(declaration);path.write_bytes(b'user change')
            with self.assertRaises(ValueError):module.restore(declaration)
            self.assertEqual(path.read_bytes(),b'user change');self.assertEqual(backup.read_bytes(),original)

    def test_unknown_config_duplicate_field_and_live_process_rejected(self):
        with self.assertRaises(ValueError):module.candidate(module.OLD+b'\n'+module.OLD)
        with patch.object(module.subprocess,'check_output',return_value='CarlaUE4-Linux-\n'):
            with self.assertRaises(RuntimeError):module.stopped()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'DefaultEngine.ini';path.write_bytes(b'unknown')
            with self.assertRaises(ValueError):module.declare(path)


if __name__=='__main__':unittest.main()
