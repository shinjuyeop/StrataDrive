"""Fresh extraction replay of domain data and official COCO masks; no models/server."""
from pathlib import Path
from unittest.mock import patch
import hashlib,json,runpy,sys,tarfile,tempfile
sys.path[:0]=['.','tests/integration/perception']
from audit_domain_v1 import audit
from physical_ai.perception.domain_data_v1 import write_json_new

def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def main(out,output=None):
 out=Path(out);sources=read(out/'sources.json')['files']
 for name,digest in sources.items():assert sha(name)==digest
 with tempfile.TemporaryDirectory(prefix='domain-archive-',dir='build') as temporary:
  extracted=Path(temporary).resolve()
  with tarfile.open(out/'sources.tar.gz','r:gz') as archive:
   assert set(archive.getnames())==set(sources);archive.extractall(extracted/'source',filter='data')
  for name,digest in sources.items():assert sha(extracted/'source'/name)==digest
  with tarfile.open(out/'experiment.tar.gz','r:gz') as archive:
   names=archive.getnames();assert len(names)==len(set(names))
   assert all(n.startswith('build/m10-domain-data-v1/') and '..' not in Path(n).parts and not n.endswith(('.onnx','.pt','.pth')) for n in names)
   archive.extractall(extracted,filter='data')
  root=extracted/'build/m10-domain-data-v1'
  rebuilt=audit(root);assert rebuilt==read(root/'experiment-audit.json')==read(out/'experiment-audit.json')
  print(json.dumps(dict(stage='raw/mask/PNG/COCO/split/coverage',status='PASS')),flush=True)
  captured=[]
  def capture(path,value):
   if Path(path)==root/'coco-api-check.json':captured.append(value)
   else:write_json_new(path,value)
  with patch('physical_ai.perception.domain_data_v1.write_json_new',side_effect=capture):runpy.run_path(str(root/'check-coco-api.py'),run_name='__main__')
  assert len(captured)==1 and captured[0]==read(root/'coco-api-check.json')==read(out/'coco-api-check.json')
  future=set(read('docs/test-plan/evidence/m10_quality_v6/future-evaluation-exclusion.json')['rgb_sha256'])
  for row in read(root/'capture-attempts.json'):
   assert sha(root/row['capture'])==row['capture_sha256'];future.update(row['rgb_sha256'])
  assert sorted(future)==read(root/'future-evaluation-exclusion.json')['rgb_sha256']==read(out/'future-evaluation-exclusion.json')['rgb_sha256'] and len(future)==2717+176+rebuilt["collection_frames"]
  report=dict(schema='m10-domain-archive-recheck-v1',status='PASS',experiment_sha256=sha(out/'experiment.tar.gz'),sources_sha256=sha(out/'sources.tar.gz'),source_files=len(sources),
   raw_pairs=176+rebuilt["collection_frames"],preflight_pairs=176,development_frames=rebuilt["collection_frames"],train_frames=rebuilt["train_frames"],validation_frames=267,prior_excluded=2717,future_excluded=len(future),
   raw_mask_png_coco_split_coverage_replay='PASS',official_coco_api_replay='PASS',original_startup_and_coverage_failures_preserved=True,
   quality_holdout_collected=False,model_training=False,model_inference=False,runtime_promotion=False,
   scope='Fresh archive extraction and offline raw/label/export replay; no model accuracy/live20Hz/vehicle acceptance')
 target=Path(output) if output else out/'archive-recheck.json';write_json_new(target,report)
 if output is None:
  with (out/'SHA256SUMS').open('a') as f:f.write(sha(target)+'  archive-recheck.json\n')
 print(json.dumps(report),flush=True)
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'docs/test-plan/evidence/m10_domain_data_v1',sys.argv[2] if len(sys.argv)>2 else None)
