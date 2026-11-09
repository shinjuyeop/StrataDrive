"""Fresh archive extraction and CPU-only raw/strict-score/nomination/order replay."""
from pathlib import Path
import hashlib,json,sys,tarfile,tempfile
sys.path[:0]=['.','tests/integration/perception']
from audit_quality_v7 import audit
from physical_ai.perception.dataset import RgbDataset

def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def main(out,output=None):
 out=Path(out);sources=read(out/'sources.json')['files']
 for name,digest in sources.items():assert sha(name)==digest
 with tempfile.TemporaryDirectory(prefix='m10-v7-archive-',dir='build') as temporary:
  extracted=Path(temporary).resolve()
  with tarfile.open(out/'sources.tar.gz','r:gz') as archive:
   assert set(archive.getnames())==set(sources);archive.extractall(extracted/'source',filter='data')
  for name,digest in sources.items():assert sha(extracted/'source'/name)==digest
  with tarfile.open(out/'experiment.tar.gz','r:gz') as archive:
   names=archive.getnames();assert len(names)==len(set(names))
   assert all(n.startswith('build/m10-quality-v7/') and '..' not in Path(n).parts and not n.endswith(('.onnx','.pt','.pth')) for n in names)
   archive.extractall(extracted,filter='data')
  root=extracted/'build/m10-quality-v7';frozen=read(root/'experiment-freeze.json')
  for name,digest in frozen['sources'].items():assert sha(root/'frozen-source'/name)==digest
  rebuilt=audit(root);assert rebuilt==read(root/'experiment-audit.json')==read(out/'experiment-audit.json')
  prior=set(read('profiles/perception-quality-exclusion-v7.json')['rgb_sha256']);future=set(prior)
  for row in read(root/'capture-attempts.json'):
   if row['capture'] is None:assert row['frames']==0;continue
   assert sha(root/row['capture'])==row['capture_sha256'];future.update(row['rgb_sha256'])
  assert sorted(future)==read(root/'future-evaluation-exclusion.json')['rgb_sha256']==read(out/'future-evaluation-exclusion.json')['rgb_sha256'] and len(prior)==3973
  for part in ('development','holdout'):assert len(list(RgbDataset(root/f'{part}-data/rgb.json').frames()))==81
  recovery=read(root/'recovery-before-launch.json');assert read(out/'recovery-before-launch.json')==recovery
  from datetime import datetime
  assert recovery['source_freeze_sha256']==sha(root/'experiment-freeze.json') and recovery['protocol_sha256']==frozen['protocol_sha256']
  assert recovery['recovery_annex_sha256']==sha('docs/test-plan/perception-quality-v7-recovery.md')
  assert recovery['model_or_gate_changes'] is False and recovery['original_limits']==[180,900,30]
  assert datetime.fromisoformat(recovery['created_utc'])<datetime.fromisoformat(read(root/'development-03/server.json')['started_utc'])
  for run in ('development-01','development-02'):
   server=read(root/run/'server.json');assert server['status']=='FAIL' and server['server_exit']==-9 and server['forced_stop'] and not(root/run/'dataset/capture.json').exists()
  acceptance=read(out/'acceptance.json');assert acceptance['eligible_for_runtime_review']==rebuilt['eligible_for_runtime_review'] and not acceptance['runtime_promotion']
  report=dict(schema='m10-quality-v7-archive-recheck-v1',status='PASS',experiment_sha256=sha(out/'experiment.tar.gz'),sources_sha256=sha(out/'sources.tar.gz'),source_files=len(sources),frozen_sources=len(frozen['sources']),preparation_sources=14,
   preparation_raw_pairs=198,evaluation_raw_pairs=162,total_new_raw_pairs=sum(row['frames'] for row in read(root/'capture-attempts.json')),prior_rgb_excluded=3973,final_evaluation_rgb_excluded=read('profiles/perception-quality-protocol-v7.json')['prior_rgb_excluded'],future_rgb_excluded=len(future),
   raw_rgb_gt_road_visibility_seal_replay='PASS',strict_score_nomination_order_replay='PASS',original_two_startup_failures_and_recovery_preserved=True,
   eligible_for_runtime_review=rebuilt['eligible_for_runtime_review'],runtime_promotion=False,
   scope='Fresh extraction and CPU-only raw/score/nomination/order replay. Pinned trained model retained in prior training evidence. No new inference/live20Hz/vehicle acceptance')
 target=Path(output) if output else out/'archive-recheck.json';write(target,report)
 if output is None:
  with (out/'SHA256SUMS').open('a') as f:f.write(sha(target)+'  archive-recheck.json\n')
 print(json.dumps(report),flush=True)
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'docs/test-plan/evidence/m10_quality_v7',sys.argv[2] if len(sys.argv)>2 else None)
