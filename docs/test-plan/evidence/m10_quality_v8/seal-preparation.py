from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys,numpy as np
sys.path[:0]=['.','tests/integration/perception']
from quality_benchmark import write_new
from audit_quality_v8 import audit_preparation
root=Path(__file__).parent
result=audit_preparation(root,dict(created_utc=datetime.now(timezone.utc).isoformat()))
write_new(root/'preparation-raw-audit.json',result)
prior=set(json.loads(Path('profiles/perception-quality-exclusion-v8.json').read_text())['rgb_sha256']);all_hashes=set(prior);rows=[]
for cap_path in sorted(root.glob('preparation-*/dataset/capture.json')):
 cap=json.loads(cap_path.read_text());hashes=[]
 for row in cap['frames']:
  p=cap_path.parent/row['rgb']['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==row['rgb']['sha256']
  raw=np.frombuffer(p.read_bytes(),np.uint8).reshape(384,640,4);hashes.append(hashlib.sha256(raw[:,:,[2,1,0]].copy().tobytes()).hexdigest())
 rows.append(dict(capture=str(cap_path),capture_sha256=hashlib.sha256(cap_path.read_bytes()).hexdigest(),status=cap['status'],rgb_sha256=hashes));all_hashes.update(hashes)
value=dict(schema='m10-quality-evaluation-exclusion-v8',rgb_sha256=sorted(all_hashes),base_rgb=4333,preparation_attempts=rows,scope='All consumed V1-V7/domain/training and all complete/partial V8 preparation RGB excluded')
Path('profiles/perception-quality-evaluation-exclusion-v8.json').write_text(json.dumps(value,indent=2)+'\n')
p=Path('profiles/perception-quality-protocol-v8.json');v=json.loads(p.read_text());v['prior_rgb_excluded']=len(all_hashes);p.write_text(json.dumps(v,indent=2)+'\n')
print(json.dumps(dict(raw_replay='PASS',prior=len(prior),preparation_pairs=sum(len(r['rgb_sha256']) for r in rows),total_excluded=len(all_hashes))),flush=True)
