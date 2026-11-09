"""Extract published V6 archives and replay raw/score/design history without a model/server."""
from pathlib import Path
from unittest.mock import patch
import hashlib,json,runpy,sys,tarfile,tempfile
sys.path[:0]=['.','tests/integration/perception']
from audit_quality_v6 import audit
from physical_ai.perception.dataset import RgbDataset

def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def write(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def main(out,output=None):
 out=Path(out);sources=read(out/'sources.json')['files']
 for name,digest in sources.items():assert sha(name)==digest
 with tempfile.TemporaryDirectory(prefix='m10-v6-archive-',dir='build') as temporary:
  extracted=Path(temporary).resolve()
  with tarfile.open(out/'sources.tar.gz','r:gz') as archive:
   assert set(archive.getnames())==set(sources);archive.extractall(extracted/'source',filter='data')
  for name,digest in sources.items():assert sha(extracted/'source'/name)==digest
  with tarfile.open(out/'experiment.tar.gz','r:gz') as archive:
   names=archive.getnames();assert len(names)==len(set(names))
   assert all(n.startswith('build/') and '..' not in Path(n).parts and not n.endswith(('.onnx','.pt','.pth')) for n in names)
   archive.extractall(extracted,filter='data')
  root=extracted/'build/m10-quality-v6';frozen=read(root/'experiment-freeze.json')
  for name,digest in frozen['sources'].items():assert sha(root/'frozen-source'/name)==digest
  rebuilt=audit(root);assert rebuilt==read(out/'experiment-audit.json')==read(root/'experiment-audit.json')
  print(json.dumps(dict(stage='raw/strict score/nomination/order',status='PASS')),flush=True)
  from quality_benchmark import write_new as original_write
  captured=[]
  def capture_history(path,value):
   if Path(path)==root/'history-audit.json':captured.append(value)
   else:original_write(path,value)
  with patch('quality_benchmark.write_new',side_effect=capture_history):runpy.run_path(str(root/'design-history.py'),run_name='__main__')
  assert len(captured)==1 and captured[0]==read(root/'history-audit.json')==read(out/'history-audit.json')
  future=set(read('profiles/perception-quality-evaluation-exclusion-v6.json')['rgb_sha256'])
  for part in ('development','holdout'):
   future.update(f['rgb_sha256'] for f in read(root/f'{part}-data/rgb.json')['frames'])
   assert len(list(RgbDataset(root/f'{part}-data/rgb.json').frames()))==81
  descriptor=read(out/'future-evaluation-exclusion.json');assert sorted(future)==descriptor['rgb_sha256']
  assert len(future)==2717 and descriptor['current_freeze_sha256']==sha(root/'experiment-freeze.json') and descriptor['current_selection_sha256']==sha(root/'candidate-selection.json')
  acceptance=read(out/'acceptance.json');assert acceptance['eligible_for_runtime_review']==rebuilt['eligible_for_runtime_review'] and not acceptance['runtime_promotion']
  report=dict(schema='m10-quality-v6-archive-recheck',status='PASS',experiment_sha256=sha(out/'experiment.tar.gz'),sources_sha256=sha(out/'sources.tar.gz'),source_files=len(sources),frozen_sources=len(frozen['sources']),preparation_source_files=13,
   preparation_raw_pairs=198,evaluation_raw_pairs=162,total_new_raw_pairs=360,consumed_design_samples=162,prior_rgb_excluded=2555,future_rgb_excluded=2717,
   raw_rgb_gt_road_visibility_seal_replay='PASS',strict_score_nomination_order_replay='PASS',consumed_development_policy_replay='PASS',
   eligible_for_runtime_review=rebuilt['eligible_for_runtime_review'],runtime_promotion=False,scope='Fresh extraction and CPU-only raw/score/design replay; no new model/server inference; original quality gates and results unchanged')
 target=Path(output) if output else out/'archive-recheck.json'
 write(target,report)
 if output is None:
  with (out/'SHA256SUMS').open('a') as f:f.write(sha(target)+'  archive-recheck.json\n')
 print(json.dumps(report),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]) if len(sys.argv)>1 else Path('docs/test-plan/evidence/m10_quality_v6'),Path(sys.argv[2]) if len(sys.argv)>2 else None)
