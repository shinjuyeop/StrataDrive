from pathlib import Path
import importlib,json,subprocess,sys,types,gc
root=Path('/d/shin/StrataDrive');out=root/'build/pre-m8-refactor'
sys.path.insert(0,str(root/'tests/integration/carla'))
def old(name):
 path=root/'tests/integration/carla'/f'{name}.py'
 mod=types.ModuleType('before_'+name);mod.__file__=str(path)
 source=subprocess.check_output(['git','show','b8b5f6a:tests/integration/carla/'+name+'.py'],text=True)
 exec(compile(source,str(path),'exec'),mod.__dict__);return mod
results=[]
def compare(name,path,*args):
 before=old(name);after=importlib.import_module(name)
 a=before.audit(path,*args);gc.collect();b=after.audit(path,*args)
 assert a==b,(name,path,a,b)
 results.append({'auditor':name,'case':str(path),'identical':True,'status':b.get('status')});print(name,path.name,'identical',flush=True)
 (out/'audit-equivalence.json').write_text(json.dumps(results,indent=2)+'\n')
hv=root/'docs/test-plan/evidence/m7_carla_wall_guard/carla-runtime/hv-budget-v1/runs'
for i in range(1,5):compare('audit_m7_wall_carla',hv/f'run{i:02}')
for i in (10,11):compare('audit_m7_wall_carla',root/'docs/test-plan/evidence/m7_carla_wall_guard/carla-runtime/nonvideo-wall5/runs'/f'run{i:02}')
sim=Path('/d/shin/stratadrive-tools/m7-source/m7-simulation-time/suite-a')
for case in ('continuous','continuous-cameras','protected-sleep','rgb-drop','snapshot-stop','work-missing','native-stall'):compare('audit_m7_simulation',sim/case,case)
for case in ('continuous','continuous-cameras','protected-sleep','rgb-drop'):compare('audit_m7_integrated',sim/case)
before=old('audit_m7_closeout');after=importlib.import_module('audit_m7_closeout')
p=Path('/d/shin/stratadrive-tools/m7-source/m7-batch-close/suite-v3/protected-sleep')
a=before.load_rows(p);b=after.load_rows(p);assert a==b
for fun in ('natural_stop','clock_evidence'):
 assert getattr(before,fun)(a)==getattr(after,fun)(b)
 results.append({'auditor':'audit_m7_closeout','case':fun,'identical':True})
(out/'audit-equivalence.json').write_text(json.dumps(results,indent=2)+'\n')
print('all',len(results),'identical',flush=True)
