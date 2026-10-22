#!/usr/bin/env python3
"""Offline immutable-result accounting, with actual Leaf renewal time axes."""
import argparse,csv,json,xml.etree.ElementTree as ET
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('raw',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
def read(p):
 with p.open() as f:return list(csv.DictReader(f))
def write(name,rows,fields):
 with (a.output/name).open('w') as f:
  w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
rows=[];timeline=[];margins=[];limits={};profiles=[]
for plan in sorted(a.raw.glob('*/plan.json')):
 cohort=plan.parent;cfg=json.loads(plan.read_text())
 for item in json.loads((cohort/'results.json').read_text()):
  folder=cohort/(item['case']+'-'+str(item['repeat']));r=json.loads((folder/'result.json').read_text())
  row=dict(cohort=cohort.name,case=folder.name,source=cfg['source'],raw_exit=item['exit'],pass_observed=r['pass'],normal_timing_ok=r['native']['normal_timing_ok'],fault_protection_ok=r['native']['fault_protection_ok'],sanitizer=r['sanitizer_diagnostics'],sdk_errors=r['unexpected_sdk_errors'],forced_cleanup=r['forced_cleanup'],renewal=r.get('renewal'),ip_packets=r['ip_data_packets'],summaries=r['processes'])
  rows.append(row)
  if (folder/'renewal-margins.csv').exists():margins.extend(dict(cohort=cohort.name,case=folder.name,**x) for x in read(folder/'renewal-margins.csv'))
  for f in folder.glob('*.events.csv'):
   for e in read(f):
    if e['event']=='host-renewal-period':profiles.append(dict(cohort=cohort.name,case=folder.name,file=f.name,**e))
    if e['event'] in ('epoch-store-begin','epoch-store-return','host-renewal-period','epoch-issued','all-eight-released','normal-armed','native-injection','local-protection','leaf-protection-selected','central-fault','native-watch-protection','protection-request','lease-expired'):
     timeline.append(dict(cohort=cohort.name,case=folder.name,file=f.name,**e))
  for f in folder.glob('*.leaf-events.csv'):
   for e in read(f):
    if e['event']=='command-expired':timeline.append(dict(e,cohort=cohort.name,case=folder.name,file=f.name,role=e['owner'],value=e['source']))
  for f in folder.glob('central-*.transport.csv'):
   for e in read(f):
    if e['event']=='permission-limit':limits[e['decision']]=limits.get(e['decision'],0)+1
reg=[]
for f in sorted(a.raw.glob('*ctest.xml')):
 tests=ET.parse(f).getroot().findall('.//testcase');failed=[t.attrib['name'] for t in tests if t.find('failure') is not None];reg.append(dict(file=f.name,total=len(tests),passed=len(tests)-len(failed),failed=failed))
summary=dict(source=json.loads((a.raw/'identity.json').read_text())['source'],runtime_total=len(rows),runtime_pass=sum(x['raw_exit']==0 for x in rows),rows=rows,regression=reg,permission_limit_counts=limits,applied_profiles=profiles,acceptance=('Host FIFO Central-Front limited acceptance; Rear integration may proceed; no Rear implementation here' if len(rows)==12 and all(r['raw_exit']==0 and r['pass_observed'] and not r['sanitizer'] and not r['sdk_errors'] and not r['forced_cleanup'] for r in rows) and len(reg)==2 and all(x['total']==983 and not x['failed'] for x in reg) else 'NOT ACCEPTED: inspect raw failures/missing evidence'))
(a.output/'results-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
write('results.csv',rows,['cohort','case','source','raw_exit','pass_observed','normal_timing_ok','fault_protection_ok','sanitizer','sdk_errors','forced_cleanup','ip_packets'])
write('timeline.csv',sorted(timeline,key=lambda r:int(r['ns'])),['cohort','case','file','ns','event','epoch','role','value','deadline'])
write('renewal-margins.csv',margins,['cohort','case','owner','epoch','source','received','previous_expiry','margin_ns'])
# Small causal window, retaining exact trace fields and original acquisition time.
replay=[]
for name in ['legacy20','host10','host10-command-loss']:
 folder=a.raw/'replay-after/renewal'/name
 scenario='command-loss' if 'loss' in name else 'normal'
 base=folder/('logical-'+scenario)
 for e in read(Path(str(base)+'-transport.csv')):
  if 1980000000<=int(e['time_ns'])<=2020000000 and (e['stage'] in ['permission-limit','permission-issued','allocation-readiness','central-enqueued','zone-received','zone-leaf-enqueued','leaf-received','leaf-completed','central-result-accepted','gateway-protection']):replay.append(dict(profile=name,kind='transport',**e))
 for e in read(Path(str(base)+'-events.csv')):
  if 1980000000<=int(e['time_ns'])<=2020000000 and e['kind'] in ['valid-feedback','valid-input','command-expired','normal-authorized','coordinator-fault','local-protection']:
   replay.append(dict(profile=name,stage=e['kind'],original_source_ns=e['source_ns'],inner_deadline_ns=e['deadline_ns'],outcome=e['code'],**e))
write('replay-timeline.csv',sorted(replay,key=lambda r:(r['profile'],int(r['time_ns']))),['profile','kind','time_ns','stage','owner','peer','epoch','token','operation','original_source_ns','inner_deadline_ns','sent_ns','deadline_ns','result_source_ns','payload_source_ns','outcome'])
print(json.dumps(dict(runtime=len(rows),passed=summary['runtime_pass'],regression=reg,profile_readbacks=len(profiles))))
