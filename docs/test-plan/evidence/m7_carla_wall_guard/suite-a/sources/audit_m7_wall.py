#!/usr/bin/env python3
"""Independent audit of the deliberately idle wall guard window, not RT acceptance."""
import argparse
import copy
import csv
import gzip
import json
from pathlib import Path


def require(value, message):
    if not value:
        raise AssertionError(message)


def validate(records, rows):
    require(len(records)==200, '199 completed intervals and one terminal barrier')
    require([r['index'] for r in records]==list(range(200)), 'contiguous original trace')
    terminal=records[-1]
    arm,stop=terminal['wall_guard_arm'],terminal['wall_guard_stop']
    require(arm['status']=='WALL_GUARD_ARMED' and arm['period_ns']==2000000 and
            arm['deadline_ns']==4000000, 'original 2ms/4ms schedule')
    require(stop['status']=='WALL_GUARD_STOP' and stop['next_frame'] is None and
            not stop['normal'] and stop['credit_mask']==0 and stop['selected_mask']==255 and
            not stop['actual_exported'] and not stop['physical_braking_accepted'], 'local terminal selection, no Actual substitute')
    require(stop['logical_barrier_ns']==terminal['native']['now_ns'], 'no selection backdating/replay')
    require('staged' not in terminal and 'receipt' not in terminal, 'no new stage/advance after arming')
    require(all('receipt' in r for r in records[:-1]) and
            all(r['settlement_ack']['ok'] for r in records[1:]), 'all observed work settled before stop')
    require(not any('protection_request' in r for r in records), 'no explicit PROTECT injection')
    require(stop['wall_selected_ns']<=terminal['wall_stop_received_ns']<=terminal['wall_containment_ns'], 'monotonic selection/receipt/containment')
    seen=set();faults={};monitor_completed=0
    for row in rows:
        owner,slot=row['owner'],row['slot']
        require(0<=owner<=9 and slot>=0 and (owner,slot) not in seen, 'owner/slot identity')
        seen.add((owner,slot))
        require(row['release_ns']==arm['first_release_ns']+slot*2000000 and
                row['deadline_ns']==row['release_ns']+4000000, 'original release/deadline')
        if row['end_ns']:
            require(row['start_ns']>=row['release_ns'] and row['end_ns']>=row['start_ns'], 'actual monotonic completion')
        if owner<9:
            # No WHEEL/WORK/owner jobs were submitted during this window.
            require(row['start_ns']==row['end_ns']==0, 'polling/waiting cannot count as owner execution')
            if row['detected_ns']:
                require(row['deadline_ns']<=row['detected_ns']<=stop['wall_selected_ns'], 'independent deadline fault before selection')
                faults.setdefault(owner,row)
        elif row['end_ns']:
            monitor_completed+=1
    require(set(faults)==set(range(9)) and monitor_completed>0, 'all missing owners observed independently')
    detected=min(row['detected_ns'] for row in faults.values())
    return dict(status='PASS_EXPECTED_WALL_CONTAINMENT',receipts=199,settlements=199,
                first_release_ns=arm['first_release_ns'],faulted_owners=sorted(faults),
                monitor_completed_jobs=monitor_completed,
                maximum_detection_lateness_ns=max(r['detected_ns']-r['deadline_ns'] for r in faults.values()),
                detection_to_local_selection_ns=stop['wall_selected_ns']-detected,
                detection_to_adapter_containment_ns=terminal['wall_containment_ns']-detected,
                wall_runtime_accepted=False,clock_mapping_accepted=False,physical_braking_accepted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    trace=args.evidence/'trace.jsonl'
    if trace.exists():
        records=[json.loads(line) for line in trace.read_text().splitlines()]
    else:
        with gzip.open(str(trace)+'.gz','rt') as f:
            records=[json.loads(line) for line in f]
    with (args.evidence/'native-wall.csv').open() as f:
        rows=[{key:int(value) for key,value in row.items()} for row in csv.DictReader(f)]
    report=validate(records,rows)
    negatives=[]
    for fault in ('missing-owner','heartbeat-as-owner','relaxed-deadline','selection-missing','selection-backdated'):
        changed_records,changed_rows=copy.deepcopy(records),copy.deepcopy(rows)
        if fault=='missing-owner':
            changed_rows=[r for r in changed_rows if r['owner']!=3]
        elif fault=='heartbeat-as-owner':
            row=next(r for r in changed_rows if r['owner']==3)
            row['start_ns']=row['end_ns']=row['release_ns']
        elif fault=='relaxed-deadline':
            changed_rows[0]['deadline_ns']+=1
        elif fault=='selection-missing':
            changed_records[-1]['wall_guard_stop']['selected_mask']=254
        else:
            changed_records[-1]['wall_guard_stop']['logical_barrier_ns']-=1
        try:
            validate(changed_records,changed_rows)
        except AssertionError:
            negatives.append(fault)
        else:
            raise AssertionError('oracle accepted '+fault)
    report['rejected_corruptions']=negatives
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
