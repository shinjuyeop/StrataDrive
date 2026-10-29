import copy,csv,io,json,sys
from pathlib import Path
sys.path.insert(0,'/d/shin/StrataDrive/tests/integration/carla')
import audit_m7_wall_carla as a
p=Path('/d/shin/stratadrive-tools/m7-source/m7-wall-stabilize/run06')
original=a.read
baseline=a.audit(p)
assert baseline['status']=='PASS_CASE_ONLY'
ingress=json.loads(original(p/'ingress.json'));report=json.loads(original(p/'result.json'))
lines=original(p/'trace.jsonl').splitlines();jobs=list(csv.DictReader(original(p/'native-wall.csv').splitlines()))
normal=next(i for i,x in enumerate(lines) if json.loads(x)['receipt']['original_actual']['native']['normal'])
protect=next(i for i,x in enumerate(lines) if json.loads(x)['receipt']['original_actual']['admitted_actual']['protection'])
changes=[]
bad=copy.deepcopy(ingress);pkt=bad[1]['ingress']['actual'][0];bad[1]['ingress']['actual'][0]=pkt[:-2]+('00' if pkt[-2:]!='00' else '01');changes.append(('ingress_crc','ingress.json',json.dumps(bad)))
bad=copy.deepcopy(ingress);bad[1]['ingress']['at_ns']=str(int(bad[-1]['ingress']['at_ns'])+1000000000);changes.append(('ingress_future','ingress.json',json.dumps(bad)))
bad=copy.deepcopy(ingress);del bad[1];changes.append(('missing_ingress','ingress.json',json.dumps(bad)))
bad=copy.deepcopy(report);bad['model_step_ns']=10000000;changes.append(('mixed_step','result.json',json.dumps(bad)))
bad=copy.deepcopy(report);bad['writer_checks']['batch_denied']=False;changes.append(('writer_not_denied','result.json',json.dumps(bad)))
bad=copy.deepcopy(report);bad['native_exit']=1;changes.append(('native_exit_failure','result.json',json.dumps(bad)))
bad=copy.deepcopy(jobs);row=next(x for x in bad if int(x['end_ns']));row['end_ns']=str(int(row['deadline_ns'])+1)
f=io.StringIO();w=csv.DictWriter(f,fieldnames=bad[0]);w.writeheader();w.writerows(bad);changes.append(('owner_late','native-wall.csv',f.getvalue()))
def changed_line(name,index,mutate):
 bad=json.loads(lines[index]);mutate(bad);ls=list(lines);ls[index]=json.dumps(bad,separators=(',',':'));changes.append((name,'trace.jsonl','\n'.join(ls)+'\n'))
old=json.loads(lines[normal])['receipt']['original_actual']['native']['actual'][0]
changed_line('applied_without_latest_ingress',protect,lambda r:r['receipt']['original_actual']['native']['actual'].__setitem__(0,old))
changed_line('solver_dt',normal,lambda r:r['raw_solver']['trace']['steps'][0].update(dt_s=.01))
row=json.loads(lines[normal]);drive=a.frame(a.wire(row['receipt']['original_actual']['native']['actual'][2],1,7,9),2,True)
used=next(i for i,x in enumerate(lines) if int(json.loads(x)['receipt']['physics_acquisition_begin_ns'])==drive['wheel_source'])
changed_line('acquisition_restamp',used,lambda r:r['receipt'].update(physics_acquisition_begin_ns=str(int(r['receipt']['physics_acquisition_begin_ns'])+1)))
results=[]
for name,file,data in changes:
 a.read=lambda path,file=file,data=data:data if path==p/file else original(path)
 try:
  r=a.audit(p);ok=r['status']!='PASS_CASE_ONLY';reason=r['status']
 except (ValueError,KeyError,IndexError) as e:ok=True;reason=str(e)
 results.append(dict(name=name,rejected=ok,reason=reason));print(name,ok,reason,flush=True)
a.read=original
out={'scope':'independent auditor corruption checks; unchanged original run06','baseline':baseline['status'],'checks':results}
(p.parent/'audit-corruptions.json').write_text(json.dumps(out,indent=2)+'\n')
assert all(x['rejected'] for x in results)
