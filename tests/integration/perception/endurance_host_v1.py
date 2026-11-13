"""Explicit owned-process CPU placement and nonrotating evidence spool checks."""
import json
import os
from pathlib import Path

ENV='STRATADRIVE_M10_CPU_PLAN'
ROLES=('owner','native','renderer','observer')


def validate(plan,allowed,topology):
    if set(plan)!=set(ROLES):raise ValueError('complete owned process CPU plan')
    seen=set();cores=set()
    for role in ROLES:
        cpus=plan[role]
        if not isinstance(cpus,list) or not cpus or any(type(c) is not int or c not in allowed for c in cpus):
            raise ValueError('available CPU identities')
        if len(set(cpus))!=len(cpus) or set(cpus)&seen:raise ValueError('disjoint CPU roles')
        role_cores={topology[c] for c in cpus}
        if role_cores&cores:raise ValueError('SMT siblings cannot span roles')
        seen.update(cpus);cores.update(role_cores)
    return plan


def load_profile(path,output):
    profile=json.loads(Path(path).read_text())
    if profile['schema']!='m10-endurance-host-v1':raise ValueError('host resource schema')
    allowed=os.sched_getaffinity(0);topology={}
    for cpu in allowed:
        p=Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        topology[cpu]=tuple(int((p/name).read_text()) for name in ('physical_package_id','core_id'))
    plan=validate(profile['cpus'],allowed,topology)
    device=Path('/sys/dev/block')/f'{os.major(output.stat().st_dev)}:{os.minor(output.stat().st_dev)}'
    physical=device.resolve();queue=physical/'queue/rotational'
    if not queue.exists():queue=physical.parent/'queue/rotational'
    if queue.read_text().strip()!='0':raise ValueError('declared recording spool must be nonrotating')
    result=dict(cpus=plan,spool=str(output.resolve()),block_device=str(physical),rotational=False)
    if 'owner_scheduler' in profile:
        if profile['owner_scheduler']!={'policy':'SCHED_RR','priority':8}:
            raise ValueError('bounded owner RR8 below native FIFO18')
        result['owner_scheduler']=profile['owner_scheduler']
    return result


def owner_command(resources,argv):
    return ['chrt','-r','8',*argv] if resources.get('owner_scheduler') else list(argv)


def check_owner(resources,pid):
    if resources.get('owner_scheduler'):
        if os.sched_getscheduler(pid)!=os.SCHED_RR or os.sched_getparam(pid).sched_priority!=8:
            raise ValueError('owner RR8 did not take effect')


def pin(role):
    value=os.environ.get(ENV)
    if value is None:return
    plan=json.loads(value);os.sched_setaffinity(0,plan[role])
    if set(os.sched_getaffinity(0))!=set(plan[role]):raise RuntimeError('owned CPU placement failed')


def command(role,argv):
    """Use exec-time affinity: Python preexec callbacks can deadlock after threads."""
    value=os.environ.get(ENV)
    if value is None:return list(argv)
    cpus=json.loads(value)[role]
    return ['taskset','--cpu-list',','.join(str(c) for c in cpus),*argv]
