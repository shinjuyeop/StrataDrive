from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,shutil,subprocess,sys
sys.path[:0]=['.','tests/integration/perception']
from prepare_road_v8 import prepare
from review_quality_road_v4 import review
from quality_road_v8 import SURVEY
root=Path(__file__).parent
old=json.loads(Path('build/m10-quality-v7/preparation-freeze.json').read_text())
files=[name.replace('v7','v8') for name in old['sources']]
files=[name.replace('profiles/perception-quality-plan-v3.json','profiles/perception-quality-template-v8.json') for name in files]
files += [str(SURVEY.relative_to(Path.cwd())), 'tests/integration/perception/carla_quality_layout_v8.py', 'tests/integration/perception/review_quality_road_v4.py',str((root/'capture-preparation.py').relative_to(Path.cwd()))]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
snapshot=dict(schema='m10-road-preparation-freeze-v8',revision='new-Town04-v8-same-staging-v5b',created_utc=datetime.now(timezone.utc).isoformat(),survey_sha256=sha(SURVEY),sources={name:sha(name) for name in files})
with (root/'preparation-freeze.json').open('x') as f:json.dump(snapshot,f,indent=2);f.write('\n')
for name in files:
 dest=root/'preparation-source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(name,dest)
runs={}
for part in ('development','holdout'):
 for attempt in (1,2):
  run=root/f'preparation-{part}-{attempt:02d}'
  args=['python3','tests/integration/perception/run_road_server_v8.py','--engine','/d/shin/stratadrive-tools/UnrealEngine_4.26','--source','/d/shin/stratadrive-tools/m7-source/carla-0.9.16','--python','/d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python','--output',str(run),'--stage','preparation','--plan','profiles/perception-road-preparation-v8.json','--partition',part]
  with (root/f'preparation-{part}-{attempt:02d}-capture.log').open('x') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT)
  server=json.loads((run/'server.json').read_text())
  print(json.dumps(dict(partition=part,attempt=attempt,status=server['status'],server_exit=server.get('server_exit'))),flush=True)
  if r.returncode==0:break
  assert attempt==1 and any(x in server.get('error','') for x in ('RPC port readiness','readiness failed')),'Only a same-budget startup retry is automatic'
 else:raise RuntimeError('preparation capture failed')
 assert server['status']=='PASS'
 runs[part]=run.name
 (root/'preparation-runs.json').write_text(json.dumps(runs,indent=2)+'\n')
 with (root/f'preparation-{part}-review.log').open('x') as log:
  result=prepare(run/'dataset/capture.json',Path('profiles/perception-road-preparation-v8.json'),Path('profiles/perception-quality-exclusion-v8.json'),root/f'preparation-{part}-data')
  print(json.dumps(result),file=log);print(json.dumps(review(root/f'preparation-{part}-data',root,'preparation-'+part)),file=log)
 assert result['status']=='PASS'
 print(json.dumps(dict(partition=part,frames=99,gates=result['gates'])),flush=True)
