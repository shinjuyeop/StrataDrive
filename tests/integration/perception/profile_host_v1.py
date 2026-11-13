"""Read-only bounded /proc and NVML sampling of one owned process tree."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import time


def stat(path):
    text = path.read_text(); end = text.rfind(')'); fields = text[end + 2:].split()
    return dict(comm=text[text.find('(') + 1:end], state=fields[0],
                user_ticks=int(fields[11]), system_ticks=int(fields[12]),
                start_ticks=int(fields[19]), last_cpu=int(fields[36]))


class GPU:
    class Util(ctypes.Structure):
        _fields_ = [('gpu', ctypes.c_uint), ('memory', ctypes.c_uint)]

    def __init__(self):
        self.lib = ctypes.CDLL('libnvidia-ml.so.1'); self.handle = ctypes.c_void_p()
        assert self.lib.nvmlInit_v2() == 0
        assert self.lib.nvmlDeviceGetHandleByIndex_v2(ctypes.c_uint(0), ctypes.byref(self.handle)) == 0

    def sample(self):
        result = {}; util = self.Util()
        if self.lib.nvmlDeviceGetUtilizationRates(self.handle, ctypes.byref(util)) == 0:
            result.update(gpu_percent=util.gpu, memory_percent=util.memory)
        for name, method, extra, scale in [
                ('temperature_c', 'nvmlDeviceGetTemperature', [ctypes.c_uint(0)], 1),
                ('power_w', 'nvmlDeviceGetPowerUsage', [], 1000),
                ('sm_clock_mhz', 'nvmlDeviceGetClockInfo', [ctypes.c_uint(1)], 1)]:
            value = ctypes.c_uint()
            code = getattr(self.lib, method)(self.handle, *extra, ctypes.byref(value))
            result[name] = value.value / scale if code == 0 else dict(error=code)
        return result


def tree(root_pid):
    pending = [root_pid]; seen = {os.getpid()}; processes = []
    while pending:
        pid = pending.pop()
        if pid in seen: continue
        seen.add(pid); root = Path(f'/proc/{pid}')
        try:
            item = dict(pid=pid, **stat(root/'stat'), threads=[])
            # Deliberately record command names only: no argv/environment secrets.
            for task in (root/'task').iterdir():
                try:
                    tid = int(task.name); row = dict(tid=tid, **stat(task/'stat'))
                    row['schedstat'] = [int(x) for x in (task/'schedstat').read_text().split()]
                    row['affinity'] = sorted(os.sched_getaffinity(tid))
                    item['threads'].append(row)
                    pending.extend(int(x) for x in (task/'children').read_text().split())
                except (OSError, ProcessLookupError): pass
            processes.append(item)
        except (OSError, ProcessLookupError): pass
    return processes


def host():
    values = {}
    paths = list(Path('/sys/devices/system/cpu').glob('cpu[0-9]*/cpufreq/scaling_cur_freq'))
    paths += list(Path('/sys/devices/system/cpu/cpu0/thermal_throttle').glob('*count'))
    for folder in Path('/sys/class/hwmon').glob('*'):
        try:
            if (folder/'name').read_text().strip() == 'coretemp': paths += list(folder.glob('temp*_input'))
        except OSError: pass
    for p in paths:
        try: values[str(p)] = int(p.read_text())
        except OSError: pass
    return values


def main(a):
    assert 0.25 <= a.period <= 2 and 0 < a.seconds <= 1200
    a.output.parent.mkdir(parents=True, exist_ok=True)
    initial = stat(Path(f'/proc/{a.pid}/stat'))['start_ticks']
    try: gpu = GPU(); gpu_error = None
    except Exception as error: gpu = None; gpu_error = repr(error)
    begin = time.monotonic(); cpu = time.process_time(); count = 0; costs = []
    with a.output.open('x') as stream:
        while time.monotonic() - begin < a.seconds:
            start = time.monotonic_ns()
            try:
                if stat(Path(f'/proc/{a.pid}/stat'))['start_ticks'] != initial: break
            except OSError: break
            row = dict(wall_ns=start, processes=tree(a.pid), host=host(),
                       gpu=gpu.sample() if gpu else dict(error=gpu_error))
            row['sample_ns'] = time.monotonic_ns() - start; costs.append(row['sample_ns']); count += 1
            stream.write(json.dumps(row, separators=(',', ':')) + '\n'); stream.flush()
            time.sleep(max(0, a.period - (time.monotonic_ns() - start) / 1e9))
    result = dict(samples=count, wall_seconds=time.monotonic()-begin,
                  monitor_cpu_seconds=time.process_time()-cpu, max_sample_ms=max(costs, default=0)/1e6,
                  ticks_per_second=os.sysconf('SC_CLK_TCK'), root_pid=a.pid, root_start_ticks=initial)
    result['schedstat_wait_enabled']=Path('/proc/sys/kernel/sched_schedstats').read_text().strip()=='1'
    a.output.with_suffix('.summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--pid', type=int, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--seconds', type=float, default=300)
    p.add_argument('--period', type=float, default=.5); main(p.parse_args())
