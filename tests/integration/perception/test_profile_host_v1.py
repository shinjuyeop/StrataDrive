import os
from pathlib import Path
import subprocess
import sys
import unittest
from profile_host_v1 import stat,tree,GPU


class ProfileHostTests(unittest.TestCase):
    def test_owned_child_records_stable_process_and_thread_identity(self):
        child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'])
        try:
            rows=tree(child.pid)
            self.assertEqual([r['pid'] for r in rows],[child.pid])
            row=rows[0];self.assertEqual(row['start_ticks'],stat(Path(f'/proc/{child.pid}/stat'))['start_ticks'])
            self.assertIn(child.pid,[t['tid'] for t in row['threads']])
            self.assertTrue(all(t['affinity']==sorted(os.sched_getaffinity(child.pid)) for t in row['threads']))
            self.assertTrue(all(len(t['schedstat'])==3 for t in row['threads']))
            self.assertNotIn('argv',row)
        finally:child.terminate();child.wait(timeout=5)


if __name__=='__main__':unittest.main()
