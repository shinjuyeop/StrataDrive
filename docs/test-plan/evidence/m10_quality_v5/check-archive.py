"""Extract V5 published archives into a fresh directory and replay without a model/server."""
from pathlib import Path
from collections import Counter
from unittest.mock import patch
import hashlib,json,runpy,sys,tarfile,tempfile
sys.path[:0]=['.','tests/integration/perception']
from audit_quality_v5 import audit
from physical_ai.perception.dataset import RgbDataset

def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def write(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')

def main(out):
 out=Path(out);sources=read(out/'sources.json')['files']
 for name,digest in sources.items():assert sha(name)==digest
 with tempfile.TemporaryDirectory(prefix='m10-v5-archive-',dir='build') as temporary:
  extracted=Path(temporary).resolve()
  with tarfile.open(out/'sources.tar.gz','r:gz') as archive:
   assert set(archive.getnames())==set(sources)
   archive.extractall(extracted/'source',filter='data')
  for name,digest in sources.items():assert sha(extracted/'source'/name)==digest
  with tarfile.open(out/'experiment.tar.gz','r:gz') as archive:
   names=archive.getnames();assert len(names)==len(set(names))
   assert all(n.startswith('build/') and not n.startswith('/') and '..' not in Path(n).parts for n in names)
   archive.extractall(extracted,filter='data')
  root=extracted/'build/m10-quality-v5b'
  for name,digest in read(root/'experiment-freeze.json')['sources'].items():assert sha(root/'frozen-source'/name)==digest
  rebuilt=audit(root)
  assert rebuilt==read(out/'experiment-audit.json')==read(root/'experiment-audit.json')
  print(json.dumps(dict(stage='raw/score/nomination/order audit',status='PASS')),flush=True)
  captured=[]
  from quality_benchmark import write_new as original_write
  def capture_history(path,value):
   if Path(path)==root/'history-audit.json':captured.append(value)
   else:original_write(path,value)
  with patch('quality_benchmark.write_new',side_effect=capture_history):
   runpy.run_path(str(root/'audit-history.py'),run_name='__main__')
  assert len(captured)==1 and captured[0]==read(root/'history-audit.json')==read(out/'history-audit.json')
  future=set(read('profiles/perception-quality-evaluation-exclusion-v5.json')['rgb_sha256'])
  for part in ('development','holdout'):
   future.update(f['rgb_sha256'] for f in read(root/f'{part}-data/rgb.json')['frames'])
  descriptor=read(out/'future-evaluation-exclusion.json')
  assert sorted(future)==descriptor['rgb_sha256'] and len(future)==2357
  assert descriptor['current_freeze_sha256']==sha(root/'experiment-freeze.json')
  assert descriptor['current_selection_sha256']==sha(root/'candidate-selection.json')
  diagnostic=read(root/'selected-view-diagnostic.json')
  assert diagnostic==read(out/'selected-view-diagnostic.json')
  assert diagnostic['original_run_sha256']==sha(root/'holdout-medium-consensus-v5/result.json')
  assert diagnostic['same_selected_outputs_within_tolerance'] and diagnostic['quality_scores_unchanged'] and not diagnostic['renomination']
  reasons=Counter();classes={}
  for row in diagnostic['records']:
   for cause in row['reasons']:
    reason=cause['reason'];reasons[reason]+=1;classes.setdefault(reason,Counter())[str(row['gt']['class_id'])]+=1
  assert dict(reasons)==diagnostic['observed_rejections']=={'crop_weak_semantic_support':15,'exclusive_body_suppression':3}
  assert dict(classes['crop_weak_semantic_support'])=={'0':6,'1':5,'3':4}
  assert dict(classes['exclusive_body_suppression'])=={'1':2,'7':1}
  # RGB hashes/layout are checked by the raw auditor; independently exercise reader paths after relocation.
  for part in ('development','holdout'):
   assert len(list(RgbDataset(root/f'{part}-data/rgb.json').frames()))==81
  acceptance=read(out/'acceptance.json')
  assert not acceptance['eligible_for_runtime_review'] and not acceptance['runtime_promotion']
  report=dict(schema='m10-quality-v5-archive-recheck',status='PASS',experiment_sha256=sha(out/'experiment.tar.gz'),
   sources_sha256=sha(out/'sources.tar.gz'),source_files=len(sources),frozen_sources=127,preparation_source_files=13,
   final_preparation_raw_pairs=198,final_evaluation_raw_pairs=162,all_preparation_attempt_pairs=322,
   total_new_raw_pairs=484,design_rounds=2,design_samples_consumed=81,prior_rgb_excluded=2195,future_rgb_excluded=2357,
   raw_rgb_gt_road_visibility_seal_replay='PASS',strict_score_nomination_order_replay='PASS',
   original_history_and_failures_replay='PASS',relocated_rgb_reader='PASS',selected_diagnostic_consistency='PASS',
   eligible_for_runtime_review=False,runtime_promotion=False,
   scope='Fresh archive extraction and CPU-only raw/score/history replay; no new simulator or model inference; quality failure unchanged')
 write(out/'archive-recheck.json',report)
 with (out/'SHA256SUMS').open('a') as f:f.write(sha(out/'archive-recheck.json')+'  archive-recheck.json\n')
 print(json.dumps(report),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]) if len(sys.argv)>1 else Path('docs/test-plan/evidence/m10_quality_v5'))
