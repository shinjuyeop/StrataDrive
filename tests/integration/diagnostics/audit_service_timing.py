#!/usr/bin/env python3
"""Verify original native service CPU placement and delayed marker receipts."""
import argparse
import copy
import csv
import json
from pathlib import Path


def require(condition,message):
    if not condition:raise ValueError(message)


def load(root):
    return {'plan':json.loads((root.parent/'plan.json').read_text()),
            'owner':{role:json.loads((root/(role+('-2' if role=='central' else '-1')+'.owner.runtime.json')).read_text()) for role in ('central','front','rear')},
            'process':{role:json.loads((root/(role+'.runtime.json')).read_text()) for role in ('central','front','rear')},
            'writer':{p.name:json.loads(p.read_text()) for p in root.glob('*.signals.runtime.json')},
            'signals':list(csv.DictReader((root/'central-2.signals.csv').open())),
            'epoch2_events':list(csv.DictReader((root/'central-2.events.csv').open())),
            'summary':json.loads((root/'central-2.json').read_text())}


def judge(data):
    require(data['plan']['split_owner_io'] and data['plan']['isolated_ecus'],'declared split owner/SDK profile')
    for role,owner,sdk in [('central',1,4),('front',2,5),('rear',7,6)]:
        info=data['owner'][role];process=data['process'][role]
        priority=(11 if role=='central' else 18) if data['plan'].get('owner_fifo') else 0
        policy=1 if priority else 0
        require(info['allowed_cpus']==[owner] and info['policy']==policy and info['priority']==priority,'actual declared owner CPU and policy')
        require(info['tid']==process['pid'],'owner placement must describe the actual process main thread')
        threads=process['threads']
        require(any(t['tid']==info['tid'] and t['affinity']==[owner] for t in threads),'independent process snapshot confirms owner CPU')
        require(any(t['tid']!=info['tid'] and t['affinity']==[sdk] for t in threads),'live SDK threads on separate declared CPU')
        require(all(t['affinity'] in ([owner],[sdk],[15]) and
                    (t['policy']==policy and t['priority']==priority if t['tid']==info['tid'] else t['policy']==t['priority']==0)
                    for t in threads),'no undeclared CPU or priority override')
    require(len(data['writer'])==5,'signal writers for plant, both Central incarnations and both peers')
    require(all(w['allowed_cpus']==[15] and w['policy']==w['priority']==0 for w in data['writer'].values()),'actual nonRT signal IO placement')
    armed=[r for r in data['signals'] if r['name']=='armed'];require(len(armed)==1,'one original arm marker per incarnation')
    r=armed[0];requested,begin,end=map(int,(r['requested_ns'],r['write_begin_ns'],r['write_end_ns']))
    arms=[r for r in data['epoch2_events'] if r['event']=='normal-armed' and r['epoch']=='2']
    require(len(arms)==1 and int(arms[0]['ns'])<=requested<=begin<=end,'original Epoch2 arm request and actual write timestamps')
    delay=data['plan']['signal_write_delay_ms']*1000000
    if delay:
        require(delay==250000000 and end-begin>=delay,'declared250ms delay actually executed')
        progress=[r for r in data['epoch2_events'] if r['event']=='command-enqueue' and begin<int(r['ns'])<end]
        require(len(progress)>=2 and not data['summary']['overflow'],'original Epoch2 command progress while marker write blocked')
    return {'split_owner_io':True,'marker_write_ns':end-begin,'final_epoch_owner_max_poll_gap_ns':data['summary']['max_owner_poll_gap_ns'],'delayed':bool(delay)}


def mutations(data):
    changes=[lambda d:d['owner']['central'].__setitem__('allowed_cpus',[4]),
             lambda d:d['writer'].clear(),
             lambda d:d['signals'].clear()]
    if data['plan']['signal_write_delay_ms']:
        changes.append(lambda d:[r.__setitem__('write_end_ns',r['write_begin_ns']) for r in d['signals'] if r['name']=='armed'])
    for change in changes:
        changed=copy.deepcopy(data);change(changed)
        try:judge(changed)
        except ValueError:continue
        raise ValueError('placement/delay mutation accepted')
    return len(changes)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--mutations',action='store_true');args=parser.parse_args()
    data=load(args.directory);result=judge(data)
    if args.mutations:result['mutations_rejected']=mutations(data)
    print(json.dumps(result,sort_keys=True))
