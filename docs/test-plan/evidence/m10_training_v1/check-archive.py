"""Fresh source/model/data-export extraction; score/tensor and CPU numeric replay."""
from pathlib import Path
import hashlib,json,sys,tarfile,tempfile
sys.path[:0]=['.','tests/integration/perception']
from audit_training_v1 import audit
from check_training_v1 import check
from physical_ai.perception.domain_data_v1 import write_json_new

def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main(out,output=None):
 out=Path(out);source=read(out/'sources.json')['files']
 for name,digest in source.items():assert sha(name)==digest
 dependency=read(out/'input-data.json');data_evidence=Path('docs/test-plan/evidence/m10_domain_data_v1')
 assert sha(data_evidence/'experiment.tar.gz')==dependency['experiment_sha256']
 with tempfile.TemporaryDirectory(prefix='m10-training-archive-',dir='build') as temporary:
  extracted=Path(temporary).resolve()
  with tarfile.open(out/'sources.tar.gz','r:gz') as archive:
   assert set(archive.getnames())==set(source);archive.extractall(extracted/'source',filter='data')
  for name,digest in source.items():assert sha(extracted/'source'/name)==digest
  with tarfile.open(out/'experiment.tar.gz','r:gz') as archive:
   names=archive.getnames();assert len(names)==len(set(names))
   assert all(n.startswith('build/m10-training-v1/') and '..' not in Path(n).parts and m.isfile() for n,m in zip(names,archive.getmembers()))
   expected_models={'build/m10-training-v1/upstream/yolox_l.pth','build/m10-training-v1/run-01/best.pth','build/m10-training-v1/run-01/last.pth','build/m10-training-v1/export/model.onnx'}
   assert {n for n in names if n.endswith(('.pth','.pt','.onnx'))}==expected_models
   archive.extractall(extracted,filter='data')
  with tarfile.open(data_evidence/'experiment.tar.gz','r:gz') as archive:
   members=[m for m in archive.getmembers() if m.name.startswith('build/m10-domain-data-v1/export/')]
   assert all(m.isfile() and '..' not in Path(m.name).parts for m in members)
   archive.extractall(extracted,members=members,filter='data')
  root=extracted/'build/m10-training-v1';data=extracted/'build/m10-domain-data-v1/export'
  rebuilt=audit(root,data)
  assert rebuilt==read(root/'experiment-audit.json')==read(out/'experiment-audit.json')
  print(json.dumps(dict(stage='all_scores/selection/strict_tensors/BN',status='PASS')),flush=True)
  check(root/'export',data,root/'archive-numeric-cpu.json','cpu')
  assert read(root/'archive-numeric-cpu.json')==read(root/'numeric-cpu.json')
  assert read(root/'archive-numeric-cpu.predictions.json')==read(root/'numeric-cpu.predictions.json')
  report=dict(schema='m10-training-archive-recheck-v1',status='PASS',experiment_sha256=sha(out/'experiment.tar.gz'),
   sources_sha256=sha(out/'sources.tar.gz'),source_files=len(source),train_images=813,validation_images=267,
   epochs=24,optimizer_steps=4896,selected_epoch=rebuilt['selected_epoch'],frozen_sources=rebuilt['frozen_sources'],
   scores_selection_retained_tensor_and_BN_replay='PASS',onnx_opencv_raw_and_complete_detection_replay='PASS',
   onnx_cpu_all_validation_reinference='PASS',new_raw_frames=0,future_rgb_excluded=3973,
   quality_holdout_read=False,runtime_promotion=False,training_backprop_repeated=False,
   scope='Fresh extraction, full score/selection, retained tensor and independent CPU numeric replay; no training rerun or quality holdout acceptance')
 target=Path(output) if output else out/'archive-recheck.json';write_json_new(target,report)
 if output is None:
  with (out/'SHA256SUMS').open('a') as f:f.write(sha(target)+'  archive-recheck.json\n')
 print(json.dumps(report),flush=True)
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'docs/test-plan/evidence/m10_training_v1',sys.argv[2] if len(sys.argv)>2 else None)
