"""Bounded read-only 20Hz host clocks/thermal/energy sampler; no process scans."""
import argparse
import json
import os
from pathlib import Path
import time
from profile_host_v1 import stat


class Counters:
    def __init__(self, paths):
        self.fds = {}
        self.unavailable = {}
        for path in sorted(set(map(str, paths))):
            fd = None
            try:
                fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
                int(os.pread(fd, 128, 0))
                self.fds[path] = fd
            except (OSError, ValueError) as error:
                if fd is not None: os.close(fd)
                self.unavailable[path] = str(error)

    def sample(self):
        values = {}; errors = {}
        for name, fd in self.fds.items():
            try: values[name] = int(os.pread(fd, 128, 0))
            except (OSError, ValueError) as error: errors[name] = str(error)
        return values, errors

    def close(self):
        for fd in self.fds.values(): os.close(fd)


def paths(extended=False):
    result = list(Path('/sys/devices/system/cpu').glob('cpu[0-9]*/cpufreq/scaling_cur_freq'))
    if extended:
        result += list(Path('/sys/devices/system/cpu').glob('cpu[0-9]*/thermal_throttle/*count'))
        result += [Path('/sys/devices/system/cpu/intel_pstate')/n for n in ('min_perf_pct','max_perf_pct','no_turbo')]
        for folder in Path('/sys/class/thermal').glob('cooling_device*'):
            try:
                # Only a kernel-maintained idle-injection state. Dell fan
                # attributes can invoke firmware and must not be polled live.
                if (folder/'type').read_text().strip()=='intel_powerclamp':result.append(folder/'cur_state')
            except OSError:pass
    else:result += list(Path('/sys/devices/system/cpu/cpu0/thermal_throttle').glob('*count'))
    for folder in Path('/sys/class/hwmon').glob('*'):
        try:
            if (folder/'name').read_text().strip() == 'coretemp': result += list(folder.glob('temp*_input'))
        except OSError: pass
    for folder in Path('/sys/class/powercap').glob('intel-rapl:*'):
        result += list(folder.glob('energy_uj'))
    return result


def main(a):
    if not .05 <= a.period <= .5 or not 0 < a.seconds <= 1200:
        raise ValueError('bounded host clock profiling')
    root = Path(f'/proc/{a.pid}/stat'); initial = stat(root)['start_ticks']
    counters = Counters(paths(a.extended)); a.output.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic(); cpu = time.process_time(); costs = []; errors = 0
    try:
        with a.output.open('x') as stream:
            while time.monotonic()-start < a.seconds:
                begin = time.monotonic_ns()
                try:
                    state=stat(root)
                    if state['start_ticks'] != initial or state['state']=='Z': break
                except OSError: break
                values, failed = counters.sample(); errors += bool(failed)
                end = time.monotonic_ns(); costs.append(end-begin)
                stream.write(json.dumps(dict(wall_ns=begin,end_ns=end,values=values,errors=failed),separators=(',',':'))+'\n')
                stream.flush()
                time.sleep(max(0,a.period-(time.monotonic_ns()-begin)/1e9))
    finally: counters.close()
    result = dict(scope='read-only sequential sysfs samples; frequency is reported scaling_cur_freq, not exact cycle-rate attribution',
        root_pid=a.pid,root_start_ticks=initial,period_seconds=a.period,samples=len(costs),extended=a.extended,
        wall_seconds=time.monotonic()-start,monitor_cpu_seconds=time.process_time()-cpu,
        max_sample_ns=max(costs,default=0),read_error_samples=errors,unavailable=counters.unavailable,
        available_paths=sorted(counters.fds))
    a.output.with_suffix('.summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True)
    p.add_argument('--seconds',type=float,default=300);p.add_argument('--period',type=float,default=.05)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--extended',action='store_true');main(p.parse_args())
