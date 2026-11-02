#!/usr/bin/env python3
"""Exercise the M8 oracle on copies of complete original nominal evidence."""
import argparse
import copy
import json
from pathlib import Path
from unittest.mock import patch
import audit_m8_speed as oracle
from evidence_io import json_rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    # Retain only fields consumed by this oracle; work has its own mutation suite.
    rows=[]
    for raw in json_rows(a.directory/'trace.jsonl'):
        row={k:v for k,v in raw.items() if k in ('index','frame','simulation_seconds','physics','native','receipt','terminal_settlement','error')}
        if 'native' in row:row['native']={k:v for k,v in row['native'].items() if k in ('native_export','speed_control','status','next_frame')}
        if 'receipt' in row:row['receipt']={k:v for k,v in row['receipt'].items() if k in ('frame','run','session','actor','application','model_sha256','physics','simulation_begin_seconds','simulation_end_seconds','original_actual')}
        rows.append(row)
    with patch.object(oracle,'json_rows',lambda _:iter(rows)):
        baseline=oracle.audit(a.directory,'nominal')
    oracle.check(baseline['status'].startswith('PASS'),'complete baseline passes')
    control_index=next(i for i in range(200,len(rows)) if
        rows[i]['native']['speed_control']['sequence']!=rows[i-1]['native']['speed_control']['sequence'])
    mutations={
        'source_restamped':(control_index,lambda r:r['native']['speed_control'].update(source_ns=r['native']['speed_control']['release_ns'])),
        'request_expiry_extended':(control_index,lambda r:r['native']['speed_control'].update(expiry_ns=r['native']['speed_control']['expiry_ns']+1)),
        'input_expiry_extended':(control_index,lambda r:r['native']['speed_control'].update(input_expiry_ns=r['native']['speed_control']['input_expiry_ns']+1)),
        'wrong_radius':(control_index,lambda r:r['native']['speed_control'].update(speed_mps=10)),
        'skipped_release':(control_index,lambda r:r['native']['speed_control'].update(sequence=999)),
        'nonfinite_integral':(control_index,lambda r:r['native']['speed_control'].update(integral=float('nan'))),
        'wrong_target':(control_index,lambda r:r['native']['speed_control'].update(target_mps=9)),
        'excessive_slew':(control_index,lambda r:r['native']['speed_control'].update(acceleration_mps2=2)),
        'physical_overspeed':(1800,lambda r:r['physics'].update(body_forward_velocity_m_s=4)),
        'physical_not_stopped':(3700,lambda r:r['physics'].update(body_forward_velocity_m_s=1)),
        'hidden_reset':(200,lambda r:r['receipt']['physics'].update(generation=999)),
    }
    rejected={}
    for name,(index,mutate) in mutations.items():
        bad=copy.deepcopy(rows[index]);mutate(bad)
        def changed(_):
            return (bad if i==index else row for i,row in enumerate(rows))
        with patch.object(oracle,'json_rows',changed):
            try:result=oracle.audit(a.directory,'nominal')
            except ValueError as error:rejected[name]=str(error)
            else:
                oracle.check(result['status']=='FAIL','accepted corruption: '+name)
                rejected[name]=result['failures']
    with patch.object(oracle,'json_rows',lambda _:iter(rows[:-1])):
        try:oracle.audit(a.directory,'nominal')
        except ValueError as error:rejected['missing_terminal_settlement']=str(error)
        else:raise ValueError('accepted missing terminal settlement')
    result=dict(status='PASS_ORACLE_MUTATIONS',rejected=rejected,baseline=baseline)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
