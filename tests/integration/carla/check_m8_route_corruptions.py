#!/usr/bin/env python3
"""Exercise the M8 oracle on copies of complete original nominal evidence."""
import argparse
import copy
import json
from pathlib import Path
from unittest.mock import patch
import audit_m8_route as oracle
from evidence_io import json_rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    # Retain only fields consumed by this oracle; work has its own mutation suite.
    rows=[]
    for raw in json_rows(a.directory/'trace.jsonl'):
        row={k:v for k,v in raw.items() if k in ('index','frame','simulation_seconds','physics','native','receipt','terminal_settlement','error','vehicle_state','route_pose','pose_input')}
        if 'native' in row:row['native']={k:v for k,v in row['native'].items() if k in ('native_export','speed_control','lateral_control','route_reference','status','next_frame')}
        if 'receipt' in row:row['receipt']={k:v for k,v in row['receipt'].items() if k in ('frame','run','session','actor','application','model_sha256','physics','simulation_begin_seconds','simulation_end_seconds','original_actual')}
        rows.append(row)
    with patch.object(oracle,'json_rows',lambda _:iter(rows)):
        baseline=oracle.audit(a.directory,'nominal')
    oracle.check(baseline['status'].startswith('PASS'),'complete baseline passes')
    control_index=next(i for i in range(200,len(rows)) if
        rows[i]['native']['speed_control']['sequence']!=rows[i-1]['native']['speed_control']['sequence'])
    mutations={
        'pose_missing':(200,lambda r:r.pop('route_pose')),
        'pose_wrong_actor':(200,lambda r:r['route_pose'].update(actor=0)),
        'pose_future':(200,lambda r:r['route_pose'].update(source_ns=r['route_pose']['source_ns']+1)),
        'pose_wrong_y_sign':(200,lambda r:r['route_pose'].update(y_m=-r['route_pose']['y_m'])),
        'actor_origin_as_axle':(200,lambda r:r['route_pose'].update(x_m=r['vehicle_state']['position_ue_m'][0],y_m=-r['vehicle_state']['position_ue_m'][1])),
        'lateral_curvature':(control_index,lambda r:r['native']['lateral_control'].update(curvature_inv_m=.1)),
        'lateral_source_restamp':(control_index,lambda r:r['native']['lateral_control'].update(source_ns=r['native']['speed_control']['release_ns'])),
        'heading_hidden':(control_index,lambda r:r['native']['lateral_control'].update(heading_error_rad=999)),
        'source_restamped':(control_index,lambda r:r['native']['speed_control'].update(source_ns=r['native']['speed_control']['release_ns'])),
        'request_expiry_extended':(control_index,lambda r:r['native']['speed_control'].update(expiry_ns=r['native']['speed_control']['expiry_ns']+1)),
        'input_expiry_extended':(control_index,lambda r:r['native']['speed_control'].update(input_expiry_ns=r['native']['speed_control']['input_expiry_ns']+1)),
        'wrong_radius':(control_index,lambda r:r['native']['speed_control'].update(speed_mps=10)),
        'skipped_release':(control_index,lambda r:r['native']['speed_control'].update(sequence=999)),
        'nonfinite_integral':(control_index,lambda r:r['native']['speed_control'].update(integral=float('nan'))),
        'wrong_target':(control_index,lambda r:r['native']['speed_control'].update(target_mps=9)),
        'excessive_slew':(control_index,lambda r:r['native']['speed_control'].update(acceleration_mps2=2)),
        'physical_overspeed':(2800,lambda r:r['physics'].update(body_forward_velocity_m_s=10)),
        'physical_not_stopped':(5800,lambda r:r['physics'].update(body_forward_velocity_m_s=1)),
        'hidden_reset':(200,lambda r:r['receipt']['physics'].update(generation=999)),
    }
    if baseline.get('reference',{}).get('scenario')=='S03':
        slow_index=next(i for i,r in enumerate(rows) if r.get('native',{}).get('route_reference',{}).get('slow_elapsed_ns') is not None)
        stop_index=next(i for i,r in enumerate(rows) if r.get('native',{}).get('route_reference',{}).get('stop_elapsed_ns') is not None)
        mutations.update({
            'slow_request_missing':(slow_index,lambda r:r['native']['route_reference'].update(slow_elapsed_ns=None)),
            'slow_request_backdated':(slow_index,lambda r:r['native']['route_reference'].update(slow_elapsed_ns=r['native']['route_reference']['slow_elapsed_ns']-20000000)),
            'slow_request_late':(slow_index,lambda r:r['native']['route_reference'].update(slow_elapsed_ns=r['native']['route_reference']['slow_elapsed_ns']+20000000)),
            'requested_speed_unchanged':(slow_index,lambda r:r['native']['route_reference'].update(requested_mps=30/3.6)),
            'early_position_request':(control_index,lambda r:r['native']['route_reference'].update(slow_elapsed_ns=0,requested_mps=20/3.6)),
            'stop_request_missing':(stop_index,lambda r:r['native']['route_reference'].update(stop_elapsed_ns=None)),
            'stop_request_backdated':(stop_index,lambda r:r['native']['route_reference'].update(stop_elapsed_ns=r['native']['route_reference']['stop_elapsed_ns']-20000000)),
            'instant_target_step':(slow_index,lambda r:r['native']['speed_control'].update(target_mps=20/3.6)),
        })
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
