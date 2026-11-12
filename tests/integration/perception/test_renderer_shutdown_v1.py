from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

from renderer_shutdown_v1 import allow_shutdown_tracer, capture, read_bounded, shutdown


class RendererShutdownTests(unittest.TestCase):
    def child(self, code, *, trace=False):
        process = subprocess.Popen([sys.executable,'-u','-c',code], stdout=subprocess.PIPE,
                                   start_new_session=True, preexec_fn=allow_shutdown_tracer if trace else None)
        self.addCleanup(self.stop, process)
        self.assertEqual(process.stdout.readline(), b'ready\n')
        return process

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.kill(); process.wait(timeout=2)
        process.stdout.close()

    def test_real_owned_child_allows_bounded_debugger_without_host_policy_change(self):
        policy = Path('/proc/sys/kernel/yama/ptrace_scope').read_bytes()
        process = self.child('import time; print("ready"); time.sleep(30)', trace=True)
        with tempfile.TemporaryDirectory() as work:
            result = capture(process, Path(work)/'diagnostic', 8)
            self.assertEqual(result['status'], 'CAPTURED', (Path(work)/'diagnostic/gdb.log').read_text())
            self.assertLessEqual(result['log_bytes'], 8*1024*1024)
            self.assertIsNone(process.poll())
        self.assertEqual(Path('/proc/sys/kernel/yama/ptrace_scope').read_bytes(), policy)

    def test_clean_exit_does_not_attach_and_retains_return_code(self):
        process = self.child('import signal,time,sys; signal.signal(signal.SIGINT,lambda *a:sys.exit(130)); print("ready"); time.sleep(30)')
        with tempfile.TemporaryDirectory() as work:
            result = shutdown(process, work, diagnostics=True, limit_seconds=2, diagnostic_after_seconds=.2)
            self.assertEqual(result['server_exit'],130)
            self.assertNotIn('diagnostic', result)
            self.assertNotIn('forced_stop', result)

    def test_ignoring_child_is_still_a_forced_failure_at_original_deadline(self):
        process = self.child('import signal,time; signal.signal(signal.SIGINT,signal.SIG_IGN); print("ready"); time.sleep(30)')
        with tempfile.TemporaryDirectory() as work:
            result = shutdown(process, work, diagnostics=False, limit_seconds=.2, diagnostic_after_seconds=.1)
            self.assertTrue(result['forced_stop'])
            self.assertEqual(result['server_exit'], -signal.SIGKILL)
            self.assertLess(result['end_wall_ns']-result['begin_wall_ns'], 2_000_000_000)

    def test_dead_pid_and_oversize_proc_input_are_not_silently_accepted(self):
        process = self.child('print("ready")'); process.wait(timeout=2)
        with tempfile.TemporaryDirectory() as work:
            self.assertEqual(capture(process,Path(work)/'dead')['status'],'ALREADY_EXITED')
            path=Path(work)/'large';path.write_text('12345')
            self.assertIn('error',read_bounded(path,4))
            self.assertEqual(read_bounded(path,5)['text'],'12345')


if __name__ == '__main__': unittest.main()
