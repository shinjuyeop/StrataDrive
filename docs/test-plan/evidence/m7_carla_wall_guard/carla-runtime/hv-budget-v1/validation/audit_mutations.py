from pathlib import Path
import csv,io,json,subprocess,sys,tempfile
root=Path('/d/shin/StrataDrive');work=Path(__file__).resolve().parent
source=work/'run01';summary=[]
for name in ('unknown_budget','mismatched_budget','hidden_policy','restamped_source','restamped_dependency','strict30_counterfactual'):
 with tempfile.TemporaryDirectory(prefix='strata-hv-audit-') as tmp:
  d=Path(tmp)
  for p in source.iterdir():
   if p.is_file() and p.name!='audit.json':(d/p.name).symlink_to(p.resolve())
  def put(filename,value):
   p=d/filename
   if p.is_symlink():p.unlink()
   p.write_text(value)
  r=json.loads((source/'result.json').read_text());m=json.loads((source/'native.json').read_text())
  if name=='unknown_budget':r['hv_dependency_ns']=40000000
  if name=='mismatched_budget':m['hv_dependency_ns']=30000000
  if name=='hidden_policy':del r['hv_dependency_ns']
  if name=='strict30_counterfactual':
   r['hv_dependency_ns']=m['hv_dependency_ns']=r['native_initial']['hv_dependency_ns']=30000000
  if name.startswith('restamped_'):
   rows=list(csv.DictReader((source/'native.csv').open()));column='hv_source' if name.endswith('source') else 'hv_dependency'
   first=next(x for x in rows if int(x['hv_source']));first[column]=str(int(first[column])+1)
   out=io.StringIO();writer=csv.DictWriter(out,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows);put('native.csv',out.getvalue())
  put('result.json',json.dumps(r));put('native.json',json.dumps(m))
  a=subprocess.run([sys.executable,str(root/'tests/integration/carla/audit_m7_wall_carla.py'),str(d),'--output',str(d/'audit.json')],capture_output=True,text=True)
  result=json.loads((d/'audit.json').read_text());assert a.returncode!=0 and result['status']=='FAIL_AUDIT',(name,result)
  summary.append(dict(case=name,exit=a.returncode,result=result));print(name,result['error'],flush=True)
(work/'audit-mutations.json').write_text(json.dumps(summary,indent=2)+'\n')
