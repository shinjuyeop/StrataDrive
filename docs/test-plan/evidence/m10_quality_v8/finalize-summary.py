from pathlib import Path
import json,hashlib,numpy as np
root=Path(__file__).parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
audit=read(root/'experiment-audit.json');frozen=read(root/'experiment-freeze.json');selection=read(root/'candidate-selection.json')
prior=set(read('profiles/perception-quality-exclusion-v8.json')['rgb_sha256']);all_hashes=set(prior);attempts=[]
for server_path in sorted(root.glob('*/server.json')):
 server=read(server_path);path=server_path.parent/'dataset/capture.json';hashes=[]
 if path.exists():
  cap=read(path)
  for row in cap['frames']:
   p=path.parent/row['rgb']['path'];assert sha(p)==row['rgb']['sha256'];raw=np.frombuffer(p.read_bytes(),np.uint8).reshape(384,640,4)
   digest=hashlib.sha256(raw[:,:,[2,1,0]].copy().tobytes()).hexdigest();hashes.append(digest)
  all_hashes.update(hashes)
 attempts.append(dict(run=server_path.parent.name,stage=server['stage'],status=server['status'],server_exit=server.get('server_exit'),
  forced_stop=server.get('forced_stop',False),wall_seconds=server['elapsed_wall_seconds'],frames=len(hashes),
  capture=str(path.relative_to(root)) if path.exists() else None,capture_sha256=sha(path) if path.exists() else None,rgb_sha256=hashes))
assert len(prior)==4333
value=dict(schema='m10-future-evaluation-exclusion-v8',rgb_sha256=sorted(all_hashes),prior_rgb=4333,current_freeze_sha256=sha(root/'experiment-freeze.json'),current_selection_sha256=sha(root/'candidate-selection.json'),scope='All consumed V1-V7/domain/training plus every complete/partial V8 preparation/evaluation attempt; no reuse as fresh quality holdout')
(root/'future-evaluation-exclusion.json').write_text(json.dumps(value,indent=2)+'\n');(root/'capture-attempts.json').write_text(json.dumps(attempts,indent=2)+'\n')
summary=dict(schema='m10-quality-v8-summary',prior_rgb=4333,preparation_excluded=read('profiles/perception-quality-protocol-v8.json')['prior_rgb_excluded'],future_rgb=len(all_hashes),
 new_raw_pairs=sum(x['frames'] for x in attempts),preparation_frames=198,evaluation_frames=162,selected=selection['selected'],eligible_for_runtime_review=audit['eligible_for_runtime_review'],runtime_promotion=False,
 development={c:read(root/f'development-{c}-score.json')['micro'] for c in ('baseline','large-v8')},holdout={c:read(root/f'holdout-{c}-score.json')['micro'] for c in ('baseline','large-v8')})
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
