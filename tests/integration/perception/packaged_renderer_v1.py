"""Explicit stock renderer boundary; physical ownership stays in the source build."""
import hashlib
import json
from pathlib import Path
import signal
import os
import subprocess
import time

MAP = 'Carla/Maps/Town03_Opt'
XODR = 'abf177bcd9b66cfefb7ac4919f6456815f1384f4229f1343c8a6a90bbb7713c9'
VERSION = '0.9.16'


def command(editor, executable, frozen):
    executable = Path(executable).resolve()
    h = hashlib.sha256()
    with executable.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    digest = h.hexdigest()
    if (executable.name != 'CarlaUE4-Linux-Shipping'
            or frozen['external'].get(str(executable)) != digest):
        raise ValueError('explicit frozen packaged renderer executable')
    # Stock shipping ignores editor-only Strata and ExecCmds switches. Do not
    # claim the editor idle-wait or t.MaxFPS implementation is running there.
    argv = [str(executable), 'CarlaUE4', *[v for v in editor[2:]
        if not v.startswith(('-Strata', '-ExecCmds=', '-ini:'))]]
    return argv, dict(executable=str(executable), sha256=digest, server_version=VERSION,
        map=MAP, xodr_sha256=XODR, editor_idle_wait=False, viewport_fps_cap=None,
        scope='SDK rendering only; no native physics or perception authority')


PREPARE = '''import carla,hashlib,json,sys,time
deadline=int(sys.argv[1]);c=carla.Client('127.0.0.1',2300)
c.set_timeout(max(.01,(deadline-time.monotonic_ns())/1e9))
version=c.get_server_version();assert version=='0.9.16'
w=c.get_world();initial_map=w.get_map().name
if initial_map!='Carla/Maps/Town03_Opt':w=c.load_world('Town03_Opt')
road=w.get_map();digest=hashlib.sha256(road.to_opendrive().encode()).hexdigest()
assert road.name=='Carla/Maps/Town03_Opt' and digest=='abf177bcd9b66cfefb7ac4919f6456815f1384f4229f1343c8a6a90bbb7713c9'
counts={k:len(w.get_actors().filter(k)) for k in ('vehicle.*','walker.*','sensor.*')};assert not any(counts.values())
s=w.get_settings();s.synchronous_mode=True;w.apply_settings(s)
assert w.get_settings().synchronous_mode and time.monotonic_ns()<deadline
print(json.dumps(dict(version=version,world=w.id,initial_map=initial_map,map=road.name,xodr_sha256=digest,empty=counts,parked=True,completed_ns=time.monotonic_ns())))
'''

UNPARK = '''import carla,json,time
c=carla.Client('127.0.0.1',2300);c.set_timeout(2)
w=c.get_world();before=w.get_snapshot();s=w.get_settings();s.synchronous_mode=False;w.apply_settings(s)
assert not w.get_settings().synchronous_mode
print(json.dumps(dict(world=w.id,frame_before=before.frame,source_before_ns=round(before.timestamp.elapsed_seconds*1e9),completed_ns=time.monotonic_ns(),synchronous_after=False)))
'''


def prepare(python, started_ns, env):
    deadline = started_ns+180_000_000_000
    remaining = (deadline-time.monotonic_ns())/1e9
    if remaining <= 0: raise TimeoutError('target-map preparation within original180s')
    result = subprocess.run([str(python), '-c', PREPARE, str(deadline)],
        env=env, capture_output=True, text=True, check=True, timeout=remaining)
    return json.loads(result.stdout)


def stop(process, python, env):
    """End the stock synchronous wait after capture; the entire exit gets30s."""
    begin = time.monotonic_ns(); deadline = time.monotonic()+30
    result = dict(begin_wall_ns=begin, limit_seconds=30, diagnostics_enabled=False,
        scope='post-client shutdown: release synchronous wait before SIGINT')
    if process.poll() is None:
        try:
            child = subprocess.run([str(python), '-c', UNPARK], env=env,
                capture_output=True, text=True, check=True, timeout=5)
            result['unpark'] = json.loads(child.stdout)
        except (subprocess.SubprocessError, ValueError) as error:
            result['unpark_error'] = type(error).__name__
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
            try: process.wait(timeout=max(.001, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                result['forced_stop'] = True
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=10)
    result.update(end_wall_ns=time.monotonic_ns(), server_exit=process.returncode)
    return result


