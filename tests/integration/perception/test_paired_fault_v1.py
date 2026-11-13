import copy
import unittest
import os
import subprocess
import sys
import time

from paired_fault_v1 import audit_crash_progress,audit_crash_cleanup,observed_process_exit


class CrashProgressTests(unittest.TestCase):
    def setUp(self):
        self.starts=[1_000_000_000+i*5_000_000 for i in range(400)]
        self.events=[dict(action='SIGSTOP',wall_ns=2_100_000_000,physical_intervals=220,
                         observed_stopped_ns=2_105_000_000,observed_proc_state='T'),
                     dict(action='SIGCONT',wall_ns=2_355_000_000,physical_intervals=271),
                     dict(action='SIGKILL',wall_ns=2_600_000_000,physical_intervals=320)]

    def test_actual_death_and_stop_have_physical_progress(self):
        result=audit_crash_progress(self.events,self.starts,2_650_000_000)
        self.assertEqual(result['physical_intervals_while_stopped'],49)
        self.assertEqual(result['physical_intervals_after_observed_exit'],69)

    def test_exit_request_progress_cannot_substitute_for_actual_death(self):
        with self.assertRaises(ValueError):audit_crash_progress(self.events,self.starts,3_000_000_000)

    def test_signal_request_alone_does_not_establish_actual_stop(self):
        events=copy.deepcopy(self.events);events[0].pop('observed_stopped_ns')
        with self.assertRaises(ValueError):audit_crash_progress(events,self.starts,2_650_000_000)

    def test_pidfd_requires_real_child_exit(self):
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)'])
        fd=os.pidfd_open(child.pid)
        try:
            self.assertIsNone(observed_process_exit(fd))
            child.kill();child.wait(timeout=3)
            self.assertLessEqual(observed_process_exit(fd),time.monotonic_ns())
        finally:
            if child.poll() is None:child.kill();child.wait()
            os.close(fd)

    def test_dead_process_cleanup_requires_all_actors_and_post_crash_observation(self):
        record=dict(observed_exit_ns=300,skipped_actor_ids=[1,2,3,4],
                    skipped_operations=['sensor.stop','actor.destroy','world.hold'])
        audit_crash_cleanup(record,100,200,[4,3,2,1])
        for bad in (None,{**record,'observed_exit_ns':99},{**record,'observed_exit_ns':199},
                    {**record,'skipped_actor_ids':[1,2,3]},{**record,'skipped_operations':[]}):
            with self.assertRaises(ValueError):audit_crash_cleanup(bad,100,200,[1,2,3,4])


if __name__=='__main__':unittest.main()
