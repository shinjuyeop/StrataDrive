"""Check Linux stat field offsets, including names containing parentheses."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from profile_host_v1 import stat, tree


class StatTest(unittest.TestCase):
    def test_owned_child_records_stable_process_and_thread_identity(self):
        child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'])
        try:
            rows=tree(child.pid)
            self.assertEqual([r['pid'] for r in rows],[child.pid])
            row=rows[0];self.assertEqual(row['start_ticks'],stat(Path(f'/proc/{child.pid}/stat'))['start_ticks'])
            self.assertIn(child.pid,[t['tid'] for t in row['threads']])
            self.assertTrue(all(t['affinity']==sorted(os.sched_getaffinity(child.pid)) for t in row['threads']))
            self.assertTrue(all(len(t['schedstat'])==3 for t in row['threads']))
            for thread in row['threads']:
                self.assertEqual(thread['scheduling_policy'], os.sched_getscheduler(thread['tid']))
                self.assertEqual(thread['rt_priority'], os.sched_getparam(thread['tid']).sched_priority)
            self.assertNotIn('argv',row)
        finally:child.terminate();child.wait(timeout=5)

    def test_original_counters_and_scheduler_identity(self):
        # /proc/<pid>/stat fields 3..52; fields39/40/41 are CPU/RT priority/policy.
        fields = [str(i) for i in range(3, 53)]
        fields[0] = 'S'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'stat'
            path.write_text('123 (worker (native)) '+' '.join(fields)+'\n')
            self.assertEqual(stat(path), dict(comm='worker (native)', state='S',
                minor_faults=10, major_faults=12, user_ticks=14, system_ticks=15,
                start_ticks=22, last_cpu=39, rt_priority=40, scheduling_policy=41))


if __name__ == '__main__':
    unittest.main()
