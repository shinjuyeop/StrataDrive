"""One-second Linux process-tree resource observations; no control scheduling."""
import os
from pathlib import Path
import time


def resources(roots):
    records=[];seen=set();pending=[(role,pid) for role,pid in roots.items()]
    while pending:
        role,pid=pending.pop()
        if pid in seen:continue
        seen.add(pid)
        try:
            proc=Path(f'/proc/{pid}');stat=(proc/'stat').read_text();fields=stat[stat.rfind(')')+2:].split()
            records.append(dict(role=role,pid=pid,start_ticks=int(fields[19]),
                user_ticks=int(fields[11]),system_ticks=int(fields[12]),rss_bytes=int(fields[21])*os.sysconf('SC_PAGE_SIZE'),
                affinity=sorted(os.sched_getaffinity(pid)),scheduler=os.sched_getscheduler(pid),
                priority=os.sched_getparam(pid).sched_priority))
            children=(proc/f'task/{pid}/children').read_text().split()
            pending.extend((role+'/child',int(child)) for child in children)
        except (FileNotFoundError,ProcessLookupError):pass
    mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    free={}
    for path in ('/d','/tmp'):
        v=os.statvfs(path);free[path]=v.f_bavail*v.f_frsize
    host={}
    for path in list(Path('/sys/devices/system/cpu').glob('cpu[0-9]*/cpufreq/scaling_cur_freq'))+list(Path('/sys/devices/system/cpu/cpu0/thermal_throttle').glob('*count')):
        try:host[str(path)]=int(path.read_text())
        except OSError:pass
    for folder in Path('/sys/class/hwmon').glob('hwmon*'):
        try:
            if (folder/'name').read_text().strip()=='coretemp':
                for path in folder.glob('temp*_input'):host[str(path)]=int(path.read_text())
        except OSError:pass
    return dict(wall_ns=time.monotonic_ns(),processes=records,free_bytes=free,host_telemetry=host,
        available_ram_bytes=int(mem['MemAvailable'].split()[0])*1024)


def endurance_runtime(freeze,manifest,source,engine,profile):
    import json
    from run_carla_control_shadow_v1 import sha
    root=Path(__file__).resolve().parents[3]
    frozen=json.loads(freeze.read_text());build=json.loads(manifest.read_text())
    if frozen['external'].get(str(manifest.resolve()))!=sha(manifest):raise ValueError('unfrozen endurance build')
    if build['schema']!='m10-endurance-build-v1' or build['original_sha256']!=profile['baseline_module_sha256']:
        raise ValueError('endurance baseline identity')
    prior=json.loads((root/'docs/test-plan/evidence/m10_fence_compare_v1/build-02/manifest.json').read_text())
    if prior['installed']['executable']['path']!=str((engine/'Engine/Binaries/Linux/UE4Editor').resolve()):
        raise ValueError('endurance engine path')
    for name,item in prior['installed'].items():
        expected=build['module_sha256'] if name=='module' else item['original_sha256']
        if sha(item['path'])!=expected or frozen['external'].get(item['path'])!=expected:
            raise ValueError('endurance runtime identity '+name)
    module='Unreal/CarlaUE4/Plugins/Carla/Binaries/Linux/libUE4Editor-Carla.so'
    if build['module_path']!=str((source/module).resolve()):raise ValueError('endurance module path')
    expected=dict(profile['external_files']);expected[module]=build['module_sha256'];return expected
