#!/usr/bin/env python3
"""Independently connect STOP30 physical observations to original durable DTCs."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
from evidence_io import json_rows
from audit_m7_1q_native import check, frame, wire
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'diagnostics'))
from audit_control_diagnostics import event, journal


def load(directory):
    result=json.loads((directory/'result.json').read_text())
    server=json.loads((directory.parent/('server-'+directory.name+'.json')).read_text())
    original=journal(directory/'diagnostic-store',lambda b:b)
    captured=[];samples=[];actuals={};origin=None;recipe=None;last_commit=0
    for i,row in enumerate(json_rows(directory/'trace.jsonl')):
        n=row['native'];d=n['diagnostics'];t=n['speed_terminal'];s=n.get('speed_control')
        check(row['index']==i and n['now_ns']==math.floor(row['simulation_seconds']*1e9+.5),'original continuous barrier clock')
        check(n['stop_configuration']==dict(id='normal-stop30-a1-t10-v1',deceleration_mps2=1,braking_timeout_ns=10000000000,confirmation_ns=60000000,shutdown_timeout_ns=2000000000),'unchanged STOP30 configuration')
        if recipe is None:recipe=d['fault']
        check(recipe==d['fault'],'fixed diagnostic recipe')
        captured.extend(bytes.fromhex(raw) for raw in d['events'])
        check(row['diagnostic_committed']==len(captured) and row['diagnostic_committed']>=last_commit,'durable original event receipt')
        last_commit=row['diagnostic_committed']
        if s:
            if origin is None:origin=s['origin_ns']
            check(s['origin_ns']==origin,'original PI origin')
        for role,packet in enumerate(n['native_export']['actual']):
            if not packet:continue
            a=frame(wire(packet,0 if role<2 else 1,7,9),role,True,require_wheel=False)
            values=[(4,a['source'],a['value'])] if role==2 else [(5,a['source'],a['value'])] if role==1 else []
            if role==2 and a['wheel_valid']:values.append((11,a['wheel_source'],a['wheel']))
            for actor,source,value in values:
                key=(actor,source);check(key not in actuals or actuals[key]==value,'immutable original acquisition');actuals[key]=value
        samples.append(dict(now=n['now_ns'],trigger=t['trigger_ns'],detected=t['detection_ns'],stop_state=t['stop_state'],stop_fault=t['stop_fault'],
            body=row['physics']['body_forward_velocity_m_s'],wheels=[w['solver_omega_rad_s'] for w in row['physics']['wheels']],
            protection=n['admission']['protection'],torque=n['admission']['torque_nm'],pressure=n['admission']['pressure_pa'],
            omissions=d['omissions'],force=(row.get('receipt') or {}).get('diagnostic_external_force_n')))
    check(captured==original,'journal equals every original native event byte in order')
    frozen=directory/'frozen-route.json'
    check(hashlib.sha256(frozen.read_bytes()).hexdigest()==result['route_profile']['sha256'],'frozen route hash')
    return dict(result=result,server=server,events=[event(raw) for raw in original],samples=samples,actuals=actuals,origin=origin,recipe=recipe)


def judge(d):
    r=d['result'];rows=d['samples'];recipe=d['recipe'];events=d['events'];origin=d['origin']
    check(r['status'].startswith('PASS') and r['receipts']==r['settlements']==6000 and len(rows)==6001,'complete physics and EV work')
    check(d['server']['server_exit']==130 and not d['server'].get('forced_stop') and not r.get('forced_native_stop') and not r.get('forced_diagnostic_stop'),'owned shutdown')
    check(r['diagnostic_collector_exit']==0 and r['diagnostic_events_committed']==len(events),'complete durable recording')
    sessions=[e for e in events if e['kind']==6]
    check(len(sessions)==1 and sessions[0]['epoch']==42 and sessions[0]['received_roles']==255,'real global eight-role Session')
    plateau=[abs(x['body']*3.6-30) for x in rows if 25_000_000_000<=x['now']-origin<35_000_000_000]
    check(len(plateau)==1000 and max(plateau)<=.5,'original 30km/h precondition')
    triggered=[x for x in rows if x['trigger']]
    check(triggered and triggered[0]['trigger']==origin+35_000_000_000 and 29<=triggered[0]['body']*3.6<=31,'unchanged trigger and actual speed')
    roots=[e for e in events if e['kind']==1]
    if recipe==1:
        check(not roots and rows[-1]['stop_state']==5,'nominal completion without false DTC')
    else:
        expected={2:0x1001,3:0x1102,4:0x2001,5:0x1101,6:0x1002}
        check(recipe in expected,'qualified physical fault recipe')
        matched=[e for e in roots if e['code']==expected[recipe]]
        if recipe==4:
            matched=[e for e in matched if {a['source_producer'] for a in events if a['kind']==4 and a['_related']==e['_id'] and a['_occurrence']==e['_occurrence']}>={4,5,11}]
        check(len(matched)==1,'original declared detector DTC')
        root=matched[0];check(root['epoch']==42 and not root['_unmapped'] and root['detected_ns']>=triggered[0]['trigger'],'trusted original occurrence')
        check(not any(e['kind']==5 for e in events),'fault is not automatically Passed')
        selected=[e for e in events if e['kind'] in (2,3) and e['_related']==root['_id'] and e['_occurrence']==root['_occurrence']]
        check(selected and all(max(e['selected_ns'],e['acknowledged_ns'])>=root['detected_ns'] for e in selected),'actual protection follows detection')
        response=[x for x in rows if x['now']>=root['detected_ns'] and x['protection'] and abs(x['torque'])<=1 and x['pressure']>=1_000_000]
        check(response,'original protection Actual response')
        actual=[e for e in events if e['kind']==4 and e['_related']==root['_id'] and e['_occurrence']==root['_occurrence']]
        check({e['source_producer'] for e in actual}>={4,5,11},'DTC retains torque pressure and wheel acquisitions')
        check(all(e['actual_source_ns']>=root['detected_ns'] for e in actual),'response acquisition follows original detector')
        check(all(d['actuals'].get((e['source_producer'],e['actual_source_ns']))==e['measured'] for e in actual),'DTC response equals original CAN P05 acquisition')
        if recipe in (3,4,6):check(rows[-1]['omissions']>0,'actual transport injection')
        if recipe==4:
            check(r.get('admission_profile')=='sampled-actual-v1','silent loss uses declared sampled physical profile')
            check(root['detected_ns']>triggered[0]['trigger'],'silent loss is detected after actual omission, not preselected protection')
        if recipe==5:
            check(root['native_reason']==8 and root['_times'][1]['ns']==triggered[0]['trigger']+10_000_000_000,'original ten-second braking timeout')
            check(root['_times'][1]['ns']<=root['detected_ns']<=root['_times'][1]['ns']+1_000_000,'original detector invocation')
            forces=[x for x in triggered[:-1] if x['force']]
            check(len(forces)==len(triggered)-1 and all(abs(math.hypot(*x['force'][:2])-1800)<.01 and x['force'][2]==0 for x in forces),'declared persistent external force')
            at=next(x for x in rows if x['now']>=root['detected_ns']);check(at['body']>.001,'actual vehicle not stopped at braking deadline')
        check(rows[-1]['stop_state']!=5,'failed stop cannot fabricate normal completion')
    stopped=abs(rows[-1]['body'])<=.001 and all(w==0 for w in rows[-1]['wheels'])
    if recipe!=5:check(stopped,'actual final body and all four wheels stopped')
    return dict(recipe=recipe,events=len(events),faults=len(roots),physics=6000,settlements=6000,physical_stopped=stopped,plateau_max_error_kmh=max(plateau))


def mutations(d):
    checks=[('plateau',lambda x:x['samples'][2600].__setitem__('body',0)),('global-session',lambda x:x['events'].clear())]
    if d['recipe']!=1:
        checks += [('code',lambda x:[e.__setitem__('code',0) for e in x['events'] if e['kind']==1]),
                   ('foreign-producer-link',lambda x:[e.__setitem__('_related',(e['_related'][0],e['_related'][1]+1,e['_related'][2])) for e in x['events'] if e['kind']==4]),
                   ('physical-response',lambda x:[r.__setitem__('protection',False) for r in x['samples']]),
                   ('detection',lambda x:[e.__setitem__('detected_ns',0) for e in x['events'] if e['kind']==1])]
    for name,change in checks:
        bad=copy.deepcopy(d);change(bad)
        try:judge(bad)
        except (ValueError,AssertionError,KeyError,IndexError):continue
        raise ValueError('accepted mutation '+name)
    return len(checks)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--mutations',action='store_true');a=p.parse_args()
    data=load(a.directory);result=judge(data)
    if a.mutations:result['mutations_rejected']=mutations(data)
    print(json.dumps(result,sort_keys=True))
