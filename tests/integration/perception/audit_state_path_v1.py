"""Join original owner/native timestamps; diagnostic integrity, not acceptance."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import statistics

PHASES=('admitted','staged','before_tick','after_tick','acquired_begin','acquired_end',
        'work_begin','work_end','publish_begin','publish_end','complete')


def owner_path(receipt,path):
    stamps=[{k:int(v) for k,v in path[name].items()} for name in PHASES]
    if any(s['wall_ns']<=0 or s['cpu_ns']<=0 for s in stamps):raise ValueError('missing owner clock')
    spans={}
    for i,(a,b) in enumerate(zip(stamps,stamps[1:])):
        wall=b['wall_ns']-a['wall_ns'];cpu=b['cpu_ns']-a['cpu_ns']
        if min(wall,cpu)<0 or cpu>wall+100_000:raise ValueError('owner clock order')
        spans[PHASES[i]+'_to_'+PHASES[i+1]]=dict(wall_ns=wall,cpu_ns=cpu,wall_minus_cpu_ns=max(0,wall-cpu))
    if stamps[4]['wall_ns']!=int(receipt['physics_acquisition_begin_ns']) or stamps[5]['wall_ns']!=int(receipt['physics_acquisition_end_ns']):
        raise ValueError('original acquisition identity')
    if not stamps[2]['wall_ns']<=int(receipt['wall_applied_ns'])<=stamps[3]['wall_ns']:raise ValueError('original application bracket')
    return stamps,spans


def join(receipt, native, path):
    stamps,spans=owner_path(receipt,path)
    if native['frame']!=int(receipt['frame']) or native['acquired_begin_ns']!=stamps[4]['wall_ns']:
        raise ValueError('native receipt identity')
    times=[native[k] for k in ('read_begin_ns','read_end_ns','service_begin_ns','service_end_ns','proof_publish_ns')]
    if any(x<=0 for x in times) or times!=sorted(times):raise ValueError('native clock order')
    if native['cpu_begin_ns']<=0 or native['cpu_end_ns']<native['cpu_begin_ns']:raise ValueError('native CPU clock order')
    # A reader can finish between the publication linearization and its end stamp.
    if native['read_end_ns']<stamps[8]['wall_ns']:raise ValueError('read precedes publication')
    return dict(frame=int(receipt['frame']),ticket=int(receipt['ticket']),
        normal=receipt['original_actual']['native']['normal'],
        acquisition_ns=stamps[4]['wall_ns'],owner_spans=spans,
        acquisition_to_publication_ns=stamps[8]['wall_ns']-stamps[5]['wall_ns'],
        publication_to_native_upper_ns=native['read_end_ns']-stamps[8]['wall_ns'],
        acquisition_to_native_ns=native['read_end_ns']-stamps[4]['wall_ns'],
        native_service_ns=native['service_end_ns']-native['service_begin_ns'],
        native_cpu_ns=native['cpu_end_ns']-native['cpu_begin_ns'],
        max_pump_gap_ns=int(path['max_pump_gap_ns']),
        max_rpc_ns=int(path['max_rpc_ns']))


def hv_origin(receipt):
    # HV depends on actuator/coil inputs, which need not be acquisition times.
    # Match the original physical audit's derivation, preserving all sources.
    applied=int(receipt['wall_applied_ns'])
    actuator=int(receipt['original_actual']['admitted_actual']['oldest_actuator_ns']) or applied
    coil=int(receipt['coil_source_ns']) or applied
    return dict(source_ns=int(receipt['physics_acquisition_begin_ns']),
        dependency_ns=min(actuator,coil),source_frame=int(receipt['frame']),
        actuator_source_ns=actuator,coil_source_ns=coil,applied_ns=applied)


def hv_join(native,origins):
    if not native['hv_source']:
        if native['hv_dependency']:raise ValueError('HV dependency without source')
        return None
    origin=origins.get(native['energy_end'])
    if origin is None or (native['hv_source'],native['hv_dependency'])!=(origin['source_ns'],origin['dependency_ns']):
        raise ValueError('HV original work/actuator/coil identity')
    if not 0<origin['dependency_ns']<=origin['source_ns']<=native['now']:
        raise ValueError('HV original clock order')
    return origin


def quant(values):
    values=list(values)
    return dict(count=len(values),median_ns=statistics.median(values),
        p95_ns=statistics.quantiles(values,n=100,method='inclusive')[94] if len(values)>1 else values[0],
        max_ns=max(values)) if values else None


def audit(run):
    read=lambda p:json.loads(p.read_text())
    if not read(run/'server.json').get('profile_state_path') or not read(run/'capture/result.json').get('profile_state_path'):
        raise ValueError('undeclared state path profile')
    def csvs(name):
        with (run/'capture'/name).open() as f:return [{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
    native=csvs('native.csv');paths=csvs('native-state-path.csv')
    if len(paths)!=len(native) or any(p['service_begin_ns']!=n['now'] for p,n in zip(paths,native)):
        raise ValueError('complete native call coverage')
    consumed={p['frame']:p for p in paths if p['frame']}
    if len(consumed)!=sum(bool(p['frame']) for p in paths):raise ValueError('duplicate consumption')
    rows=[];origins={}
    with gzip.open(run/'capture/trace.jsonl.gz','rt') as stream:
        for line in stream:
            record=json.loads(line);receipt=record['receipt'];frame=int(receipt['frame'])
            if 'state_path' in receipt:raise ValueError('diagnostic mutated original receipt')
            if frame not in consumed:raise ValueError('missing consumed frame')
            row=join(receipt,consumed.pop(frame),record['state_path']);rows.append(row)
            energy_end=int(receipt['work_end_ns'])
            if energy_end in origins:raise ValueError('duplicate original work end')
            origins[energy_end]=hv_origin(receipt)
    if consumed:raise ValueError('unmatched native frame')
    hv=[];last=None
    for n,p in zip(native,paths):
        origin=hv_join(n,origins)
        key=(n['energy_end'],n['hv_source'],n['hv_dependency'])
        if key!=last and origin:
            hv.append(dict(service_begin_ns=n['now'],service_end_ns=p['service_end_ns'],
                **origin,dependency_age_ns=n['now']-origin['dependency_ns']))
        last=key
    fault=next((n['now'] for n in native if n['protection']),None)
    phase={}
    for name,group in [('all',rows),('normal',[r for r in rows if r['normal']]),('non_normal',[r for r in rows if not r['normal']])]:
        phase[name]={k:quant(r[k] for r in group) for k in ('acquisition_to_publication_ns','publication_to_native_upper_ns','acquisition_to_native_ns','native_service_ns','native_cpu_ns','max_pump_gap_ns','max_rpc_ns')}
        phase[name]['owner_spans']={span:{metric:quant(r['owner_spans'][span][metric] for r in group)
            for metric in ('wall_ns','cpu_ns','wall_minus_cpu_ns')} for span in rows[0]['owner_spans']} if rows else {}
    return dict(status='PASS_DIAGNOSTIC_TRACE_INTEGRITY',scope='does not replace the original physical/renderer/shadow acceptance audits; wall-minus-CPU includes waiting/preemption and measurement skew',
        native_calls=len(native),receipts=len(rows),hv_derivations=len(hv),first_protection_ns=fault,
        phases=phase,first_fault_owner_window=[r for r in rows if fault and abs(r['acquisition_ns']-fault)<=200_000_000],
        first_fault_hv_window=[r for r in hv if fault and abs(r['service_begin_ns']-fault)<=200_000_000])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as error:result=dict(status='FAIL',error=str(error).replace(str(a.run),'<run>'))
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('phases','first_fault_owner_window','first_fault_hv_window')}))
    raise SystemExit(0 if result['status']=='PASS_DIAGNOSTIC_TRACE_INTEGRITY' else 1)
