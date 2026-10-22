"""Offline native verdict. Timing failures are not converted to normal success."""
import csv
import json
from pathlib import Path

def native_oracle(folder,case,result,fifo):
    folder=Path(folder);three=result.get('three_ecu',False);target=result.get('fault_target','front');out={'pass':True,'errors':[],'processes':[],'normal_timing_ok':True,'fault_protection_ok':None}
    def require(ok,why):
        if not ok:out['pass']=False;out['errors'].append(why)
    try:
        injected=int((folder/'inject').read_text()) if (folder/'inject').exists() else 0
        native_fault=case in ('owner-pause','monitor-overrun','model-delay')
        if native_fault:
            require(injected>0,'declared fault was not injected')
            for process in result.get('processes',[]):
                protected=process.get('summary',{}).get('pre_shutdown_protection',0)
                require(not protected or protected>=injected,'normal protection preceded fault injection')
        for path in sorted(folder.glob('*.native.watch.json')):
            info=json.loads(path.read_text())
            with path.with_suffix('.csv').open() as stream:rows=list(csv.DictReader(stream))
            active=[{k:int(v) for k,v in r.items()} for r in rows if int(r['deadline'])<=info['quiesced']]
            missed=[r for r in active if not r['end'] or r['end']>r['deadline']]
            require(all(r['deadline']-r['release']==4_000_000 for r in active),'guard deadline changed')
            require(all(not r['end'] or (r['requested'] and r['requested']<=r['start'] and r['release']<=r['requested']<r['release']+2_000_000) for r in active),'completed wrong requested slot')
            require(info['monitor']['policy']==(1 if fifo else 0) and info['monitor']['priority']==(20 if fifo else 0) and info['monitor']['allowed_cpus']==[0],'monitor placement/policy')
            role=path.name.split('-')[0];cpu={'central':1,'front':2,'rear':7,'plant':3}[role];priority={'central':11,'front':18,'rear':18,'plant':19}[role]
            owner=info.get('owner',{})
            require(owner.get('policy')==(1 if fifo else 0) and owner.get('priority')==(priority if fifo else 0) and owner.get('allowed_cpus')==[cpu],'per-generation owner setup '+path.name)
            if case=='normal' and role!='plant':require(len(active)>=2422 if three else len(active)==2422,'normal1211 owner/monitor slots missing')
            if three:require(info['quiesced']<=info['stop']-20_000_000,'owner outlived guarded observation window '+path.name)
            row={'file':path.name,'active_slots':len(active),'misses':len(missed),'first_miss':missed[0] if missed else None,'fault_ns':info['fault_ns'],'fault_deadline':info['fault_deadline']};out['processes'].append(row)
            if missed:out['normal_timing_ok']=False
            if native_fault:
                require(all(r['deadline']>=injected for r in missed),'miss before declared injection')
            else:require(not missed,'unexpected native deadline miss: '+path.name)
        require(len(out['processes'])>=2,'missing native watch records')
        if three:
            live={p['role'] for p in result.get('processes',[]) if not p.get('expected_abrupt_stop')}
            recorded={p['file'].split('-')[0] for p in out['processes']}
            require(live<=recorded,'missing surviving ECU watch records')
        for role,cpu,priority in [('central',1,11),('front',2,18),('plant',3,19)]+([('rear',7,18)] if three else []):
            data=json.loads((folder/f'{role}.runtime.json').read_text());main=next(t for t in data['threads'] if t['tid']==data['pid'])
            require(main['affinity']==[cpu] and main['policy']==(1 if fifo else 0) and main['priority']==(priority if fifo else 0),'owner actual setup '+role)
            # SDK threads were created before owner policy. Only explicit monitor
            # TIDs may have FIFO20; no blanket promotion of dispatch/IO/sender.
            require(all(t['policy']==0 and t['priority']==0 or t['tid']==data['pid'] or (t['priority']==20 and t['affinity']==[0]) for t in data['threads']),'unexpected SDK RT thread')
        if case in ('owner-pause','monitor-overrun'):
            front=next(r for r in out['processes'] if r['file']==target+'-1.native.watch.json')
            require(front['misses']>0,'missing intended missed/late slot')
            require(0<=front['fault_ns']-front['fault_deadline']<=10_000_000 and front['fault_ns']>=injected,'independent deadline detection bound')
            with (folder/'plant-events.csv').open() as stream:events=list(csv.DictReader(stream))
            applied=[int(e['ns']) for e in events if e['event']=='override-applied' and int(e['ns'])>=injected]
            require(bool(applied) and 0<=min(applied)-front['fault_ns']<=10_000_000,'physical override bound')
            if case=='owner-pause':
                with (folder/(target+'-1.events.csv')).open() as stream:events=list(csv.DictReader(stream))
                begin=next(int(e['ns']) for e in events if e['event']=='native-injection')
                require(not any(e['event']=='local-ack-produced' and begin<int(e['ns'])<begin+200_000_000 for e in events),'paused owner fabricated ACK')
            out['fault_protection_ok']=not out['errors']
    except (OSError,ValueError,KeyError,StopIteration) as e:require(False,'native evidence missing: '+str(e))
    return out

def overflow_counters_ok(front,central,restarted):
    return (front.get('rx_highwater')==8 and front.get('overflow') is True
            and front.get('rx_rejected')==1 and front.get('rx_overflow_token')==1000000008
            and front.get('fifo_preserved') is True and front.get('overflow_drained')==8
            and front.get('unprocessed_rejected')==8
            and 0<front.get('rx_overflow_ns',0)<=front.get('pre_shutdown_protection',0)<=front.get('selected_ns',0)
            and restarted is True and central.get('diagnostic_sent')==8
            and central.get('diagnostic_rejected',0)+central.get('diagnostic_expired',0)==8)
