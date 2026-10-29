#!/usr/bin/env python3
"""Independent simulation-profile continuity/lifecycle/fault evidence checks.

Wire, solver equations, energy and scenario behavior have separate auditors.
This audit never converts simulation ages into host real-time acceptance.
"""
import argparse
import gzip
import json
from pathlib import Path
from audit_m7_1q_native import check


def audit(directory, case, corrupt=None):
    result=json.loads((directory/'result.json').read_text())
    events=json.loads((directory/'events.json').read_text())
    server=json.loads((directory.parent/('server-'+directory.name+'.json')).read_text())
    check(result['status'].startswith('PASS') and result['execution_profile']=='m7-simulation-time-v1','profile/runtime')
    check(server['status']=='COMPLETE_ISOLATED_RUN' and server['server_exit']==130 and 'forced_stop' not in server,'owned server shutdown')
    check(not result['wall_runtime_accepted'],'no real-time acceptance substitution')
    check(all(r['status']=='PASS' for r in result['cases']),'no failed runtime assertion')
    checks={r['name']:r['status'] for r in result['cases']}
    required=('foreign_batch_writer_denied','foreign_tick_denied','ticket_single_use',
              'wall_pause_no_tick_or_restamp','containment_pause_clear_no_tick','latched_no_resume',
              'reset_requires_new_init','ego_destroyed','restored_settings_actors','native_expected_exit')
    check(all(checks.get(k)=='PASS' for k in required),'writer/lifecycle coverage')
    binding=result['binding'];start=int(binding['frame']);count=0;normal=0;seen_normal=False
    last=None;terminal=None;first_wall=None;end_wall=None
    path=directory/'trace.jsonl'
    with (path.open() if path.exists() else gzip.open(str(path)+'.gz','rt')) as stream:
        for index,line in enumerate(stream):
            row=json.loads(line)
            if corrupt and index==200:corrupt(row)
            terminal=row
            check(row['index']==index and row['frame']==start+index,'continuous source sequence')
            if first_wall is None:first_wall=row['wall_begin_ns']
            end_wall=row['wall_end_ns']
            if 'receipt' not in row:continue
            q=row['receipt'];count+=1
            check(int(q['frame'])==start+count,'no skipped/duplicate physics')
            check(all(q[k]==binding[k] for k in ('run','session','actor','application','model_sha256')),'one original session')
            check(q['physics']['generation']==binding['physics']['generation'],'no hidden reset between cycles')
            if last:check(q['simulation_begin_seconds']==last['simulation_end_seconds'],'time continuity')
            check(abs(q['simulation_end_seconds']-q['simulation_begin_seconds']-.01)<1e-6,'original 10ms simulation step')
            actual=q['original_actual']['admitted_actual'];normal+=actual['normal']
            if case.startswith('continuous') and seen_normal:check(actual['normal'] and not actual['protection'],'uninterrupted normal authority')
            seen_normal|=actual['normal'];last=q
    check(count==result['receipts'] and normal==result['normal_intervals'],'reported original counts')
    final_frame=start+count
    pause=next(e for e in events if e['request']['op']=='pause')
    reset=next(e for e in events if e['request']['op']=='reset')
    check(int(pause['response']['frame'])==final_frame and pause['response']['latched'],'fault/end cannot add physics')
    check(reset['response']['latched'] and reset['response']['physics']['inputs_zero'],'reset invalidates, not a braking witness')
    if case.startswith('continuous'):
        check(result['continuous_simulation'] and count==result['requested_ticks']==6000,'60s bounded execution')
        check(terminal.get('terminal_settlement') and result['settlements']==6000,'last original work settled once')
        check(checks.get('continuous_final_wheel_stop')=='PASS' and checks.get('native_profile_rejects_synthetic_stage')=='PASS','normal brake end/Actual-only')
    elif case=='native-stall':
        check(count==200 and result['settlements']==199 and 'native' not in terminal and 'receipt' not in terminal,'stalled pending work not invented')
        watch=terminal['host_watchdog']
        check(watch['timeout_seconds']==10 and watch['detected_ns']-watch['begin_ns']>=10_000_000_000,'actual host wait bound')
        check(checks.get('host_watchdog_no_tick')=='PASS','host watchdog containment')
    elif case=='snapshot-stop':
        check(count==200 and result['status']=='PASS_EXPECTED_SNAPSHOT_STOP' and
              'snapshot missing/skipped' in terminal['error'] and 'native' not in terminal,'stale original snapshot rejected')
    elif case=='work-missing':
        check(count==200 and terminal['native']['status']=='FAIL' and terminal['native']['next_frame'] is None,'partial work rejected before next tick')
    elif case=='rgb-drop':
        sensors=json.loads((directory/'sensors.json').read_text())
        check(len(sensors['dropped'])==1 and sensors['errors'] and 'receipt' not in terminal,'sensor gap blocks tick')
    elif case=='protected-sleep':
        check(count==400 and checks.get('protection_history_cleared_on_new_init')=='PASS','terminal protection/new INIT')
        check(last['physics']['sleeping'] and last['original_actual']['admitted_actual']['protection'],'natural stop before reset')
    else:raise ValueError('unknown case')
    return dict(status='PASS_SIMULATION_SCOPE_ONLY',case=case,receipts=count,normal_intervals=normal,
        simulated_seconds=last['simulation_end_seconds']-binding['simulation_seconds'],
        execution_wall_seconds=(end_wall-first_wall)/1e9,one_session=True,
        original_timestamps=True,wall_realtime_accepted=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--case',required=True);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    try:result=audit(a.directory,a.case)
    except (ValueError,KeyError,StopIteration) as error:result=dict(status='FAIL',error=str(error))
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    return int(result['status']=='FAIL')


if __name__=='__main__':raise SystemExit(main())
