import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from control_shadow_capture_v1 import Capture


class CaptureSetupTests(unittest.TestCase):
    def test_failure_keeps_preparation_reason_and_restores_observer(self):
        worker = SimpleNamespace(prepare=lambda: True, wait_prepared=lambda timeout: False,
            preparation_status=lambda: dict(state='FAILED', error='settled probe deadline'))
        backend = SimpleNamespace(detector=SimpleNamespace(session=SimpleNamespace(
            get_providers=lambda: ['CUDAExecutionProvider'])), resize=SimpleNamespace(threads=4))
        with tempfile.TemporaryDirectory() as folder:
            args = SimpleNamespace(output=Path(folder), wall_clock=1, detector='x', models='y', library='z')
            capture = Capture(args)
            before = os.sched_getaffinity(0)
            try:
                with patch('control_shadow_capture_v1.StagedKernelBackend', return_value=backend), \
                     patch('control_shadow_capture_v1.IpcWorldPerception', return_value=worker), \
                     patch('control_shadow_capture_v1.configure_pipeline_threads') as configure:
                    with self.assertRaisesRegex(RuntimeError, 'settled probe deadline'):
                        capture.attach(SimpleNamespace(id=1), None, None)
                    configure.assert_called_once()
                    self.assertEqual(capture.report['preparation']['state'], 'FAILED')
                    self.assertEqual(os.sched_getaffinity(0), before)
                    self.assertIsNone(capture.recorder)
            finally:
                capture.tx.close(); capture.rx.close()
