#!/usr/bin/env python3
"""Sample owned runtime schedstat counters; retain coverage gaps and blocked kernel tracing."""
import argparse
import csv
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
# multiprocessing "spawn" must be able to import the worker by its real module name.
sys.path.insert(0,str(ROOT/'tests/integration/runtime'))
import check_timing as timing


def covering_delta(samples, begin_ns, end_ns):
    """Cover the entire event, without allocating an aggregate counter delta to a specific wakeup."""
    before = [s for s in samples if s['end_ns'] <= begin_ns]
    after = [s for s in samples if s['begin_ns'] >= end_ns]
    if not before or not after:
        return dict(coverage='incomplete', attribution='unknown')
    left, right = before[-1], after[0]
    delta = {name: right[name]-left[name] for name in ('cpu_ns','queue_ns','slices','voluntary','involuntary')}
    if any(v < 0 for v in delta.values()):
        return dict(coverage='counter_regressed', attribution='unknown')
    return dict(coverage='complete', sample_begin_ns=left['begin_ns'], sample_end_ns=right['end_ns'], delta=delta,
                boundary_extra_ns=(begin_ns-left['begin_ns'])+(right['end_ns']-end_ns),
                attribution='runqueue wait observed in covering interval' if delta['queue_ns'] else 'no runqueue increment observed; timer/IRQ/VM cause unproven')


def correlate(directory, samples):
    metadata = json.loads((directory/'run.json').read_text())
    by_tid = {}
    for sample in samples:
        by_tid.setdefault(sample['tid'], []).append(sample)
    events = []
    for role, filename in dict(rx='rx-jobs.csv', monitor='monitor-cycles.csv', plant_fixture='plant-cycles.csv').items():
        rows = timing.multirate_rows(directory/filename)
        for i, row in enumerate(rows):
            if not row.get('guarded',1) or row['ran'] and not row['detected_ns'] and row['end_ns'] <= row['deadline_ns']:
                continue
            following = row if row['ran'] else next((r for r in rows[i+1:] if r['ran']), None)
            tid = metadata['threads'][role]['tid']
            event = dict(role=role,slot=i,tid=tid,release_ns=row['release_ns'],deadline_ns=row['deadline_ns'],ran=row['ran'])
            if following:
                event['next_start_ns'] = following['start_ns']
                end = following['end_ns'] if row['ran'] else following['start_ns']
                event['counters'] = covering_delta(by_tid.get(tid,[]), row['release_ns'], max(row['release_ns'],end))
                if role != 'rx':
                    event['requested_wake_delay_ns'] = following['start_ns']-following['wake_target_ns']
            else:
                event['counters'] = dict(coverage='incomplete',attribution='unknown')
            events.append(event)
    return events


def snapshot(pid):
    records = []
    try: tasks = list((Path('/proc')/str(pid)/'task').iterdir())
    except FileNotFoundError: return records
    for task in tasks:
        begin = time.monotonic_ns()
        try:
            cpu, queue, slices = map(int,(task/'schedstat').read_text().split())
            status = dict(line.split(':',1) for line in (task/'status').read_text().splitlines() if ':' in line)
        except (FileNotFoundError,ProcessLookupError): continue
        records.append(dict(begin_ns=begin,end_ns=time.monotonic_ns(),tid=int(task.name),cpu_ns=cpu,queue_ns=queue,slices=slices,
                            voluntary=int(status['voluntary_ctxt_switches']),involuntary=int(status['nonvoluntary_ctxt_switches'])))
    return records


def preemption_configuration(text):
    options = dict(line.split('=', 1) for line in text.splitlines() if line.startswith('CONFIG_') and '=' in line)
    return dict(preempt_rt=options.get('CONFIG_PREEMPT_RT') == 'y',
                preempt_dynamic=options.get('CONFIG_PREEMPT_DYNAMIC') == 'y',
                sched_info=options.get('CONFIG_SCHED_INFO') == 'y')


def fifo_probe(priority):
    """Try only in a disposable child, restoring it before reporting; never promote the observer."""
    if not os.sched_get_priority_min(os.SCHED_FIFO) <= priority <= os.sched_get_priority_max(os.SCHED_FIFO):
        raise ValueError('FIFO priority outside supported range')
    code = '''import json, os, sys
result = dict(requested_priority=int(sys.argv[1]), verdict='BLOCKED')
before = (os.sched_getscheduler(0), os.sched_getparam(0))
try:
    os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(result['requested_priority']))
    result.update(observed_policy=os.sched_getscheduler(0), observed_priority=os.sched_getparam(0).sched_priority)
    if result['observed_policy'] == os.SCHED_FIFO and result['observed_priority'] == result['requested_priority']:
        result['verdict'] = 'AVAILABLE'
except OSError as error:
    result.update(errno=error.errno, error=str(error))
finally:
    try:
        os.sched_setscheduler(0, before[0], before[1])
        result['restored'] = (os.sched_getscheduler(0), os.sched_getparam(0)) == before
    except OSError as error:
        result.update(verdict='BLOCKED', restore_error=str(error), restored=False)
print(json.dumps(result))
'''
    try:
        probe = subprocess.run([sys.executable, '-c', code, str(priority)], capture_output=True, text=True, timeout=3, check=False)
        result = json.loads(probe.stdout)
        result.update(exitcode=probe.returncode, stderr=probe.stderr)
        if probe.returncode != 0 or not result.get('restored'):
            result['verdict'] = 'BLOCKED'
        return result
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return dict(requested_priority=priority, verdict='UNKNOWN', error=str(error))


def capabilities(fifo_priority=1):
    result = dict(kernel=os.uname().release,monotonic_clock='CLOCK_MONOTONIC',schedstat_sampling='intrusive diagnostic, not a performance baseline')
    config = Path('/boot')/('config-'+os.uname().release)
    try:
        result['preemption'] = dict(source=str(config), **preemption_configuration(config.read_text()))
        result['sched_info_enabled'] = result['preemption']['sched_info']
    except OSError as error:
        result.update(preemption=dict(preempt_rt=None, error=str(error)), sched_info_enabled=None)
    result.update(machine=os.uname().machine, fifo_probe=fifo_probe(fifo_priority),
                  rlimit_rtprio=list(resource.getrlimit(resource.RLIMIT_RTPRIO)),
                  caller_policy=os.sched_getscheduler(0), caller_priority=os.sched_getparam(0).sched_priority,
                  allowed_cpus=sorted(os.sched_getaffinity(0)),
                  scope='capability observation only; no RT workload, latency acceptance or system setting changes')
    for key, path in dict(kernel_realtime='/sys/kernel/realtime', rt_runtime_us='/proc/sys/kernel/sched_rt_runtime_us',
                          rt_period_us='/proc/sys/kernel/sched_rt_period_us', perf_event_paranoid='/proc/sys/kernel/perf_event_paranoid').items():
        try: result[key] = Path(path).read_text().strip()
        except OSError as error: result[key] = dict(error=str(error))
    try:
        result['tracefs'] = sorted(p.name for p in Path('/sys/kernel/tracing').iterdir())
    except OSError as error:
        result['tracefs_error'] = str(error)
    try:
        probe = subprocess.run(['perf','stat','-e','context-switches','--','true'],capture_output=True,text=True,check=False,timeout=3)
        result.update(perf_probe_exit=probe.returncode,perf_probe_stderr=probe.stderr)
    except (OSError, subprocess.SubprocessError) as error:
        result['perf_probe_error']=str(error)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir',type=Path,default=ROOT/'build/m1-angle')
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--owner-cpus',default='1,1,1,1,0,2,0')
    parser.add_argument('--observer-cpu',type=int,default=3)
    parser.add_argument('--load-cpu',type=int)
    parser.add_argument('--owner-fifo',help='optional seven-owner FIFO map; the observer stays SCHED_OTHER')
    parser.add_argument('--repetitions',type=int,default=3)
    parser.add_argument('--probe-only',action='store_true',help='record RT/kernel/trace capabilities without running a workload or creating vCAN')
    parser.add_argument('--fifo-priority',type=int,default=1,help='priority for the short disposable capability probe, not a runtime scheduling configuration')
    args = parser.parse_args()
    timing.require(1 <= args.repetitions <= 10,'repetitions must be 1..10')
    timing.require(1 <= args.fifo_priority <= 99,'FIFO probe priority must be 1..99')
    if args.probe_only:
        timing.require(args.load_cpu is None,'probe-only cannot start a load worker')
        timing.require(args.owner_fifo is None,'probe-only cannot configure a runtime')
        output = args.output_dir.resolve(); output.mkdir(parents=True,exist_ok=False)
        result = capabilities(args.fifo_priority)
        result.update(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                      working_tree=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines(),
                      source_sha256=timing.sha256(Path(__file__)))
        (output/'capabilities.json').write_text(json.dumps(result,indent=2)+'\n')
        (output/'artifact-sha256.json').write_text(json.dumps({'capabilities.json':timing.sha256(output/'capabilities.json')},indent=2)+'\n')
        print('Capability probe recorded; FIFO',result['fifo_probe']['verdict'],'; workload NOT RUN')
        return
    allowed = os.sched_getaffinity(0)
    owners = timing.parse_owner_cpus(args.owner_cpus)
    priorities = timing.parse_fifo_priorities(args.owner_fifo) if args.owner_fifo is not None else None
    timing.require(set(owners.values()) <= allowed and args.observer_cpu in allowed,'CPU outside allowed mask')
    timing.require(args.load_cpu is None or args.load_cpu in allowed,'load CPU outside allowed mask')
    os.sched_setaffinity(0,{args.observer_cpu})
    output = args.output_dir.resolve(); output.mkdir(parents=True,exist_ok=False)
    build = args.build_dir.resolve(); binary = build/'actuator_demo'
    # Keep original inherited CPU set in the runtime. The observer alone stays pinned.
    environment = timing.environment(build,binary,'multirate')
    environment.update(diagnostic=capabilities(args.fifo_priority),requested_owner_cpus=owners,requested_owner_fifo=priorities,observer_cpu=args.observer_cpu,load_cpu=args.load_cpu,
                       runtime_inherited_allowed_cpus=sorted(allowed),runtime_cpu_topology=timing.cpu_topology(sorted(allowed)))
    (output/'environment.json').write_text(json.dumps(environment,indent=2)+'\n')
    interface='diagnostic0'; reports=[]
    subprocess.run(['ip','link','add','dev',interface,'type','vcan'],check=True)
    try:
        subprocess.run(['ip','link','set','dev',interface,'mtu','72','up'],check=True)
        for index in range(args.repetitions):
            directory = output/f'normal-{index+1}'
            process = None; load = None; samples = []
            report = dict(directory=str(directory),contract_verdict='FAIL')
            with (output/f'normal-{index+1}.log').open('w') as log:
                try:
                    if args.load_cpu is not None: load=timing.CpuLoad(args.load_cpu)
                    command = [str(binary),'multirate-runtime','normal',interface,str(directory),'owner-cpus='+args.owner_cpus]
                    if priorities is not None: command += ['owner-fifo='+args.owner_fifo]
                    process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,preexec_fn=lambda:os.sched_setaffinity(0,allowed))
                    limit = time.monotonic()+10
                    while process.poll() is None:
                        samples.extend(snapshot(process.pid))
                        if time.monotonic()>limit: process.kill(); raise RuntimeError('diagnostic runtime timeout')
                        time.sleep(.001)
                    timing.require(process.returncode==0,'runtime process failed')
                    report['observations']=timing.observe_jobs(directory)
                    timing.validate_placement(report['observations']['metadata'],owners,priorities)
                    timing.validate_scheduling(report['observations']['metadata'],priorities)
                    report['control_verdict']='PASS'
                    try: timing.analyze(directory); report['contract_verdict']='PASS'
                    except (AssertionError,KeyError,ValueError) as error: report['contract_error']=str(error)
                    report['events']=correlate(directory,samples)
                finally:
                    if process is not None:
                        if process.poll() is None: process.kill()
                        process.wait()
                    if load is not None:
                        report['load']=load.finish()
                        meta=report['observations']['metadata']
                        report['load_metrics']=timing.validate_load(report['load'],args.load_cpu,meta['enable_ns'],meta['stop_ns'])
            sample_path=output/f'normal-{index+1}-schedstat.csv'
            with sample_path.open('w') as stream:
                writer=csv.DictWriter(stream,fieldnames=('begin_ns','end_ns','tid','cpu_ns','queue_ns','slices','voluntary','involuntary'))
                writer.writeheader(); writer.writerows(samples)
            report['sample_rows']=len(samples); reports.append(report)
            print(directory.name,report['contract_verdict'],len(report['events']),'miss events',flush=True)
    finally:
        subprocess.run(['ip','link','delete','dev',interface],check=True)
    summary=dict(runs=reports,kernel_trace='NOT RUN: see capability probe',root_cause='not isolated; counters cover sampled intervals, not individual scheduler wakeups')
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (output/'artifact-sha256.json').write_text(json.dumps({str(p.relative_to(output)):timing.sha256(p) for p in output.rglob('*') if p.is_file()},indent=2)+'\n')


if __name__=='__main__': main()
