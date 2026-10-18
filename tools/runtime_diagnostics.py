#!/usr/bin/env python3
"""Sample owned runtime schedstat counters; retain coverage gaps and blocked kernel tracing."""
import argparse
import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('runtime_timing', ROOT/'tests/integration/runtime/check_timing.py')
timing = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(timing)


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


def capabilities():
    result = dict(kernel=os.uname().release,monotonic_clock='CLOCK_MONOTONIC',schedstat_sampling='intrusive diagnostic, not a performance baseline')
    config = Path('/boot')/('config-'+os.uname().release)
    try: result['sched_info_enabled'] = 'CONFIG_SCHED_INFO=y' in config.read_text()
    except OSError: result['sched_info_enabled'] = None
    try:
        result['tracefs'] = sorted(p.name for p in Path('/sys/kernel/tracing').iterdir())
    except OSError as error:
        result['tracefs_error'] = str(error)
    try:
        probe = subprocess.run(['perf','stat','-e','context-switches','--','true'],capture_output=True,text=True,check=False)
        result.update(perf_probe_exit=probe.returncode,perf_probe_stderr=probe.stderr)
    except OSError as error:
        result['perf_probe_error']=str(error)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir',type=Path,default=ROOT/'build/m1-angle')
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--owner-cpus',default='1,1,1,1,0,2,0')
    parser.add_argument('--observer-cpu',type=int,default=3)
    parser.add_argument('--load-cpu',type=int)
    parser.add_argument('--repetitions',type=int,default=3)
    args = parser.parse_args()
    timing.require(1 <= args.repetitions <= 10,'repetitions must be 1..10')
    allowed = os.sched_getaffinity(0)
    owners = timing.parse_owner_cpus(args.owner_cpus)
    timing.require(set(owners.values()) <= allowed and args.observer_cpu in allowed,'CPU outside allowed mask')
    timing.require(args.load_cpu is None or args.load_cpu in allowed,'load CPU outside allowed mask')
    os.sched_setaffinity(0,{args.observer_cpu})
    output = args.output_dir.resolve(); output.mkdir(parents=True,exist_ok=False)
    build = args.build_dir.resolve(); binary = build/'actuator_demo'
    # Keep original inherited CPU set in the runtime. The observer alone stays pinned.
    environment = timing.environment(build,binary,'multirate')
    environment.update(diagnostic=capabilities(),requested_owner_cpus=owners,observer_cpu=args.observer_cpu,load_cpu=args.load_cpu,
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
                    process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,preexec_fn=lambda:os.sched_setaffinity(0,allowed))
                    limit = time.monotonic()+10
                    while process.poll() is None:
                        samples.extend(snapshot(process.pid))
                        if time.monotonic()>limit: process.kill(); raise RuntimeError('diagnostic runtime timeout')
                        time.sleep(.001)
                    timing.require(process.returncode==0,'runtime process failed')
                    report['observations']=timing.observe_jobs(directory)
                    timing.validate_placement(report['observations']['metadata'],owners)
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
