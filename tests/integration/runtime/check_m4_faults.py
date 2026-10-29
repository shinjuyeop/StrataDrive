#!/usr/bin/env python3
"""M4 functional evidence + the prospective 48-run M3 native cohort (no retries)."""
import argparse
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy
import resource
import select
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
BASE = runpy.run_path(str(ROOT / 'tests/integration/runtime/check_m4_async.py'))
PROFILES = BASE['PROFILES']
REPRESENTATIVES = ('central-stop', 'drive-stop', 'delay-expiry', 'overflow-rejoin', 'wall-overflow-rejoin', 'guard-monitor-overrun')


def save_csv(path, rows):
    if not rows:
        return
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def run(command, folder, name):
    with (folder / (name + '.log')).open('w') as stream:
        with subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT) as process:
            # Read the actual child, not inferred credentials of its launcher.
            try:
                identity = process_identity(process.pid)
            except (OSError, ProcessLookupError) as error:
                identity = {'pid': process.pid, 'error': str(error)}
            (folder/(name+'-identity.json')).write_text(json.dumps(identity, indent=2)+'\n')
            return process.wait()


def process_identity(pid):
    status = dict(line.split(':', 1) for line in Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in line)
    return dict(pid=pid, uids=list(map(int, status['Uid'].split())), cap_eff=status['CapEff'].strip(),
                rtprio=list(resource.prlimit(pid, resource.RLIMIT_RTPRIO)))


def load_child(folder, cpu):
    """Separate OTHER process; controlled wall busy demand, measured CPU use."""
    os.sched_setaffinity(0, {cpu}); os.sched_setscheduler(0, os.SCHED_OTHER, os.sched_param(0))
    identity = process_identity(os.getpid())
    (folder/'load-identity.json').write_text(json.dumps(identity, indent=2)+'\n')
    active = True
    def stop(_signal, _frame):
        nonlocal active
        active = False
    signal.signal(signal.SIGTERM, stop)
    start = time.monotonic_ns(); begin_cpu = time.process_time_ns(); windows = 0
    print('LOAD_READY', flush=True)
    while active:
        release = time.monotonic_ns(); end_busy = release + 7_000_000
        while active and time.monotonic_ns() < end_busy:
            pass
        windows += 1
        remaining = (release + 10_000_000 - time.monotonic_ns()) / 1e9
        if active and remaining > 0:
            time.sleep(remaining)
    data = {'cpu': cpu, 'policy': os.sched_getscheduler(0), 'priority': os.sched_getparam(0).sched_priority,
            'affinity': sorted(os.sched_getaffinity(0)), 'cpu_ns': time.process_time_ns()-begin_cpu,
            'wall_ns': time.monotonic_ns()-start, 'windows': windows, 'busy_ns': 7_000_000, 'period_ns': 10_000_000}
    (folder/'load.json').write_text(json.dumps(data, indent=2)+'\n')


def percentile(values, p):
    import math
    return sorted(values)[max(0, math.ceil(len(values)*p)-1)] if values else 0


def timing_run(folder, profile, policy, loaded, case, repetition):
    folder.mkdir(parents=True, exist_ok=False)
    demo = str(ROOT/PROFILES[profile]/'actuator_demo')
    if run([demo, 'epoch', 'init', str(folder/'epochs')], folder, 'epoch'):
        return {'profile': profile, 'policy': policy, 'loaded': loaded, 'case': case, 'repetition': repetition, 'verdict': 'BLOCKED', 'reason': 'durable grant bootstrap'}
    command = [demo, 'm4-async', 'wall', 'normal' if case=='normal' else 'fault', str(folder/'epochs'), str(folder/'result'), 'guards', 'cpus=0,1', 'duration-ms=2540']
    if policy == 'fifo': command.append('fifo')
    if case == 'drive-stop': command.append('fault=owner:pause:drive:1200:200:0')
    if case == 'monitor-overrun': command.append('fault=owner:overrun:monitor:1200:6:0')
    load = None
    control = True
    if loaded:
        load = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--load-child', str(folder), '--cpu', '1'], cwd=ROOT, stdout=subprocess.PIPE, stderr=(folder/'load.stderr').open('w'), text=True)
        ready, _, _ = select.select([load.stdout], [], [], 5)
        control = bool(ready) and load.stdout.readline().strip() == 'LOAD_READY'
    try:
        code = run(command, folder, 'runtime')
    finally:
        if load:
            control = control and load.poll() is None
            load.terminate()
            try:
                load.wait(timeout=5)
            except subprocess.TimeoutExpired:
                control = False; load.kill(); load.wait()
    if load:
        data = json.loads((folder/'load.json').read_text()) if (folder/'load.json').exists() else {}
        control = control and data.get('cpu_ns',0) >= 100_000_000 and data.get('policy')==0 and data.get('priority')==0 and data.get('affinity')==[1] and data.get('windows',0)>0
    prefix = folder/'result'/('wall-normal' if case=='normal' else 'wall-fault')
    row = {'profile': profile, 'policy': policy, 'loaded': loaded, 'case': case, 'repetition': repetition, 'verdict': 'FAIL', 'reason': '', 'exit_code': code, 'load_control': control}
    (folder/'command.json').write_text(json.dumps(command, indent=2)+'\n')
    if not prefix.with_suffix('.json').exists():
        row.update(verdict='FAIL', reason='runtime did not reach result; see runtime.log')
        return row
    result = json.loads(prefix.with_suffix('.json').read_text())
    priorities = [18,18,10,10,10,9,10,11,19,20]
    setup = result['startup_ok'] and len(result['threads'])==10
    for t in result['threads']:
        cpu = 0 if t['owner']<2 or t['owner']>=8 else 1
        setup = setup and t['setup_error']==0 and t['affinity']==[cpu] and t['cpu']==cpu and t['policy']==(1 if policy=='fifo' else 0) and t['priority']==(priorities[t['owner']] if policy=='fifo' else 0)
    jobs = list(csv.DictReader(Path(str(prefix)+'-execution.csv').open()))
    events = list(csv.DictReader(Path(str(prefix)+'-events.csv').open()))
    observed = [j for j in jobs if int(j['start_ns']) and int(j['end_ns'])]
    late = [(int(j['start_ns'])-int(j['release_ns']))/1e6 for j in observed]
    body = [(int(j['end_ns'])-int(j['start_ns']))/1e6 for j in observed]
    cpu_times = [int(j['cpu_ns'])/1e6 for j in observed]
    wake_delays = [(int(j['start_ns'])-int(j['requested_wake_ns']))/1e6 for j in observed if int(j.get('requested_wake_ns',0))]
    origin = int(jobs[0]['release_ns'])-100_000_000 if jobs else 0
    grid_control = bool(observed) and all(0 < int(j.get('requested_wake_ns',0)) <= int(j['start_ns']) and (int(j['requested_wake_ns'])-origin) % (2_000_000 if int(j['owner'])==9 else 1_000_000 if int(j['owner'])==8 else 200_000)==0 for j in observed)
    growth_control = all(t.get('audit_buffer_growths',-1)==0 for t in result['timing'])
    response = 0.0; apply_response = 0.0
    fault_ok = True
    if case != 'normal':
        target = 4 if case=='drive-stop' else 9
        trips = [e for e in events if e['kind']=='deadline-detected' and int(e['code'])==target]
        applied = [e for e in events if e['kind']=='override-applied']
        injected = [e for e in events if e['kind'] in ('owner-stopped','overrun-injected') and int(e['owner'])==target]
        returned = [e for e in events if e['kind'] in ('owner-resumed','overrun-ended') and int(e['owner'])==target]
        fault_ok = bool(trips and applied and injected and returned)
        if fault_ok:
            detect = int(trips[0]['time_ns']); deadline = int(trips[0]['deadline_ns'])
            response = (detect-deadline)/1e6; apply_response = (int(applied[0]['time_ns'])-detect)/1e6
            fault_ok = 0 <= response <= 10 and 0 <= apply_response <= 10 and int(injected[0]['time_ns']) <= detect < int(returned[0]['time_ns'])
    metrics=[]
    for owner in range(10):
        sample=[j for j in observed if int(j['owner'])==owner]
        starts=[int(j['start_ns']) for j in sample]
        periods=[(b-a)/1e6 for a,b in zip(starts,starts[1:])]
        wakes=[(int(j['start_ns'])-int(j['release_ns']))/1e6 for j in sample]
        bodies=[(int(j['end_ns'])-int(j['start_ns']))/1e6 for j in sample]
        controls=[e for e in events if int(e['owner'])==owner and e['kind']=='control-completed']
        controller_starts=[int(e['reference_ns']) for e in controls]
        controller_periods=[(b-a)/1e6 for a,b in zip(controller_starts,controller_starts[1:])]
        metrics.append({'owner':owner,'samples':len(sample),'service_period_mean_ms':sum(periods)/len(periods) if periods else 0,
                        'service_period_p95_ms':percentile(periods,.95),'service_period_p99_ms':percentile(periods,.99),'service_period_max_ms':max(periods,default=0),
                        'wake_mean_ms':sum(wakes)/len(wakes) if wakes else 0,'wake_p95_ms':percentile(wakes,.95),'wake_p99_ms':percentile(wakes,.99),'wake_max_ms':max(wakes,default=0),
                        'body_mean_ms':sum(bodies)/len(bodies) if bodies else 0,'body_p95_ms':percentile(bodies,.95),'body_p99_ms':percentile(bodies,.99),'body_max_ms':max(bodies,default=0),
                        'control_samples':len(controls),'control_period_mean_ms':sum(controller_periods)/len(controller_periods) if controller_periods else 0,
                        'control_period_p95_ms':percentile(controller_periods,.95),'control_period_p99_ms':percentile(controller_periods,.99),'control_period_max_ms':max(controller_periods,default=0),
                        'control_deadline_misses':sum(e['code']!='0' for e in controls)+sum(e['kind']=='control-late-start' and int(e['owner'])==owner for e in events)})
    (folder/'owners.json').write_text(json.dumps(metrics,indent=2)+'\n')
    exact_window = len(jobs)==10*1211
    ok = code==0 and result['passed'] and setup and control and exact_window and grid_control and growth_control and fault_ok and (case!='normal' or result['timing_ok'])
    row.update(verdict='PASS' if ok else 'BLOCKED' if not result['startup_ok'] and any(t['setup_error'] in (1,13) for t in result['threads']) else 'FAIL', reason='' if ok else 'functional/setup/load/window/deadline oracle; inspect preserved raw',
               setup_control=setup, grid_control=grid_control, growth_control=growth_control, requested_wake_max_ms=max(wake_delays,default=0), jobs=len(jobs), deadline_misses=result['deadline_misses'], skipped=result['skipped_opportunities'],
               wake_mean_ms=sum(late)/len(late) if late else 0, wake_p95_ms=percentile(late,.95), wake_p99_ms=percentile(late,.99), wake_max_ms=max(late,default=0),
               body_mean_ms=sum(body)/len(body) if body else 0, body_p95_ms=percentile(body,.95), body_p99_ms=percentile(body,.99), body_max_ms=max(body,default=0),
               cpu_mean_ms=sum(cpu_times)/len(cpu_times) if cpu_times else 0, detect_after_deadline_ms=response, apply_after_detect_ms=apply_response,
               live_fault_ns=result['live_fault_ns'], normal_blocked_ns=result['normal_blocked_ns'])
    return row


def cohort(directory):
    directory.mkdir(parents=True, exist_ok=False)
    metadata = {'source_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), 'source_digest': BASE['fingerprint'](),
                'protocol_sha256': hashlib.sha256((ROOT/'docs/archive/protocols/m4-fault-timing-protocol.md').read_bytes()).hexdigest(),
                'followup_protocol_sha256': hashlib.sha256((ROOT/'docs/archive/protocols/m4-follow-up-protocol.md').read_bytes()).hexdigest(),
                'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'planned_runs':48, 'duration_ns':2540000000, 'guard_lead_ns':100000000,
                'period_ns':2000000, 'deadline_ns':4000000, 'guard_slots_per_owner':1211, 'tail_ns':20000000, 'cpus':[0,1], 'repetitions':3}
    (directory/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    rows=[]
    for profile in PROFILES:
        for repetition in range(3):
            conditions=[(policy,loaded,'normal') for policy in ('other','fifo') for loaded in (False,True)] + [(policy,False,case) for policy in ('other','fifo') for case in ('drive-stop','monitor-overrun')]
            conditions=conditions[repetition:]+conditions[:repetition]
            for policy,loaded,case in conditions:
                name=f'{profile}-{repetition+1}-{policy}-{int(loaded)}-{case}'
                row=timing_run(directory/name,profile,policy,loaded,case,repetition+1); row['raw']=name
                rows.append(row); (directory/'cohort.json').write_text(json.dumps(rows,indent=2)+'\n')
                print(name,row['verdict'],flush=True)
    return rows


def export(raw, output, timing):
    output.mkdir(parents=True,exist_ok=True)
    metadata=json.loads((raw/'metadata.json').read_text())
    if metadata['source_digest'] != BASE['fingerprint'](): raise ValueError('functional reuse source fingerprint differs')
    counts={}; scenarios={}
    for profile in PROFILES:
        tests=BASE['junit'](raw/profile/'unit.xml'); counts[profile]=len(tests)
        if any(v!='PASS' for v in tests.values()): raise ValueError('failed functional suite; original JUnit retained')
        for p in sorted((raw/profile/'faults').glob('*/*-fault.json')):
            data=json.loads(p.read_text()); name=p.parent.name
            if not data['passed'] or not data['model_preserved'] or not data['gate_latched'] or data['stopped_ack_violations']: raise ValueError(f'failed fault {profile}/{name}')
            scenarios[profile+'/'+name]={k:v for k,v in data.items() if k not in ('timing','threads')}
            if profile=='normal' and name in REPRESENTATIVES:
                rows=list(csv.DictReader(p.with_suffix('.csv').open()))
                keep=set(range(0,len(rows),3)) | {len(rows)-1}
                for ns in (data['effective_injection_ns'],data['live_fault_ns'],data['normal_blocked_ns'],data['recovery_ns'],data['rejoin_active_ns']):
                    if ns and rows: keep.add(min(range(len(rows)),key=lambda i:abs(float(rows[i]['elapsed_ms'])-ns/1e6)))
                save_csv(output/(name+'.csv'),[rows[i] for i in sorted(keep)])
                events=list(csv.DictReader(p.with_name(p.stem+'-events.csv').open()))
                events=[e for e in events if e['kind'] not in ('sent','delivered','valid-input','valid-feedback') or (1160<=float(e['elapsed_ms'])<=1240 and e['kind'].startswith('valid-'))]
                save_csv(output/(name+'-events.csv'),events)
    report={'metadata':metadata,'scope':'Host shared-process component; system TC NOT RUN; learner review pending','counts':counts,'scenarios':scenarios}
    if timing:
        tm=json.loads((timing/'metadata.json').read_text())
        if tm['source_digest'] != BASE['fingerprint'](): raise ValueError('cohort source fingerprint differs')
        rows=json.loads((timing/'cohort.json').read_text())
        fields=list(dict.fromkeys(key for row in rows for key in row))
        save_csv(output/'timing-results.csv',[{key:row.get(key,'') for key in fields} for row in rows])
        owners=[]
        for trial in rows:
            p=timing/trial['raw']/'owners.json'
            if p.exists():
                for metric in json.loads(p.read_text()): owners.append({**{k:trial[k] for k in ('profile','policy','loaded','case','repetition')},**metric})
        save_csv(output/'owner-timing.csv',owners)
        report['timing']={'metadata':tm,'counts':{v:sum(row['verdict']==v for row in rows) for v in ('PASS','FAIL','BLOCKED')},'requested':tm['planned_runs'],'recorded':len(rows),'not_run':tm['planned_runs']-len(rows)}
    mapping=list(csv.DictReader((ROOT/'docs/test-plan/component-traceability.csv').open()))
    for profile in PROFILES:
        tests=BASE['junit'](raw/profile/'unit.xml')
        for row in mapping: row[profile]=tests[row['test']]
    save_csv(output/'component_results.csv',mapping)
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    plot(output)
    print(json.dumps({'counts':counts,'fault_cases':len(scenarios),'source_commit':metadata['source_commit'],'timing':report.get('timing',{}).get('counts',{})}),flush=True)


def plot(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({'svg.fonttype':'none','svg.hashsalt':'StrataDrive-M4-faults-v1'})
    for name in ('drive-stop','overflow-rejoin'):
        rows=list(csv.DictReader((output/(name+'.csv')).open()))
        x=[float(r['elapsed_ms'])/1000 for r in rows]
        fig,axes=plt.subplots(4,1,sharex=True,figsize=(7.2,6.4),constrained_layout=True)
        for ax,field,label,scale in zip(axes,('angle_rad','pressure_pa','torque_nm','energy_j'),('Angle [rad]','Pressure [MPa]','Torque [Nm]','Energy change [J]'),(1,1e6,1,1)):
            values=[float(r[field])/scale for r in rows]
            if field=='energy_j': values=[v-values[0] for v in values]
            ax.plot(x,values,linewidth=1.3); ax.set_ylabel(label);ax.grid(alpha=.25);ax.axvline(1.2,color='#b54',linestyle='--',linewidth=.8)
            if name=='overflow-rejoin':ax.axvline(2.3,color='#478',linestyle='--',linewidth=.8)
        axes[0].set_title(name);axes[-1].set_xlabel('Logical elapsed time [s]')
        path=output/(name+'.svg');fig.savefig(path,metadata={'Date':None});plt.close(fig)
        path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()).rstrip()+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir',type=Path,default=Path('build/m4-fault-final'))
    parser.add_argument('--output',type=Path,default=Path('build/m4-fault-evidence'))
    parser.add_argument('--reuse',action='store_true')
    parser.add_argument('--timing-dir',type=Path)
    parser.add_argument('--run-timing',action='store_true')
    parser.add_argument('--load-child',type=Path);parser.add_argument('--cpu',type=int,default=1)
    args=parser.parse_args()
    if args.load_child:load_child(args.load_child,args.cpu);return
    raw=args.raw_dir.resolve();output=args.output.resolve()
    if not args.reuse:
        subprocess.run([sys.executable,str(ROOT/'tests/integration/runtime/check_m4_async.py'),'--raw-dir',str(raw),'--output',str(raw/'baseline-export')],cwd=ROOT,check=True)
    if args.run_timing:
        if not args.timing_dir: raise ValueError('--run-timing requires a new --timing-dir')
        cohort(args.timing_dir.resolve())
    export(raw,output,args.timing_dir.resolve() if args.timing_dir else None)

if __name__=='__main__':main()
