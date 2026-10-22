"""M6 SIL-only response contract. Model samples bracket, never backdate, completion."""
import csv
import json
import math
from pathlib import Path

CONFIG=Path(__file__).resolve().parents[3]/'profiles/m6_sil_response_v1.json'

def contract():
    c=json.loads(CONFIG.read_text())
    torque=max(abs(c['minimum_torque_nm']),c['maximum_torque_nm'])-c['torque_tolerance_nm']
    ramp=max(torque/c['zero_rate_nm_s'],(c['brake_floor_pa']-c['brake_minimum_pa'])/c['brake_rise_pa_s'])*1e9
    budget=ramp+c['protection_delay_ns']+sum(c[k] for k in ('delivery_budget_ns','model_budget_ns','observation_budget_ns','margin_ns'))
    if not math.isclose(budget,c['selection_to_observed_complete_ns'],abs_tol=1):raise ValueError('inconsistent model budget')
    return c

def response_oracle(folder,result):
    folder=Path(folder);out={'pass':True,'errors':[]}
    def require(ok,why):
        if not ok:out['pass']=False;out['errors'].append(why)
    def rows(name):
        with (folder/name).open() as f:return list(csv.DictReader(f))
    try:
        c=contract();require(result.get('physical_response')==c,'missing/wrong explicit M6 response contract')
        require(json.loads((folder/'physical-response-contract.json').read_text())==c,'missing/mismatched saved contract')
        model=json.loads((folder/'response-model.json').read_text())
        require(all(model.get(k)==c[k] for k in ('minimum_torque_nm','maximum_torque_nm','zero_rate_nm_s','normal_delay_ns','brake_initial_pa','brake_rise_pa_s')),'compiled physical model differs from budget')
        require(model['brake_maximum_pa']>=c['brake_floor_pa'],'protection floor outside model')
        injection=int((folder/'inject').read_text());rs=rows('physical-response.csv')
        require(2<=len(rs)<=1024,'missing/bounded response samples')
        for r in rs:
            for k in ('torque_nm','pressure_pa'):require(math.isfinite(float(r[k])),'nonfinite physical actual')
            require(injection<=int(r['before_ns'])<=int(r['model_ns'])<=int(r['after_ns']),'invalid step/application time interval')
            require(int(r['epoch'])>0,'missing response epoch')
        require(all(int(a['model_ns'])<int(b['model_ns']) for a,b in zip(rs,rs[1:])),'nonmonotonic model samples')
        require(all(int(b['model_ns'])-int(a['model_ns'])<=c['model_budget_ns'] for a,b in zip(rs,rs[1:])),'model execution gap exceeds retained guard')
        live={r['role']:r['summary'] for r in result['processes'] if r['role'] in ('front','rear') and not r.get('expected_abrupt_stop')}
        targets=[];applications=[]
        for leaf,role in [('drive','rear'),('brake','front')]:
            # pre_shutdown_protection is logged AFTER synchronous protection;
            # the service-entry event brackets detection, it is not a new source time.
            observed=live[role]['pre_shutdown_protection'];ack=live[role]['selected_ns']
            intervals=[e for e in rows(role+'-1.events.csv') if e['event']=='local-protection-service' and int(e['deadline'])==observed]
            require(len(intervals)==1,'missing local detection service interval '+leaf)
            if len(intervals)!=1:continue
            t=int(intervals[0]['value'])
            require(injection<=t<=observed<=ack<=t+c['local_selection_ns'],'local protection selection ACK late '+leaf)
            selected=[r for r in rs if int(r[leaf+'_selected'])>=injection and int(r[leaf+('_zero' if leaf=='drive' else '_protect')])==1]
            require(bool(selected),'missing actual local target '+leaf)
            if not selected:continue
            r=selected[0];s=int(r[leaf+'_selected']);targets.append(s)
            # A later published repeated protective output is an upper bound on first selection.
            require(0<=s-t<=c['local_selection_ns'],'local detection-to-selection deadline '+leaf)
            applied=[x for x in selected if int(x[leaf+'_applied'])==int(x[leaf+'_source']) and int(x[leaf+'_applied'])>0]
            require(bool(applied),'protective output not consumed '+leaf)
            if applied:
                a=applied[0];applications.append(int(a['after_ns']));require(int(a['after_ns'])-s<=c['delivery_budget_ns'],'output handoff late '+leaf)
                out[leaf]={'detection_interval_ns':[t,observed],'selection_ack_ns':ack,'selection_observed_ns':s,'application_interval_ns':[int(a['before_ns']),int(a['after_ns'])]}
        if len(targets)==2 and len(applications)==2:
            require(max(applications)-min(targets)<=c['delivery_budget_ns'],'both protective outputs not applied within global handoff budget')
        complete=[r for r in rs if abs(float(r['torque_nm']))<=c['torque_tolerance_nm'] and float(r['pressure_pa'])>=c['brake_floor_pa']]
        require(len(targets)==2 and bool(complete),'actual torque/brake protection incomplete')
        if len(targets)==2 and complete:
            r=complete[0];end=int(r['model_ns']);origin=min(targets)
            require(end>=max(targets) and int(r['after_ns'])-origin<=c['selection_to_observed_complete_ns'],'physical response deadline exceeded')
            i=rs.index(r);out.update(injection_ns=injection,origin_ns=origin,first_model_complete_ns=end,first_observed_complete_ns=int(r['after_ns']),crossing_interval_ns=[int(rs[i-1]['model_ns']) if i else None,end],injection_to_complete_ns=end-injection,selection_to_complete_ns=end-origin)
            legacy=rows('physical.csv');sampled=[x for x in legacy if int(x['ns'])>=origin and abs(float(x['torque']))<=c['torque_tolerance_nm'] and float(x['pressure'])>=c['brake_floor_pa']]
            out['first_10ms_complete_ns']=int(sampled[0]['ns']) if sampled else None
            # New high-rate model evidence is required, legacy10ms rows alone cannot replace it.
        if result.get('case')=='command-loss':
            ev=rows(result['fault_target']+'-1.leaf-events.csv')
            expiry=[r for r in ev if r['event']=='command-expired' and int(r['owner'])==4 and int(r['ns'])>=injection]
            require(bool(expiry),'missing Drive original command-expiry detection')
            if expiry:
                e=expiry[0];detect=int(e['ns'])
                valid=[r for r in ev if r['event']=='valid-input' and int(r['owner'])==4 and int(r['detail'])==1 and int(r['source'])==int(e['source']) and int(r['deadline'])==int(e['deadline']) and int(r['ns'])<=detect]
                require(bool(valid),'missing matching last valid command reception')
                if valid:
                    rx=int(valid[-1]['ns']);require(0<=detect-rx<=c['loss_detection_ns'],'last-valid reception-to-detection exceeds100ms')
                    out['loss']={'last_valid_rx_ns':rx,'source_ns':int(e['source']),'original_expiry_ns':int(e['deadline']),'detected_ns':detect,'rx_to_detect_ns':detect-rx,'injection_to_detect_ns':detect-injection}
                require(detect>=int(e['deadline']),'expiry detected before original expiry')
    except (OSError,KeyError,ValueError,TypeError,IndexError) as e:require(False,'missing/invalid response evidence: '+str(e))
    return out
