"""Check directly recorded GC spans and the declared process-local GC policy."""
import argparse
import json
from pathlib import Path
from audit_owner_wait_v1 import stamp,delta

def declared_owner_cpus(server):
    # Only the two explicit, disjoint Host layouts are supported. In particular,
    # accepting a new owner core must not silently allow overlap with native,
    # observer or renderer threads.
    plan=server['host_resources']['cpus']
    common=dict(native=[1,9],observer=[0,8])
    baseline=dict(common,owner=[2,3,10,11],renderer=[4,5,6,7,12,13,14,15])
    three=dict(common,owner=[2,3,4,10,11,12],renderer=[5,6,7,13,14,15])
    if plan not in (baseline,three):raise ValueError('declared disjoint two/three-core owner layout')
    return tuple(plan['owner'])

def declared_policy(server):
    if server.get('profile_owner_gc') is not True or server.get('profile_state_path') is not True:
        raise ValueError('explicit GC and state-path observation')
    if server.get('endurance_seconds') not in (30,300):raise ValueError('finite GC observation horizon')
    serial=server.get('owner_serial_gc',False)
    owner=server['argv']['owner'];renderer=server['argv']['renderer']
    if owner.count('-StrataM10GcProfile')!=1 or any('gc.' in s or s=='-StrataM10GcProfile' for s in renderer):
        raise ValueError('GC policy and profiling must be owner only')
    gc_commands=[s for s in owner if 'gc.' in s]
    if serial:
        if len(gc_commands)!=1 or not gc_commands[0].startswith('-ExecCmds=') or not gc_commands[0].endswith(',gc.AllowParallelGC 0'):
            raise ValueError('declared serial GC command')
        if gc_commands[0].count('gc.')!=1:raise ValueError('undeclared additional GC policy')
    elif gc_commands:raise ValueError('undeclared GC override')
    return serial

def validate(profile,serial,owner_cpus=(2,3,10,11)):
    if tuple(owner_cpus) not in ((2,3,10,11),(2,3,4,10,11,12)):
        raise ValueError('declared owner CPU set')
    if int(profile['errors']) or profile['active'] is not False:
        raise ValueError('incomplete or invalid GC journal')
    if profile['parallel']!=(0 if serial else 1):raise ValueError('declared GC parallel policy')
    if abs(profile['period_seconds']-61.1)>1e-4:raise ValueError('unchanged GC period')
    if len(profile['cycles'])>64:raise ValueError('bounded GC journal')
    result=[];previous=0;frame=0
    for row in profile['cycles']:
        begin,trim,end=stamp(row['begin']),stamp(row['memory_trim']),stamp(row['end']);span=delta(begin,end)
        before_trim,allocator_trim=delta(begin,trim),delta(trim,end)
        if begin['wall_ns']<=previous or int(row['completed_frame'])<=frame:
            raise ValueError('GC order/frame identity')
        if any(point['processor'] not in owner_cpus for point in (begin,trim,end)):
            raise ValueError('GC owner CPU placement')
        result.append(dict(completed_frame=int(row['completed_frame']),begin=begin,memory_trim=trim,end=end,
            delta=span,before_memory_trim=before_trim,allocator_trim_to_gc_end=allocator_trim))
        previous=end['wall_ns'];frame=int(row['completed_frame'])
    return result

def audit(run):
    read=lambda p:json.loads((run/p).read_text())
    server=read('server.json')
    serial=declared_policy(server)
    owner_cpus=declared_owner_cpus(server)
    cycles=validate(read('capture/owner-gc.json'),serial,owner_cpus)
    native=read('capture/native.json');initial=native['initial']
    live=[r for r in cycles if initial<=r['begin']['wall_ns']<=initial+server['endurance_seconds']*1_000_000_000]
    if server['endurance_seconds']==300 and len(live)<4:
        raise ValueError('unchanged periodic GC not observed throughout five minutes')
    return dict(status='PASS_GC_OBSERVATION_ONLY',serial=serial,period_seconds=61.1,owner_cpus=list(owner_cpus),
        cycles=cycles,live_cycles=len(live),maximum_live_wall_ns=max((r['delta']['wall_ns'] for r in live),default=None),
        scope='direct GC delegate brackets; original physical and freshness audits remain authoritative')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as e:result=dict(status='FAIL',error=str(e).replace(str(a.run),'<run>'))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if result['status']=='PASS_GC_OBSERVATION_ONLY' else 1)
