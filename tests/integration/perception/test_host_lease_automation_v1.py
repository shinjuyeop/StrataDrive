import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tools'))
import m10_install_host_lease as installer
import m10_start_owner_gc_unattended as launcher
import test_owner_gc_launcher as manual_tests


class InstallerTests(unittest.TestCase):
    def test_installed_payload_changes_only_interpreter(self):
        source = ROOT/'tools/m10_boost_lease.py'
        data = installer.payload(source)
        self.assertEqual(data.split(b'\n', 1)[0], b'#!/usr/bin/python3 -I')
        self.assertEqual(data.split(b'\n', 1)[1], source.read_bytes().split(b'\n', 1)[1])
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder)/'helper.py'; bad.write_bytes(source.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError, 'fixed version'):
                installer.payload(bad)

    def test_rule_is_one_command_and_parses_with_actual_visudo(self):
        rule = installer.policy_bytes('alswoghd')
        self.assertEqual(rule.splitlines()[1],
            b'alswoghd ALL=(root) NOPASSWD: NOSETENV: /usr/local/sbin/stratadrive-m10-boost-lease')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'rule'; path.write_bytes(rule)
            result = subprocess.run(['/usr/sbin/visudo', '-c', '-f', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        for username in ('a\nroot ALL=(ALL) ALL', 'user,root', '#0', 'ALL'):
            with self.assertRaises(ValueError): installer.policy_bytes(username)

    def test_isolated_helper_ignores_working_directory_and_pythonpath(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder); marker = path/'IMPORTED'
            (path/'argparse.py').write_text(f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("injected")\n')
            helper = path/'helper'; helper.write_bytes(installer.payload(ROOT/'tools/m10_boost_lease.py')); helper.chmod(0o755)
            result = subprocess.run([str(helper), '--help'], cwd=path,
                env=dict(os.environ, PYTHONPATH=str(path)), capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(marker.exists())

    def test_existing_file_checks_owner_mode_links_and_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'helper'; path.write_bytes(b'fixed')
            good = dict(st_mode=stat.S_IFREG|0o755, st_uid=0, st_gid=0, st_nlink=1)
            with patch.object(Path, 'lstat', return_value=SimpleNamespace(**good)):
                self.assertTrue(installer.existing_matches(path, b'fixed', 0o755))
                with self.assertRaises(ValueError): installer.existing_matches(path, b'changed', 0o755)
            for field, value in [('st_mode', stat.S_IFLNK|0o755), ('st_mode', stat.S_IFREG|0o777),
                                 ('st_uid', 1000), ('st_gid', 1000), ('st_nlink', 2)]:
                with self.subTest(field=field, value=value), patch.object(Path, 'lstat', return_value=SimpleNamespace(**dict(good, **{field:value}))):
                    with self.assertRaises(ValueError): installer.existing_matches(path, b'fixed', 0o755)

    def test_writable_or_symlink_parent_is_rejected(self):
        for mode in (stat.S_IFDIR|0o777, stat.S_IFLNK|0o755):
            with patch.object(Path, 'lstat', return_value=SimpleNamespace(st_mode=mode, st_uid=0)):
                with self.assertRaises(ValueError): installer.trusted_directory(Path('/test'))

    def test_create_does_not_replace_and_validation_failure_leaves_no_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(installer.os, 'fchown'):
            path = Path(folder)/'target'
            with self.assertRaises(RuntimeError):
                installer.create_file(path, b'fixed', 0o440,
                    lambda _: (_ for _ in ()).throw(RuntimeError('syntax')))
            self.assertFalse(path.exists()); self.assertEqual(list(Path(folder).iterdir()), [])
            path.write_bytes(b'other')
            with self.assertRaises(FileExistsError): installer.create_file(path, b'fixed', 0o440)
            self.assertEqual(path.read_bytes(), b'other')

    def test_failed_policy_probe_rolls_back_only_new_files(self):
        for helper_exists in (False, True):
            with self.subTest(helper_exists=helper_exists), tempfile.TemporaryDirectory() as folder:
                helper, policy = Path(folder)/'helper', Path(folder)/'rule'
                if helper_exists: helper.write_bytes(b'fixed')
                def matches(path, data, mode):
                    if not path.exists(): return False
                    if path.read_bytes() != data: raise ValueError('different')
                    return True
                with (patch.object(installer, 'HELPER', helper), patch.object(installer, 'POLICY', policy),
                      patch.object(installer, 'trusted_directory'), patch.object(installer, 'existing_matches', side_effect=matches),
                      patch.object(installer.os, 'fchown'), patch.object(installer, 'visudo'),
                      patch.object(installer, 'check_passwordless', side_effect=RuntimeError('not authorized'))):
                    with self.assertRaisesRegex(RuntimeError, 'not authorized'):
                        installer.install(SimpleNamespace(pw_name='alswoghd'), b'fixed')
                self.assertFalse(policy.exists()); self.assertEqual(helper.exists(), helper_exists)

    def test_passwordless_probe_drops_privilege_and_ignores_cache(self):
        user = SimpleNamespace(pw_uid=1000, pw_gid=1000)
        with patch.object(installer.subprocess, 'run') as run:
            installer.check_passwordless(user)
        self.assertEqual(run.call_args.args[0], ['/usr/bin/sudo', '-n', '-k', str(installer.HELPER), '--help'])
        self.assertEqual(run.call_args.kwargs['user'], 1000)
        self.assertEqual(run.call_args.kwargs['extra_groups'], [])
        self.assertEqual(run.call_args.kwargs['cwd'], '/')

    def test_install_is_idempotent_and_removal_revokes_rule_first(self):
        with tempfile.TemporaryDirectory() as folder:
            helper, policy = Path(folder)/'helper', Path(folder)/'rule'
            def matches(path, data, mode):
                if not path.exists(): return False
                if path.read_bytes() != data: raise ValueError('different')
                return True
            with (patch.object(installer, 'HELPER', helper), patch.object(installer, 'POLICY', policy),
                  patch.object(installer, 'trusted_directory'), patch.object(installer, 'existing_matches', side_effect=matches),
                  patch.object(installer.os, 'fchown'), patch.object(installer, 'visudo'),
                  patch.object(installer, 'check_passwordless')):
                user = SimpleNamespace(pw_name='alswoghd')
                installer.install(user, b'fixed')
                before = (helper.stat().st_ino, policy.stat().st_ino)
                installer.install(user, b'fixed')
                self.assertEqual(before, (helper.stat().st_ino, policy.stat().st_ino))
                order = []; original_unlink = Path.unlink
                def unlink(path, *args, **kwargs):
                    order.append(path); return original_unlink(path, *args, **kwargs)
                with patch.object(Path, 'unlink', autospec=True, side_effect=unlink):
                    installer.remove(user, b'fixed')
                self.assertEqual(order, [policy, helper])
                self.assertFalse(helper.exists()); self.assertFalse(policy.exists())


class UnattendedTests(unittest.TestCase):
    def fixture(self, root, wrong_pid=False):
        series, work, runner, source = manual_tests.OwnerGcLauncherTests().fixture(root, wrong_pid)
        for name in ('m10_start_owner_gc.py', 'm10_install_host_lease.py'):
            (root/'tools'/name).write_bytes((ROOT/'tools'/name).read_bytes())
        manifest = json.loads((series/'sources.json').read_text())
        name = 'tools/m10_start_owner_gc.py'
        manifest['files'][name] = dict(sha256=hashlib.sha256((root/name).read_bytes()).hexdigest())
        (series/'sources.json').write_text(json.dumps(manifest))
        helper = root/'installed-helper'; helper.write_bytes(b'reviewed fixed helper')
        return series, work, runner, helper

    def test_helper_preflight_checks_root_copy_before_noninteractive_sudo(self):
        with tempfile.TemporaryDirectory() as folder:
            source = ROOT/'tools/m10_boost_lease.py'
            helper = Path(folder)/'helper'; helper.write_bytes(installer.payload(source))
            info = SimpleNamespace(st_mode=stat.S_IFREG|0o755, st_uid=0, st_gid=0, st_nlink=1)
            with (patch.object(launcher, 'HELPER', helper), patch.object(launcher, 'trusted_directory'),
                  patch.object(Path, 'lstat', return_value=info), patch.object(launcher.subprocess, 'run') as run):
                launcher.helper_check(source)
                self.assertEqual(run.call_args.args[0], ['/usr/bin/sudo', '-n', '-k', str(helper), '--help'])
                run.reset_mock(); helper.write_bytes(b'modified')
                with self.assertRaisesRegex(ValueError, 'differs'): launcher.helper_check(source)
                run.assert_not_called()
                helper.write_bytes(installer.payload(source)); info.st_uid = 1000
                with self.assertRaisesRegex(ValueError, 'differs'): launcher.helper_check(source)
                run.assert_not_called()

    def test_missing_policy_fails_before_asset_preparation_or_owner(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); series, work, _, _ = self.fixture(root)
            with (patch.object(launcher, 'helper_check', side_effect=RuntimeError('install once')),
                  patch.object(launcher.subprocess, 'run') as run, patch.object(launcher.subprocess, 'Popen') as popen):
                with self.assertRaisesRegex(RuntimeError, 'install once'): launcher.run(root)
                run.assert_not_called(); popen.assert_not_called()
            self.assertFalse((series/'automation-launches').exists())

    def test_real_fresh_owner_only_uses_installed_helper_and_records_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); series, work, runner, helper = self.fixture(root)
            fake = root/'fake-lease.py'
            fake.write_text('import json,os,signal,sys\npid=int(sys.argv[1]);os.kill(pid,0)\n'
                'print(json.dumps(dict(event="OWNER",pid=pid)),flush=True)\nos.kill(pid,signal.SIGTERM)\n')
            real_popen = subprocess.Popen; calls = []
            def popen(argv, **kwargs):
                calls.append(argv)
                if argv[0] == '/usr/bin/sudo':
                    return real_popen([sys.executable, str(fake), argv[argv.index('--owner-pid')+1]], **kwargs)
                return real_popen(argv, **kwargs)
            with (patch.object(launcher, 'HELPER', helper), patch.object(launcher, 'helper_check'),
                  patch.object(launcher.subprocess, 'run') as prepare,
                  patch.object(launcher.subprocess, 'Popen', side_effect=popen)):
                self.assertEqual(launcher.run(root), 0)
                self.assertEqual(prepare.call_count, 1)
            owner = json.loads((work/'experiment-owner.json').read_text())
            self.assertEqual(calls[1], ['/usr/bin/sudo', '-n', '-k', str(helper), '--owner-pid', str(owner['pid']), '--seconds', '1800'])
            self.assertEqual(json.loads((work/'power-lease.jsonl').read_text())['pid'], owner['pid'])
            attempt = next((series/'automation-launches').glob('launch-*')); record = json.loads((attempt/'invocation.json').read_text())
            self.assertEqual(record['status'], 'OWNER_EXITED_CHECK_ORIGINAL_DISPOSITION')
            for value in record['source_files'].values():
                self.assertEqual(hashlib.sha256((attempt/value['retained']).read_bytes()).hexdigest(), value['sha256'])

    def test_changed_policy_after_preparation_does_not_start_owner(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); series, work, _, helper = self.fixture(root)
            with (patch.object(launcher, 'HELPER', helper),
                  patch.object(launcher, 'helper_check', side_effect=[None, RuntimeError('policy revoked')]),
                  patch.object(launcher.subprocess, 'run'), patch.object(launcher.subprocess, 'Popen') as popen):
                with self.assertRaisesRegex(RuntimeError, 'policy revoked'): launcher.run(root)
                popen.assert_not_called()
            record = json.loads(next(series.glob('automation-launches/launch-*/invocation.json')).read_text())
            self.assertEqual(record['status'], 'ERROR')

    def test_wrong_owner_identity_stops_child_before_sudo(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); _, _, _, helper = self.fixture(root, wrong_pid=True)
            real_popen = subprocess.Popen; children = []
            def popen(*args, **kwargs):
                child = real_popen(*args, **kwargs); children.append(child); return child
            with (patch.object(launcher, 'HELPER', helper), patch.object(launcher, 'helper_check'),
                  patch.object(launcher.subprocess, 'run'), patch.object(launcher.subprocess, 'Popen', side_effect=popen)):
                with self.assertRaisesRegex(RuntimeError, 'Fresh owner'): launcher.run(root)
            self.assertEqual(len(children), 1); self.assertIsNotNone(children[0].poll())

    def test_lease_failure_stops_owner_and_preserves_attempt_without_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); series, _, _, helper = self.fixture(root)
            real_popen = subprocess.Popen; children = []
            def popen(argv, **kwargs):
                if argv[0] == '/usr/bin/sudo': argv = [sys.executable, '-c', 'raise SystemExit(5)']
                child = real_popen(argv, **kwargs); children.append(child); return child
            with (patch.object(launcher, 'HELPER', helper), patch.object(launcher, 'helper_check'),
                  patch.object(launcher.subprocess, 'run'), patch.object(launcher.subprocess, 'Popen', side_effect=popen)):
                with self.assertRaisesRegex(RuntimeError, 'Host lease failed'): launcher.run(root)
            self.assertEqual(len(children), 2)
            self.assertTrue(all(child.poll() is not None for child in children))
            record = json.loads(next(series.glob('automation-launches/launch-*/invocation.json')).read_text())
            self.assertEqual(record['status'], 'ERROR')


if __name__ == '__main__':
    unittest.main()
