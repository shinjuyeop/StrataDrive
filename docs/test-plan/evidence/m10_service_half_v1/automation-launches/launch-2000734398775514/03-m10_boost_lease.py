#!/usr/bin/env python3
"""Bounded, explicit root-only Intel P-state cap for one M10 host experiment.

Only max_perf_pct is written. No shell, child command, governor, thermal policy,
minimum frequency, fan or IRQ change. The unprivileged owner can end the lease
by exiting; SIGINT/SIGTERM and timeout also restore the original cap.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import time

PSTATE=Path('/sys/devices/system/cpu/intel_pstate')


def process_identity(pid):
    folder=Path('/proc')/str(pid)
    text=(folder/'stat').read_text();fields=text[text.rfind(')')+2:].split()
    return dict(uid=folder.stat().st_uid,start_ticks=int(fields[19]),state=fields[0])


def alive(pid, identity):
    try:
        current=process_identity(pid)
        return current['state']!='Z' and all(current[k]==identity[k] for k in ('uid','start_ticks'))
    except (OSError,ValueError):return False


def emit(event, **values):
    print(json.dumps(dict(event=event,wall_ns=time.monotonic_ns(),**values)),flush=True)


def lease(read, write, owner_alive, stopped, seconds, *, clock=time.monotonic,
          pause=time.sleep, report=emit):
    """Dependency-injected state machine; tests never write host settings."""
    if not 1<=seconds<=1800:raise ValueError('lease must be at most1800s')
    original={name:read(name) for name in ('status','min_perf_pct','max_perf_pct','no_turbo')}
    if original['status']!='active' or original['max_perf_pct']!='100' or original['no_turbo']!='0':
        raise ValueError('requires original active Intel P-state, max100 and turbo enabled')
    if not 0<=int(original['min_perf_pct'])<=70:raise ValueError('minimum exceeds proposed cap')
    if not owner_alive():raise ValueError('experiment owner is not alive')
    deadline=clock()+seconds;applied=False;reason='ERROR'
    try:
        # Mark before writing, so read-back or later observation errors still
        # attempt restoration after a possibly successful write.
        applied=True;write('max_perf_pct','70')
        if read('max_perf_pct')!='70':raise RuntimeError('cap read-back failed')
        report('APPLIED',original=original,maximum_percent=70,seconds=seconds)
        while clock()<deadline:
            if stopped():reason='SIGNAL';break
            if not owner_alive():reason='OWNER_EXIT';break
            if read('max_perf_pct')!='70':
                reason='EXTERNAL_CHANGE';raise RuntimeError('cap changed externally; stop experiment')
            if read('min_perf_pct')!=original['min_perf_pct'] or read('no_turbo')!=original['no_turbo']:
                reason='EXTERNAL_CHANGE';raise RuntimeError('another host power setting changed')
            pause(min(.25,max(0,deadline-clock())))
        else:reason='TIME_LIMIT'
    finally:
        if applied:
            current=read('max_perf_pct')
            if current=='70':
                write('max_perf_pct',original['max_perf_pct'])
                if read('max_perf_pct')!=original['max_perf_pct']:raise RuntimeError('restoration read-back failed')
                report('RESTORED',reason=reason,maximum_percent=int(original['max_perf_pct']))
            elif current==original['max_perf_pct']:
                report('ALREADY_RESTORED',reason=reason,maximum_percent=int(current))
            else:
                report('RESTORE_CONFLICT',reason=reason,current=current,original=original['max_perf_pct'])
                raise RuntimeError('external cap preserved; manual review required')
    return reason


def main(a):
    if os.geteuid()!=0:raise PermissionError('explicit sudo execution required')
    uid=int(os.environ['SUDO_UID'])
    if uid==0 or a.owner_pid<=1:raise ValueError('non-root experiment owner required')
    identity=process_identity(a.owner_pid)
    if identity['uid']!=uid or identity['state']=='Z':raise ValueError('owner must belong to the invoking user')
    if Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver').read_text().strip()!='intel_pstate':
        raise ValueError('unsupported driver')
    fd=os.open('/run/stratadrive-m10-boost.lock',os.O_CREAT|os.O_RDWR|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(fd)
        if info.st_uid!=0 or not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ValueError('lease lock identity')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        stop=[]
        for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,lambda *_:stop.append(True))
        emit('OWNER',pid=a.owner_pid,uid=uid,start_ticks=identity['start_ticks'])
        def write(name,value):
            if name!='max_perf_pct':raise ValueError('only maximum cap may be written')
            (PSTATE/name).write_text(value+'\n')
        lease(lambda name:(PSTATE/name).read_text().strip(),write,
              lambda:alive(a.owner_pid,identity),lambda:bool(stop),a.seconds)
    finally:os.close(fd)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--owner-pid',type=int,required=True)
    p.add_argument('--seconds',type=int,default=1800,help='maximum1800; bounded again before any write')
    main(p.parse_args())
