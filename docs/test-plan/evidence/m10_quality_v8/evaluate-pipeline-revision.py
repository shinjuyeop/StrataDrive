from pathlib import Path
import json,subprocess,sys,shutil,time
sys.path[:0]=['.','tests/integration/perception']
from quality_v8_common import freeze
root=Path(__file__).parent
python='build/m10-perception/cuda-venv/bin/python'
def step(label,args):
 print(json.dumps(dict(step=label,status='STARTED')),flush=True)
 with (root/f'{label}.log').open('x') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT)
 assert r.returncode==0,(label,r.returncode)
 print(json.dumps(dict(step=label,status='PASS')),flush=True)
# The marker is created only after both actual model-free preparations and manual panel review.
end=time.monotonic()+1200
while not (root/'preparation-reviewed.flag').exists():
 assert time.monotonic()<end,'Preparation review deadline';time.sleep(.5)
step('initial-preparation-audit',['python3',str(root/'audit-initial-preparation.py')])
step('seal-preparation',['python3',str(root/'seal-preparation.py')])
step('model-check',[python,'tests/integration/perception/check_quality_models_v8.py',str(root/'preparation-development-data/rgb.json'),'build/m10-quality-v6-design/upstream/yolox_l.onnx','build/m10-perception/yolox.onnx',str(root/'model-check.json')])
step('python-before-freeze',[python,'-m','unittest','discover','-s','tests/integration/perception','-p','test_*.py'])
step('component-checks',['python3',str(root/'run-component-checks.py')])
result=freeze(root/'experiment-freeze.json')
for name in result['sources']:
 dest=root/'frozen-source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(name,dest)
for label,source in [('plan','profiles/perception-road-evaluation-v8b.json'),('protocol','profiles/perception-quality-protocol-v8.json')]:shutil.copy2(source,root/f'{label}-before-capture.json')
print(json.dumps(dict(step='freeze',sources=len(result['sources']),status='PASS')),flush=True)
runs={}
for part in ('development','holdout'):
 for attempt in (1,2):
  run=root/f'{part}-{attempt:02d}'
  args=['python3','tests/integration/perception/run_quality_evaluation_v8.py','--engine','/d/shin/stratadrive-tools/UnrealEngine_4.26','--source','/d/shin/stratadrive-tools/m7-source/carla-0.9.16','--python','/d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python','--output',str(run),'--plan','profiles/perception-road-evaluation-v8b.json','--partition',part,'--freeze',str(root/'experiment-freeze.json')]
  if part=='holdout':args+=['--selection',str(root/'candidate-selection.json')]
  with (root/f'{part}-{attempt:02d}-capture.log').open('x') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT)
  server=json.loads((run/'server.json').read_text())
  print(json.dumps(dict(step='capture',partition=part,attempt=attempt,status=server['status'])),flush=True)
  if r.returncode==0:break
  assert attempt==1 and any(x in server.get('error','') for x in ('RPC port readiness','readiness failed')),'Only a same-budget startup retry is automatic'
 assert server['status']=='PASS'
 runs[part]=run.name;(root/'evaluation-runs.json').write_text(json.dumps(runs,indent=2)+'\n')
 step(f'{part}-prepare-review',['python3',str(root/'prepare-evaluation.py'),part])
 step(f'{part}-models',[python,str(root/'run-partition.py'),part])
 step(f'{part}-errors',['python3',str(root/'diagnose-errors.py'),part])
step('experiment-audit',['python3','tests/integration/perception/audit_quality_v8.py',str(root),str(root/'experiment-audit.json')])
print(json.dumps(dict(step='quality_evaluation_complete',eligible_for_runtime_review=json.loads((root/'experiment-audit.json').read_text())['eligible_for_runtime_review'])),flush=True)
