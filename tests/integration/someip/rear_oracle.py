"""Three-ECU evidence: real endpoints, participants, Leaf renewal and shutdown.
No raw exit or timing verdict is rewritten here.
"""
import csv
import json
from pathlib import Path
from renewal_oracle import renewal_oracle


def expected_paused_overflow(case,role,target,summary,watch,injection):
    # Only saturation caused by the declared stopped consumer, after an independently
    # detected deadline fault. This is a fault outcome, never normal availability.
    return (case=='owner-pause' and role==target and summary.get('overflow') is True
            and injection<=watch.get('fault_ns',0)<=summary.get('rx_overflow_ns',0)
            and summary.get('authority_highwater')==8 and summary.get('authority_rejected',0)>0)

def rear_oracle(folder,case,result):
    folder=Path(folder);out={'pass':True,'errors':[]}
    def require(ok,why):
        if not ok:out['pass']=False;out['errors'].append(why)
    def rows(name):
        with (folder/name).open() as f:return list(csv.DictReader(f))
    try:
        capture=json.loads((folder/'capture.json').read_text())
        require(all(capture.get('peer_data_packets',{}).get(ip,0)>=4 for ip in ('10.88.0.2','10.88.0.3')),'missing both real TCP/IP paths')
        runtime=[json.loads((folder/(r+'.runtime.json')).read_text()) for r in ('central','front','rear')]
        require(len({r['netns'] for r in runtime})==3 and len({r['pid'] for r in runtime})==3,'ECUs not distinct processes/netns')
        live={r['role']:r.get('summary',{}) for r in result['processes'] if not r.get('expected_abrupt_stop')}
        for role in ('central','front','rear'):
            if role not in live:continue
            s=live[role]
            require(s.get('orderly_stop') is True and 0<s.get('stop_begin',0)<=s.get('stop_return',0)<=s.get('join_return',0),'stop/join not returned '+role)
            expected=False
            if s.get('overflow') and case=='owner-pause':
                watch=json.loads((folder/(role+'-1.native.watch.json')).read_text())
                expected=expected_paused_overflow(case,role,result['fault_target'],s,watch,int((folder/'inject').read_text()))
                if expected:out['expected_paused_consumer_overflow']={'role':role,'fault_ns':watch['fault_ns'],'overflow_ns':s['rx_overflow_ns'],'authority_rejected':s['authority_rejected']}
            require((not s.get('overflow') or expected) and s.get('rx_highwater',9)<=8 and s.get('authority_highwater',9)<=8,'unexpected overflow '+role)
        physical=rows('physical.csv')
        injection=int((folder/'inject').read_text()) if (folder/'inject').exists() else 0
        before=[r for r in physical if not injection or int(r['ns'])<injection]
        require(len(physical)>10 and any(float(r['torque'])>1 and float(r['pressure'])<1 for r in before),'no actual normal Drive/brake model response before injection')
        healthy=case in ('normal','restart-live')
        if healthy:
            c=live['central'];f=live['front'];r=live['rear']
            require(c.get('release_ack_mask')==255 and c.get('armed_ns',0)>0,'missing real eight-participant release/arm')
            require(c.get('normal_stop_complete',0)>c.get('normal_stop_started',0)>c.get('armed_ns',0),'normal stop did not complete')
            require(c.get('pre_shutdown_protection')==0 and c.get('pending_cancelled')==0 and c.get('pending_expired')==0,'normal command/protection failure')
            for role,s in [('front',f),('rear',r)]:
                require(s.get('pre_shutdown_protection',0)>=c.get('protected_ns',0),'premature protection '+role)
            require(r.get('drive_applied',0)>=10,'missing actual Drive commands')
            prefix='central-1-rejoined' if case=='restart-live' else 'central-1'
            events=rows(prefix+'.events.csv')
            released={int(e['role']) for e in events if e['event']=='session-ack' and int(e['value'])==20}
            require(released==set(range(8)),'missing individual accepted Release ACKs')
            # release_ack_mask is generated only by accepted actual ACKs;
            # keep individual ACK events as the primary participant time axis.
            out['session_events']=len([e for e in events if e['event']=='session-ack'])
            complete=c['normal_stop_complete']
            final=[p for p in physical if int(p['ns'])>=complete]
            require(bool(final) and any(float(p['bus'])<=30 and abs(float(p['torque']))<=1 for p in final),'actual HV/torque not down after normal stop')
            if case=='restart-live':
                require(result.get('survivor_pids_before')==result.get('survivor_pids_after') and len(result.get('survivor_pids_before',{}))==2,'surviving ECU restarted')
                out['renewal']=renewal_oracle(folder,three=True,epoch=c['epoch'],target=result['fault_target'])
                require(out['renewal']['pass'],'new Epoch Leaf renewal: '+str(out['renewal']['errors']))
        else:
            injection=int((folder/'inject').read_text())
            protected=[]
            for role,s in live.items():
                if role=='plant':continue
                t=s.get('pre_shutdown_protection',0)
                require(t>=injection and t>0,'missing post-injection protection '+role)
                if role!='central':require(s.get('selected_ns',0)>=t,'actual Leaf protection not selected '+role)
                protected.append(t)
            after=[p for p in physical if int(p['ns'])>=max(protected,default=injection)]
            protected_actual=[p for p in physical if injection<=int(p['ns'])<=injection+100_000_000 and abs(float(p['torque']))<=1 and float(p['pressure'])>=100000]
            require(bool(protected_actual),'actual torque/brake protection within original100ms not observed')
            out['physical_protection_ns']=int(protected_actual[0]['ns']) if protected_actual else None
            if case=='command-loss':
                target=result['fault_target'];events=rows(target+'-1.leaf-events.csv')
                expiry=[e for e in events if e['event']=='command-expired' and int(e['ns'])>=injection]
                require(bool(expiry) and all(int(e['ns'])>=int(e['deadline']) for e in expiry),'original command expiry not observed')
                out['expired_commands']=expiry
    except (OSError,KeyError,ValueError,TypeError) as e:require(False,'missing three-ECU evidence: '+str(e))
    return out
