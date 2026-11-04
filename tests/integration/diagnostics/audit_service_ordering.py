#!/usr/bin/env python3
"""Independent original CSV check for vehicle authority / two-Zone command ordering."""
import argparse
import copy
import csv
import json
from pathlib import Path


def require(condition,message):
    if not condition:raise ValueError(message)


def load(root):
    return {p.name:list(csv.DictReader(p.open())) for p in sorted(root.glob('*.transport.csv'))}


def judge(files):
    commands=deferred=0
    for name,rows in files.items():
        latest={};pending=None;staged={};previous={}
        for row in rows:
            event=row['event'];epoch=int(row['epoch']);peer=int(row['peer']);operation=int(row['operation'])
            source=int(row['original_source']);token=int(row['token']);now=int(row['ns'])
            if event=='zone-received':
                if operation==1:latest[epoch]=source
                elif operation==3:
                    require(latest.get(epoch)==source,f'{name}: command parent was superseded before arrival token={token}')
                    commands+=1
            if event=='vehicle-authorization-deferred':
                require(token==0,'staged root must not pretend to own a transmitted token')
                staged[epoch,source]=row;deferred+=1
            if event=='central-result-accepted' and peer==1 and operation==3:
                require(pending==(epoch,source),'Rear result must close the original Front batch');pending=None
            if event=='central-enqueued':
                require(token>previous.get((epoch,peer),0),'actual per-peer tokens must increase')
                previous[epoch,peer]=token
                if operation==1:
                    require(pending is None,'new parent overtook an unfinished Front/Rear batch')
                    if original:=staged.get((epoch,source)):
                        require(row['sent']==original['sent'] and row['deadline']==original['deadline'], 'staged authority result budget changed')
                        require(int(original['ns'])<=now<int(row['deadline']),'staged authority enqueued outside original budget')
                elif operation==3 and peer==0:
                    require(pending is None,'overlapping command batches');pending=(epoch,source)
    require(commands>0,'no actual Zone commands to audit')
    return {'commands_checked':commands,'authorizations_staged':deferred}


def mutations(files):
    changed=copy.deepcopy(files)
    command=next(r for rows in changed.values() for r in rows if r['event']=='zone-received' and r['operation']=='3')
    command['original_source']=str(int(command['original_source'])+1)
    try:judge(changed)
    except ValueError:pass
    else:raise ValueError('superseded parent mutation accepted')
    changed=copy.deepcopy(files)
    staged={(name,r['epoch'],r['original_source']) for name,rows in changed.items() for r in rows if r['event']=='vehicle-authorization-deferred'}
    emitted=next((r for name,rows in changed.items() for r in rows if r['event']=='central-enqueued' and r['operation']=='1' and (name,r['epoch'],r['original_source']) in staged),None)
    if emitted:
        emitted['deadline']=str(int(emitted['deadline'])+1)
        try:judge(changed)
        except ValueError:pass
        else:raise ValueError('renewed staging budget mutation accepted')
    return 2 if emitted else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--mutations',action='store_true');args=parser.parse_args()
    data=load(args.directory);result=judge(data)
    if args.mutations:result['mutations_rejected']=mutations(data)
    print(json.dumps(result,sort_keys=True))
