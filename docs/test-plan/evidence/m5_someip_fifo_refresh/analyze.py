#!/usr/bin/env python3
"""Offline accounting. Does not run/retry a workload or alter raw verdicts."""
import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

p = argparse.ArgumentParser()
p.add_argument('raw_root', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
rows, timeline, ordering = [], [], []
for plan in sorted(a.raw_root.glob('*/plan.json')):
    campaign = plan.parent
    for result in json.loads((campaign/'results.json').read_text()):
        folder = campaign/(result['case']+'-'+str(result['repeat']))
        raw = json.loads((folder/'result.json').read_text())
        summaries = {str(x['role'])+'-'+str(x['generation']): x.get('summary', {}) for x in raw['processes']}
        row = dict(cohort=campaign.name, case=result['case'], repeat=result['repeat'], raw_exit=result['exit'],
                   individual_pass=raw['pass'], final_source=campaign.name.startswith('final-'),
                   error=raw.get('error'), sanitizer_diagnostics=raw.get('sanitizer_diagnostics'),
                   unexpected_sdk_errors=raw.get('unexpected_sdk_errors'), forced_cleanup=raw['forced_cleanup'],
                   ip_data_packets=raw.get('ip_data_packets'), native=raw.get('native'), summaries=summaries)
        rows.append(row)
        for file in sorted(folder.glob('*.events.csv')):
            events = list(csv.DictReader(file.open()))
            for event in events:
                if event['event'] in ('epoch-store-begin','epoch-store-return','epoch-issued','all-eight-released',
                                      'normal-armed','native-injection','local-protection','leaf-protection-selected',
                                      'central-fault','native-watch-protection','leaf-first-fault'):
                    timeline.append(dict(cohort=campaign.name, case=folder.name, file=file.name, **event))
            returned = [int(x['ns']) for x in events if x['event']=='epoch-store-return']
            if not returned:
                continue
            native = file.with_name(file.name.replace('.events.csv','.native.watch.json'))
            if not native.exists():
                continue
            origin = json.loads(native.read_text())['origin']
            # Runner's final Central summary aliases the rejoined guard. Recover
            # the FIRST generation origin from its preserved pre-rejoin channel.
            if result['case']=='restart-live' and file.name=='central-1.events.csv':
                snapshot = json.loads((folder/'after-front-crash-watch-channels.json').read_text())
                origin = snapshot['central']['enable']-100_000_000
            ordering.append(dict(cohort=campaign.name, case=folder.name, file=file.name,
                                 returned_ns=max(returned), guard_origin_ns=origin, pass_order=max(returned)<=origin))
        for file in folder.glob('*.leaf-events.csv'):
            for event in csv.DictReader(file.open()):
                if event['event']=='command-expired':
                    timeline.append(dict(cohort=campaign.name, case=folder.name, file=file.name,
                                         ns=event['ns'],event=event['event'],epoch=event['epoch'],
                                         role=event['owner'],value=event['source'],deadline=event['deadline']))
regression = []
for file in sorted(a.raw_root.glob('*ctest.xml')):
    tests = ET.parse(file).getroot().findall('.//testcase')
    failed = [t.attrib['name'] for t in tests if t.find('failure') is not None]
    regression.append(dict(file=file.name,total=len(tests),passed=len(tests)-len(failed),failed=failed))
summary = dict(runtime_total=len(rows),runtime_pass=sum(r['raw_exit']==0 for r in rows),rows=rows,
               regression=regression,epoch_before_guard=ordering,
               acceptance='BLOCKED: historical short-support renewal remains unresolved; no retrospective FAIL conversion')
(a.output/'results-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
fields=['cohort','case','repeat','raw_exit','individual_pass','final_source','sanitizer_diagnostics','error']
with (a.output/'results.csv').open('w') as out:
    w=csv.DictWriter(out,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
with (a.output/'timeline.csv').open('w') as out:
    fields=['cohort','case','file','ns','event','epoch','role','value','deadline']
    w=csv.DictWriter(out,fields,extrasaction='ignore');w.writeheader();w.writerows(sorted(timeline,key=lambda r:int(r['ns'])))
print(json.dumps({'runtime_total':len(rows),'runtime_pass':summary['runtime_pass'],'ordering_records':len(ordering),
                  'ordering_pass':sum(x['pass_order'] for x in ordering)}))
