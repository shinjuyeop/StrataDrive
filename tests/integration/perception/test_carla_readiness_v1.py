import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

from carla_readiness_v1 import wait_probe


class ReadinessTests(unittest.TestCase):
    def test_hung_initial_connection_is_reaped_and_fresh_probe_can_succeed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = '''import json,os,sys,time
from pathlib import Path
p=Path(sys.argv[1])
if not p.exists():
 p.write_text(str(os.getpid()));time.sleep(60)
print(json.dumps(dict(world=7,frame=10,version='pinned')))
'''
            result = wait_probe([sys.executable, '-c', code, str(root/'first')], root/'log',
                timeout_seconds=3, attempt_seconds=.25)
            self.assertEqual(result['world'], 7)
            self.assertGreaterEqual(result['attempts'], 2)
            rows = [json.loads(line) for line in (root/'log').read_text().splitlines()]
            self.assertTrue(rows[0]['timeout'])
            with self.assertRaises(ProcessLookupError):os.kill(int((root/'first').read_text()), 0)

    def test_invalid_frame_never_becomes_ready_or_extends_total_horizon(self):
        with tempfile.TemporaryDirectory() as directory:
            begin = time.monotonic()
            with self.assertRaises(TimeoutError):
                wait_probe([sys.executable, '-c', 'print(\'{"world":7,"frame":0,"version":"pinned"}\')'],
                    Path(directory)/'log', timeout_seconds=.35, attempt_seconds=.2)
            self.assertLess(time.monotonic()-begin, 1.5)


if __name__ == '__main__':unittest.main()
