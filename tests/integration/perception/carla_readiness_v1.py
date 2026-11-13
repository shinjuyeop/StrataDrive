"""Finite fresh SDK probes: a pre-start connection cannot poison all retries."""
import json
from pathlib import Path
import subprocess
import time

PROBE = '''import carla,json,sys
c=carla.Client('127.0.0.1',int(sys.argv[1]));c.set_timeout(2)
w=c.get_world();s=w.get_snapshot()
if s.frame<=0 or s.id!=w.id:sys.exit(1)
print(json.dumps(dict(world=w.id,frame=s.frame,version=c.get_server_version())))
'''


def wait_probe(command, output, *, env=None, timeout_seconds=180, attempt_seconds=5):
    if not 0 < attempt_seconds <= timeout_seconds <= 180:
        raise ValueError('bounded readiness deadlines')
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    with Path(output).open('x') as log:
        while time.monotonic() < deadline:
            attempts += 1
            row = dict(attempt=attempts, begin_ns=time.monotonic_ns())
            ready = None
            try:
                child = subprocess.run(command, env=env, capture_output=True, text=True,
                    timeout=min(attempt_seconds, max(.001, deadline-time.monotonic())))
                row.update(exit=child.returncode, stdout=child.stdout[-4096:], stderr=child.stderr[-4096:])
                if child.returncode == 0:
                    value = json.loads(child.stdout)
                    if (type(value) is dict and type(value.get('world')) is int and value['world'] > 0
                            and type(value.get('frame')) is int and value['frame'] > 0
                            and type(value.get('version')) is str and value['version']):
                        ready = value
            except subprocess.TimeoutExpired:
                row['timeout'] = True  # subprocess.run has killed and reaped this probe.
            except (ValueError, TypeError):
                row['invalid_response'] = True
            row['end_ns'] = time.monotonic_ns()
            log.write(json.dumps(row)+'\n');log.flush()
            if ready is not None:
                return dict(**ready, attempts=attempts)
            time.sleep(min(.1, max(0, deadline-time.monotonic())))
    raise TimeoutError('original180s readiness horizon exhausted')


def wait_ready(python, port, output, env=None):
    return wait_probe([str(python), '-c', PROBE, str(port)], output, env=env)
