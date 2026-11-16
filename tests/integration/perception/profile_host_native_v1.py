"""Read-only native-CPU interrupt and selected kernel-thread observations."""
import argparse
import json
from pathlib import Path
import time
from profile_host_v1 import stat


def read_interrupts(path='/proc/interrupts', limit=262144):
    # procfs seq_files may return a short read before EOF (typically one page).
    # Read the complete snapshot on a fresh open; never treat one pread as EOF.
    with open(path, 'rb') as stream:
        data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('bounded interrupt read truncated')
    return data.decode()


def interrupts(text, cpus):
    lines=text.splitlines();header=lines[0].split()
    positions=[header.index('CPU'+str(cpu)) for cpu in cpus]
    rows={}
    for line in lines[1:]:
        if ':' not in line:continue
        name,rest=line.split(':',1);fields=rest.split()
        if len(fields)<len(header) or not all(v.isdigit() for v in fields[:len(header)]):continue
        rows[name.strip()]=dict(counts=[int(fields[i]) for i in positions],label=' '.join(fields[len(header):]))
    return rows


class NativeHost:
    def __init__(self, cpus):
        self.cpus=cpus
        wanted={'irq/9-acpi'}|{'idle_inject/'+str(cpu) for cpu in cpus}
        self.threads={};self.errors={}
        for path in Path('/proc').iterdir():
            if not path.name.isdigit():continue
            try:
                name=(path/'comm').read_text().strip()
                if name in wanted:
                    row=stat(path/'stat');self.threads[int(path.name)]=dict(comm=name,start_ticks=row['start_ticks'])
            except OSError:pass

    def sample(self):
        data=read_interrupts()
        rows=[]
        for pid,identity in self.threads.items():
            path=Path('/proc')/str(pid)
            try:
                row=stat(path/'stat')
                if row['start_ticks']!=identity['start_ticks'] or row['comm']!=identity['comm']:
                    raise ValueError('kernel thread identity changed')
                rows.append(dict(pid=pid,**row,schedstat=[int(v) for v in (path/'schedstat').read_text().split()]))
            except (OSError,ValueError) as error:self.errors[str(pid)]=str(error)
        return dict(interrupts=interrupts(data,self.cpus),kernel_threads=rows)

    def close(self):pass


def main(a):
    if a.period!=.05 or not 0<a.seconds<=1200:raise ValueError('bounded50ms observation')
    root=Path(f'/proc/{a.pid}/stat');initial=stat(root)['start_ticks'];observer=NativeHost([1,9])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();cpu=time.process_time();costs=[]
    try:
        with a.output.open('x') as stream:
            while time.monotonic()-start<a.seconds:
                begin=time.monotonic_ns()
                try:
                    state=stat(root)
                    if state['start_ticks']!=initial or state['state']=='Z':break
                except OSError:break
                row=observer.sample();row['wall_ns']=begin;row['end_ns']=time.monotonic_ns()
                costs.append(row['end_ns']-begin)
                stream.write(json.dumps(row,separators=(',',':'))+'\n');stream.flush()
                time.sleep(max(0,a.period-(time.monotonic_ns()-begin)/1e9))
    finally:observer.close()
    result=dict(scope='50ms sequential counters on CPUs1,9; no causal kernel scheduling trace',
        cpus=[1,9],root_pid=a.pid,root_start_ticks=initial,period_seconds=a.period,samples=len(costs),
        wall_seconds=time.monotonic()-start,monitor_cpu_seconds=time.process_time()-cpu,
        max_sample_ns=max(costs,default=0),kernel_thread_identities=observer.threads,errors=observer.errors,
        schedstat_wait_enabled=Path('/proc/sys/kernel/sched_schedstats').read_text().strip()=='1')
    a.output.with_suffix('.summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=float,default=300)
    p.add_argument('--period',type=float,default=.05);main(p.parse_args())
