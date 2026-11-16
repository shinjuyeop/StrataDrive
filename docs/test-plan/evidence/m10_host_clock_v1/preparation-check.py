"""Post-live fixed placement preflight: synthetic model preparation, no CARLA."""
import argparse
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT/'tests/integration/perception')]
from control_shadow_capture_v1 import Capture

p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True)
a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=False)
args = SimpleNamespace(output=a.output, wall_clock=1, step_ms=5, camera_absent_control=True,
    detector=ROOT/'build/m10-resolution-v2/models/dfine-960.onnx',
    models=ROOT/'build/m10-resolution-v2/models.json',
    library=ROOT/'build/m10-source-compare-v1/native/libstrata_resize_2k_v1.so')
world = SimpleNamespace(id=1, on_tick=lambda callback: 1, remove_on_tick=lambda token: None)
before = sorted(os.sched_getaffinity(0))
capture = Capture(args)
try:
    capture.attach(world, None, None)
    assert capture.report['preparation']['state'] == 'READY'
    assert sorted(os.sched_getaffinity(0)) == before == [0, 8]
    assert capture.report['model_setup_cpus'] == [4, 5, 6, 7, 12, 13, 14, 15]
    assert len(capture.report['preparation_calls']) == 3
    assert all(r['cpus'] == capture.report['model_setup_cpus'] for r in capture.report['preparation_calls'])
    assert capture.report['preparation_thread_overrides'] == dict(cv=4, resize=4)
finally:
    capture.stop()
print(json.dumps(dict(status='PASS_SYNTHETIC_PREPARATION_ONLY',
    settled_ms=[r['elapsed_wall_ns']/1e6 for r in capture.report['preparation']['calls']],
    observer_cpus=before, model_cpus=capture.report['model_setup_cpus'],
    native_started=False, physical_receipts=0, live_stability_accepted=False)))
