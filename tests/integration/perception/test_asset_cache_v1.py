import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

path=Path(__file__).resolve().parents[3]/'tools/m10_asset_cache.py'
spec=importlib.util.spec_from_file_location('asset_cache',path)
cache=importlib.util.module_from_spec(spec);spec.loader.exec_module(cache)


class AssetCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);self.source=root/'source';self.source.mkdir()
        self.asset=self.source/'mesh.uasset';self.asset.write_bytes(b'original mesh bytes')
        self.ddc=self.source/'derived.udd';self.ddc.write_bytes(b'cached data')
        self.inventory=root/'inventory.json';self.inventory.write_text(json.dumps(dict(files={str(self.asset):self.asset.stat().st_size,str(self.ddc):self.ddc.stat().st_size})))
        self.target=root/'cache'
        for name,value in [('ALLOWED',(self.source,)),('RESERVE_BYTES',0)]:
            guard=patch.object(cache,name,value);guard.start();self.addCleanup(guard.stop)
        for name in ('stopped',):
            guard=patch.object(cache,name);guard.start();self.addCleanup(guard.stop)
        guard=patch.object(cache.os,'sync');guard.start();self.addCleanup(guard.stop)
        self.original_stat=self.asset.stat();self.original=self.asset.read_bytes()

    def test_round_trip_restores_same_inode_bytes_and_mode(self):
        plan=cache.stage(self.inventory,self.target)
        self.assertFalse(self.asset.is_symlink())
        cache.install(self.target);self.assertTrue(self.asset.is_symlink());self.assertEqual(self.asset.read_bytes(),self.original)
        self.assertEqual(cache.validate_installed(self.target)['status'],'PASS_ASSET_BYTES_AND_STORAGE_LINKS')
        result=cache.restore(self.target)
        self.assertFalse(self.asset.is_symlink());self.assertEqual(self.asset.read_bytes(),self.original)
        self.assertEqual(self.asset.stat().st_ino,self.original_stat.st_ino)
        self.assertEqual(self.asset.stat().st_mode,self.original_stat.st_mode)
        self.assertEqual(result['modified_cache_files'],[])
        self.assertEqual(cache.restore(self.target)['restored'],0)

    def test_interrupted_rename_before_symlink_is_recoverable(self):
        plan=cache.stage(self.inventory,self.target)
        item=next(i for i in plan['entries'] if i['path']==str(self.asset))
        self.asset.rename(item['backup'])
        cache.restore(self.target)
        self.assertEqual(self.asset.read_bytes(),self.original)
        self.assertEqual(self.asset.stat().st_ino,self.original_stat.st_ino)

    def test_changed_cache_is_preserved_and_original_is_restored(self):
        cache.stage(self.inventory,self.target);cache.install(self.target)
        target=self.asset.resolve();target.write_bytes(b'changed candidate')
        with self.assertRaisesRegex(ValueError,'immutable asset'):cache.validate_installed(self.target)
        result=cache.restore(self.target)
        self.assertIn(str(target),result['modified_cache_files'])
        self.assertEqual(target.read_bytes(),b'changed candidate')
        self.assertEqual(self.asset.read_bytes(),self.original)

    def test_unrelated_replacement_is_not_overwritten(self):
        cache.stage(self.inventory,self.target);cache.install(self.target)
        self.asset.unlink();self.asset.write_bytes(b'user replacement')
        with self.assertRaisesRegex(ValueError,'unexpected replacement'):cache.restore(self.target)
        self.assertEqual(self.asset.read_bytes(),b'user replacement')

    def test_changed_copy_cannot_start_partial_install(self):
        plan=cache.stage(self.inventory,self.target);Path(plan['entries'][-1]['target']).write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError,'bytes changed'):cache.install(self.target)
        self.assertFalse(self.asset.is_symlink());self.assertFalse(self.ddc.is_symlink())

    def test_bad_plan_path_and_space_limit_fail_before_mutation(self):
        with patch.object(cache,'RESERVE_BYTES',2**63):
            with self.assertRaisesRegex(ValueError,'budget'):cache.stage(self.inventory,self.target)
        plan=cache.stage(self.inventory,self.target);plan['entries'][0]['backup']=str(self.source/'unrelated')
        cache.save(self.target/'plan.json',plan)
        with self.assertRaisesRegex(ValueError,'mapping'):cache.install(self.target)
        self.assertFalse(self.asset.is_symlink())

    def test_engine_may_update_derived_cache_but_original_is_retained(self):
        cache.stage(self.inventory,self.target);cache.install(self.target)
        self.ddc.write_bytes(b'new derived result')
        result=cache.validate_installed(self.target)
        self.assertEqual(len(result['mutable_derived_cache_changes']),1)
        cache.restore(self.target)
        self.assertEqual(self.ddc.read_bytes(),b'cached data')


if __name__=='__main__':unittest.main()
