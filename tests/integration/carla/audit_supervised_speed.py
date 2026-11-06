#!/usr/bin/env python3
"""Audit the opt-in native speed path, original provenance and durable DTC.

Run the existing solver-work/NoDrive audit separately. This checks the new
supervision contract; it does not assess a learned model or the whole ODD.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import select
import subprocess

from evidence_io import json_rows, read_json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'diagnostics'))
from audit_control_diagnostics import event, journal, require


def audit(directory, mutate=None):
    result=read_json(directory/'result.json')
    require(result['status']=='PASS_FUNCTIONAL_NATIVE_SOLVER_WORK','runtime did not pass')
    require(result['execution_profile']=='m10-native-supervised-speed-v1','execution profile')
    require(result['learned_model']=='NOT_RUN_CLASSICAL_FALLBACK','unexpected model claim')
    fault_case=result['speed_terminal']=='input-loss'
    count=steps=0;last=None;fault=None;raw=[];maximum_speed=0.;final=None;mutated=False
    for row in json_rows(directory/'trace.jsonl'):
        native=row['native'];s=native['supervised_speed'];control=native.get('speed_control')
        if mutate and control and not mutated:
            mutate(native);mutated=True
        require(native['admission']['ok'],'server command admission')
        raw.extend(event(bytes.fromhex(v)) for v in native['diagnostics']['events'])
        if s['fault_ns'] is not None:
            require(fault_case and s['source']==2 and s['reason']==8,'unexpected supervision fault')
            if fault is None:fault=s['fault_ns']
            require(fault==s['fault_ns'] and native['admission']['protection'] and not native['admission']['normal'],'protection latch')
        elif control and (last is None or control['sequence']!=last['sequence']):
            force=s['force'];reference=s['reference'];now=control['release_ns']
            require(s['source']==1 and s['reason']==1,'classical fallback selection')
            require(0<=now-control['source_ns']<=30000000,'current wheel age')
            require(0<=now-force['source_ns']<=70000000,'original BMS dependency age')
            require(now<force['expiry_ns']<=force['source_ns']+70000001,'force expiry')
            require(control['expiry_ns']<=min(now+30000001,force['expiry_ns'],control['source_ns']+60000001),'request expiry renewal')
            require(control['input_expiry_ns']<=force['expiry_ns'],'power dependency omitted')
            require(reference['source_ns']==min(force['source_ns'],control['source_ns']),'reference oldest source')
            require(reference['expiry_ns']<=min(force['expiry_ns'],control['source_ns']+60000001),'reference expiry')
            low,high=result['road_load_bounds_n']
            require((force['road_load_min_n'],force['road_load_max_n'])==(low,high),'calibration changed')
            amin=max(-5.,(-.9*force['braking_n']-low)/1696.)
            amax=min(2.,(.9*force['propulsion_n']-high)/1696.)
            require(math.isclose(amin,reference['minimum_acceleration_mps2'],abs_tol=1e-12) and
                    math.isclose(amax,reference['maximum_acceleration_mps2'],abs_tol=1e-12),'force intersection')
            require(abs(control['target_mps']-control['speed_mps'])<=.5+1e-10,'tracking envelope')
            if last:
                require(now-last['release_ns']==20000000 and control['source_ns']>last['source_ns'],'release/acquisition progress')
                acceleration=(control['target_mps']-last['target_mps'])/.02
                require(amin-1e-9<=acceleration<=amax+1e-9,'reference acceleration')
            last=control;steps+=1
        require(not fault or s['fault_ns']==fault,'restored input resumed normal control')
        if row.get('receipt'):
            final=row['receipt']['physics'];maximum_speed=max(maximum_speed,final['body_forward_velocity_m_s'])
        count+=1
    require(count==4001 and steps>500,'finite campaign coverage')
    require(final is not None and maximum_speed>.5 and abs(final['body_forward_velocity_m_s'])<=.001 and
            all(w['solver_omega_rad_s']==0 for w in final['wheels']),'moving vehicle then physical stop')
    require(raw==journal(directory/'diagnostic-store'),'original events differ from durable journal')
    roots=[e for e in raw if e['kind']==1]
    if fault_case:
        root=[e for e in roots if (e['code'],e['component'],e['monitor'],e['subject'])==(0x1002,1,4,4)]
        require(len(root)==1 and root[0]['detected_ns']==fault and root[0]['native_reason']==8<<8,'supervision DTC root')
        related=[e for e in raw if e['_related']==root[0]['_id']]
        require(any(e['kind']==2 for e in related) and any(e['kind']==3 for e in related) and
                sum(e['kind']==4 for e in related)>=2,'protection/ACK/Actual chain')
        require(not any(e['kind']==5 and e['monitor']==4 for e in raw),'unqualified Passed')
    else:require(not roots and fault is None,'false DTC in nominal run')
    return dict(status='PASS_NATIVE_SUPERVISED_SPEED',observations=count,control_steps=steps,
                maximum_body_speed_mps=maximum_speed,final_body_speed_mps=final['body_forward_velocity_m_s'],
                fault_ns=fault,events=len(raw),fault_roots=len(roots),learned_model=False)


def replay(directory,binary,log):
    result=read_json(directory/'result.json');low,high=result['road_load_bounds_n']
    profile='v1-input-loss' if result['speed_terminal']=='input-loss' else 'v1'
    command=[str(binary.resolve()),'--native-solver-work','1','42','7',str(result['binding']['actor']),
             '--sim-horizon-ms','60000','--speed-profile',profile,'--supervised-speed',f'{low}:{high}']
    count=0;digest=hashlib.sha256()
    with log.open('w') as errors:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors,text=True)
        try:
            for row in json_rows(directory/'trace.jsonl'):
                for field in ('work_input','native_input'):
                    if row.get(field):process.stdin.write(row[field]+'\n')
                process.stdin.flush()
                require(bool(select.select([process.stdout],[],[],10)[0]),'native replay reply timeout')
                line=process.stdout.readline();require(json.loads(line)==row['native'],f'native replay differs at {count}')
                digest.update(line.encode());count+=1
            process.stdin.close();require(process.wait(timeout=10)==0,'native replay exit')
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=5)
            process.stdout.close()
            if not process.stdin.closed:process.stdin.close()
    require(count==4001,'replay coverage')
    return dict(observations=count,sha256=digest.hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mutations',action='store_true');parser.add_argument('--replay',type=Path)
    args=parser.parse_args()
    result=audit(args.directory)
    if args.mutations:
        changes=[lambda n:n['supervised_speed']['force'].__setitem__('source_ns',n['speed_control']['release_ns']+1),
                 lambda n:n['speed_control'].__setitem__('expiry_ns',n['supervised_speed']['force']['expiry_ns']+1),
                 lambda n:n['supervised_speed'].__setitem__('source',0)]
        rejected=0
        for change in changes:
            try:audit(args.directory,change)
            except ValueError:rejected+=1
        require(rejected==len(changes),'corruption was accepted');result['mutations_rejected']=rejected
    if args.replay:result['exact_native_replay']=replay(args.directory,args.replay,args.output.with_suffix('.replay.stderr'))
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
