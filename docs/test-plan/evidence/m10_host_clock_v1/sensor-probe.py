"""One declared native-only scheduler observation; not physical acceptance."""
import csv
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
SERIES = Path(__file__).resolve().parent
OUT = SERIES/'sensor-probe-01'
SCRIPTS = ROOT/'tests/integration/perception'
sys.path.insert(0, str(SCRIPTS))
from profile_host_v1 import host, tree
from profile_host_native_v1 import NativeHost
from profile_host_clock_v1 import Counters, paths
from audit_watch_timing_v1 import validate

BINARY = ROOT/'build/m10-watch-timing-v1/native-postfix/tests/integration/carla/m7_1g/m7_carla_wall_owner'
SCENARIO = ROOT/'tests/integration/carla/scenarios/m10_endurance_hold_v1.txt'


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert sorted(os.sched_getaffinity(0)) == [0, 8], 'observer placement'
    OUT.mkdir(exist_ok=False)
    # The executable identity is part of the pre-live external/runtime freeze.
    identities = {str(p.relative_to(ROOT)): sha(p) for p in (
        BINARY, SCENARIO, Path(__file__), SERIES/'sensor-probe-protocol.md', SCRIPTS/'profile_host_v1.py', SCRIPTS/'profile_host_native_v1.py', SCRIPTS/'profile_host_clock_v1.py', SCRIPTS/'audit_watch_timing_v1.py')}
    preflight = []
    until = time.monotonic()+180
    while True:
        temperatures = [v/1000 for k, v in host().items() if '/temp' in k]
        temperature = max(temperatures)
        preflight.append(dict(wall_ns=time.monotonic_ns(), max_cpu_c=temperature))
        if temperature <= 70 or time.monotonic() >= until:
            break
        time.sleep(2)
    write(OUT/'declaration.json', dict(scope='native-only5s + four declared sensor reads; no physical acceptance',
        identities=identities, preflight=preflight, observer_affinity=[0, 8],
        status='READY' if temperature <= 70 else 'NOT_RUN_PREFLIGHT'))
    if temperature > 70:
        return
    tx, rx = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    tx.setblocking(False); rx.setblocking(False)
    command = ['taskset', '-c', '1,9', 'chrt', '-f', '18', str(BINARY),
        str(OUT/'bridge'), str(OUT/'native'), str(SCENARIO), '5', '30',
        '--perception-shadow', f'{rx.fileno()}:1:2', '--endurance-seconds', '30', '--profile-state-path']
    write(OUT/'command.json', command)
    observer=NativeHost([1,9])
    extra=list(Path('/sys/devices/system/cpu').glob('cpu[0-9]*/thermal_throttle/*count'))
    extra += [Path('/sys/devices/system/cpu/intel_pstate')/n for n in ('min_perf_pct','max_perf_pct','no_turbo')]
    for folder in Path('/sys/class/thermal').glob('cooling_device*'):
        try:
            if 'dell' not in (folder/'type').read_text().lower():extra.append(folder/'cur_state')
        except OSError:pass
    counters= Counters(paths()+extra)
    hwmon={}
    for folder in Path('/sys/class/hwmon').glob('*'):
        try:hwmon[(folder/'name').read_text().strip()]=folder
        except OSError:pass
    queries=[(1,hwmon['coretemp']/'temp1_input')]+[(i+1,hwmon['dell_smm']/f'fan{i}_input') for i in (1,2,3)]
    queries_done=[]
    begin = time.monotonic_ns(); cpu = time.process_time_ns()
    initial = None; samples = []; error = None; code = None
    with (OUT/'stderr.log').open('w') as log:
        process = subprocess.Popen(command, pass_fds=(rx.fileno(),), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=log, text=True)
        rx.close()
        try:
            process.stdin.write('START 99 1000000000 1 1 00000000-0000-4000-8000-000000000001\n')
            process.stdin.flush()
            while True:
                stamp = time.monotonic_ns()
                if initial and stamp >= initial['initial']+5_000_000_000:
                    break
                if not initial and stamp-begin > 10_000_000_000:
                    raise RuntimeError('native initialization timeout')
                if initial and queries and stamp>=initial['initial']+queries[0][0]*1_000_000_000:
                    offset,path=queries.pop(0);before=time.monotonic_ns();thread_cpu=time.thread_time_ns()
                    value=path.read_text().strip()
                    cpu_cost=time.thread_time_ns()-thread_cpu;after=time.monotonic_ns()
                    queries_done.append(dict(offset_seconds=offset,path=str(path),value=value,begin_ns=before,end_ns=after,thread_cpu_ns=cpu_cost))
                values,failed=counters.sample()
                row = dict(wall_ns=stamp, processes=tree(process.pid) if len(samples)%10==0 else [], host=values, counter_errors=failed, native_host=observer.sample())
                row['end_ns'] = time.monotonic_ns(); samples.append(row)
                if select.select([process.stdout], [], [], 0)[0]:
                    line = process.stdout.readline()
                    if not line:
                        raise RuntimeError('native exited before STOP')
                    initial = json.loads(line)
                    assert initial['model_step_ns'] == 5_000_000 and initial['hv_dependency_ns'] == 30_000_000
                time.sleep(max(0, .05-(time.monotonic_ns()-stamp)/1e9))
            process.stdin.write('STOP\n'); process.stdin.flush(); process.stdin.close()
            code = process.wait(timeout=5)
            assert code == 0, 'native exit status'
        except Exception as failure:
            error = repr(failure)
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=5)
            tx.close();observer.close();counters.close()
    with (OUT/'observations.jsonl').open('x') as stream:
        for row in samples:
            stream.write(json.dumps(row, separators=(',', ':'))+'\n')
    result = dict(status='RECORDED' if error is None else 'ERROR', error=error, exit=code,
        wall_seconds=(time.monotonic_ns()-begin)/1e9, observer_cpu_seconds=(time.process_time_ns()-cpu)/1e9,
        samples=len(samples), initial=initial, sensor_queries=queries_done, counter_unavailable=counters.unavailable, native_perception_accepted=False, physical_receipts=0,
        scope='single unloaded native-only observation; not CARLA or a stability acceptance')
    if initial and (OUT/'native.json').exists():
        meta = json.loads((OUT/'native.json').read_text()); result['native'] = meta
        candidates = {t['tid'] for row in samples if row['end_ns'] < initial['initial']
            for p in row['processes'] if p['pid'] == process.pid for t in p['threads'] if t['tid'] != process.pid}
        result['monitor_tid_candidates'] = sorted(candidates)
        if len(candidates) == 1:
            tid = next(iter(candidates))
            result['monitor_identity_samples'] = [dict(wall_ns=row['wall_ns'], **t) for row in samples
                for p in row['processes'] for t in p['threads'] if t['tid'] == tid]
        with (OUT/'native.csv').open() as stream:
            native = list(csv.DictReader(stream))
        stop = int(native[-1]['now']) if native else initial['initial']
        with (OUT/'native-wall.csv').open() as stream:
            watch = [{k:int(v) for k,v in r.items()} for r in csv.DictReader(stream)]
        eligible = [r for r in watch if r['owner'] == 9 and r['deadline_ns'] <= stop]
        late = [r for r in eligible if not r['end_ns'] or r['end_ns'] > r['deadline_ns']]
        delays = sorted(r['start_ns']-r['release_ns'] for r in eligible if r['start_ns'])
        result['monitor_slots'] = dict(eligible=len(eligible), missing=sum(not r['end_ns'] for r in eligible),
            late=sum(r['end_ns'] > r['deadline_ns'] for r in eligible), violations=late,
            max_wake_delay_ns=max(delays, default=None), median_wake_delay_ns=delays[len(delays)//2] if delays else None)
    if initial and (OUT/'native-monitor.csv').exists():
        def rows(name):
            with (OUT/name).open() as stream:return [{k:int(v) for k,v in r.items()} for r in csv.DictReader(stream)]
        result['profile_integrity']=validate(json.loads((OUT/'native-monitor.json').read_text()),
            rows('native-monitor.csv'),rows('native-wall.csv'),initial['initial'],35_000_000_000)
    write(OUT/'result.json', result)
    print(json.dumps({k:v for k,v in result.items() if k != 'monitor_identity_samples'}))


if __name__ == '__main__':
    main()
