import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gc_launcher',
    Path(__file__).resolve().parents[3]/'tools/m10_start_owner_gc.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class OwnerGcLauncherTests(unittest.TestCase):
    def fixture(self, root, wrong_pid=False):
        series = root/'docs/test-plan/evidence/m10_owner_gc_v1'; series.mkdir(parents=True)
        work = root/'build/m10-owner-gc-v1'; work.mkdir(parents=True)
        python = root/'build/m10-perception/cuda-venv/bin/python'
        python.parent.mkdir(parents=True); python.symlink_to(sys.executable)
        helper = root/'tools/m10_boost_lease.py'; helper.parent.mkdir(); helper.write_text('# unchanged narrow helper\n')
        runner = series/'run-sequence.py'
        runner.write_text('import json,os,signal,time\nfrom pathlib import Path\n'
            'signal.signal(signal.SIGTERM,lambda *_:exit(0))\n'
            f'Path({str(work / "experiment-owner.json")!r}).write_text(json.dumps('
            f'dict(pid=os.getpid()+{int(wrong_pid)},uid=os.getuid())))\n'
            'while True: time.sleep(.02)\n')
        (series/'prepared.json').write_text(json.dumps(dict(status='READY_FOR_EXPLICIT_HOST_LEASE')))
        (series/'sources.json').write_text(json.dumps(dict(files={str(p.relative_to(root)):
            dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (runner, helper)})))
        return series, work, runner, helper

    def test_password_failure_does_not_start_owner_or_create_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, work, _, _ = self.fixture(root)
            with (patch.object(module.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'sudo')),
                  patch.object(module.subprocess, 'Popen') as popen):
                with self.assertRaises(subprocess.CalledProcessError): module.run(root)
                popen.assert_not_called()
            self.assertFalse((work/'experiment-owner.json').exists())
            self.assertFalse((work/'power-lease.jsonl').exists())

    def test_real_fresh_child_pid_and_lease_output_are_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, work, runner, helper = self.fixture(root)
            fake = root/'fake_lease.py'
            fake.write_text('import json,os,signal,sys\n'
                'pid=int(sys.argv[1]);os.kill(pid,0)\n'
                'print(json.dumps(dict(event="OWNER",pid=pid)),flush=True)\n'
                'os.kill(pid,signal.SIGTERM)\n')
            real_popen = subprocess.Popen; calls = []
            def popen(argv, **kwargs):
                calls.append((argv, kwargs))
                if argv[0] == '/usr/bin/sudo':
                    return real_popen([sys.executable, str(fake), argv[argv.index('--owner-pid')+1]], **kwargs)
                return real_popen(argv, **kwargs)
            with patch.object(module.subprocess, 'run') as auth, patch.object(module.subprocess, 'Popen', side_effect=popen):
                self.assertEqual(module.run(root), 0)
                auth.assert_called_once_with(['/usr/bin/sudo', '-v'], check=True)
            identity = json.loads((work/'experiment-owner.json').read_text())
            self.assertTrue(calls[0][1]['start_new_session'])
            self.assertEqual(calls[0][0], [str(root/'build/m10-perception/cuda-venv/bin/python'), str(runner)])
            self.assertEqual(calls[1][0], ['/usr/bin/sudo', '-n', '/usr/bin/python3', str(helper),
                '--owner-pid', str(identity['pid']), '--seconds', '1800'])
            self.assertEqual(json.loads((work/'power-lease.jsonl').read_text())['pid'], identity['pid'])

    def test_wrong_fresh_identity_stops_child_before_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root, wrong_pid=True)
            real_popen = subprocess.Popen
            with patch.object(module.subprocess, 'run'), patch.object(module.subprocess, 'Popen', wraps=real_popen) as popen:
                with self.assertRaisesRegex(RuntimeError, 'Fresh owner'): module.run(root)
                self.assertEqual(popen.call_count, 1)

    def test_lease_failure_stops_fresh_owner_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            real_popen = subprocess.Popen; children = []
            def popen(argv, **kwargs):
                if argv[0] == '/usr/bin/sudo':
                    argv = [sys.executable, '-c', 'raise SystemExit(5)']
                child = real_popen(argv, **kwargs); children.append(child)
                return child
            with patch.object(module.subprocess, 'run'), patch.object(module.subprocess, 'Popen', side_effect=popen):
                with self.assertRaisesRegex(RuntimeError, 'Host lease failed'): module.run(root)
            self.assertEqual(len(children), 2)
            self.assertIsNotNone(children[0].poll())
            self.assertEqual(children[1].returncode, 5)

    def test_existing_attempt_changed_source_and_root_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, work, _, helper = self.fixture(root)
            record = work/'experiment-owner.json'; record.write_text('{}')
            with self.assertRaisesRegex(RuntimeError, 'prior attempt'): module.check(root)
            record.unlink(); helper.write_text('# modified\n')
            with self.assertRaisesRegex(RuntimeError, 'Frozen source'): module.check(root)
            with patch.object(module.os, 'geteuid', return_value=0):
                with self.assertRaisesRegex(RuntimeError, 'without sudo'): module.check(root)


if __name__ == '__main__': unittest.main()
