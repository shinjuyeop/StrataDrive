#!/usr/bin/env python3
"""Check causal external-wheel ZOH prediction, never CARLA applied energy."""
import argparse
import json
import math
from pathlib import Path
from analyze_m7_1g import analyze as wheel_oracle, require


def analyze(path):
    wheel=wheel_oracle(path)
    summary=json.loads((path/'capture/summary.json').read_text())
    require(summary['native_mode']=='external-wheel-plant','wrong native mode')
    rows=[json.loads(line) for line in (path/'capture/frames.jsonl').read_text().splitlines()]
    sources={}
    end=None
    work=[]
    max_source_age=0
    max_work_error=0.
    max_total_error=0.
    for row in rows:
        now=round(row['sim_s']*1e9)
        sources[now]=(row['wheel'][2]['omega']+row['wheel'][3]['omega'])/2
        n=row['native']
        require(n['energy_basis']=='MODEL_ZOH_UNAPPLIED' and n['carla_work_valid'] is False,'false applied energy claim')
        require(len(n['electrical_steps'])<=11,'unbounded interval batch')
        for e in n['electrical_steps']:
            require(e['end_ns']-e['begin_ns']==1000000 and e['end_ns']<=now,'physical step grid/future')
            require(end is None or end==e['begin_ns'],'energy interval gap/overlap')
            end=e['end_ns']
            source=e['wheel_source_ns']
            require(source in sources and source<=e['begin_ns'] and e['wheel_oldest_ns']==source,'future/restamped dependency')
            require(e['wheel_rad_s']==sources[source],'energy used a different wheel')
            age=e['end_ns']-source
            require(age<=30000000 and e['begin_ns']-source<=10000000,'original EV age/skew')
            require(all(math.isfinite(e[k]) for k in ['wheel_rad_s','actual_torque_nm','mechanical_j','total_mechanical_j','soc','balance_j']),'nonfinite electrical audit')
            predicted=e['actual_torque_nm']*sources[source]*(e['end_ns']-e['begin_ns'])*1e-9
            max_work_error=max(max_work_error,abs(e['mechanical_j']-predicted))
            work.append(predicted)
            max_total_error=max(max_total_error,abs(e['total_mechanical_j']-math.fsum(work)))
            max_source_age=max(max_source_age,age)
    require(len(work)>=3900 and max_work_error<1e-8 and max_total_error<1e-8,'ZOH work mismatch/incomplete')
    require(math.fsum(work)>0,'positive wheel/actual excitation absent')
    return dict(wheel=wheel,external_zoh_audit='PASS',intervals=len(work),
                model_predicted_work_j=math.fsum(work),max_interval_error_j=max_work_error,
                max_cumulative_error_j=max_total_error,max_wheel_dependency_age_ns=max_source_age,
                carla_applied_work='UNAVAILABLE',normal_driving='NOT_CONNECTED')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('attempt',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    try:
        result=analyze(args.attempt)
        code=0
    except Exception as e:
        result=dict(external_zoh_audit='FAIL',error=str(e))
        code=1
    text=json.dumps(result,indent=2)+'\n'
    args.output.write_text(text)
    print(text,end='')
    return code


if __name__=='__main__':
    raise SystemExit(main())
