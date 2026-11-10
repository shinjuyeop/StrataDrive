"""Frozen, read-only three-case development sensor/tag review."""
from pathlib import Path
import sys,json,hashlib,re,math
import numpy as np
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from physical_ai.perception.dataset import local_path
from quality_annotation import visible_boxes_v2,SEMANTICS_BY_CLASS
BASE=ROOT/'build/m10-model-diagnostics-v1';ANNEX=BASE/'mask-annex';DATA=ROOT/'build/m10-quality-v4g/development-01/dataset';DEV=ROOT/'build/m10-quality-v4g/development-data'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,value):
 with path.open('x') as stream:stream.write(json.dumps(value,indent=2)+'\n')
capture=DATA/'capture.json';assert sha(capture)=='e4cb5fbcc3e075582d0d252223f2872613223e9aa702089a19588b0630739667';c=json.loads(capture.read_text());assert c['partition']=='development' and c['phase']=='evaluation'
cases=[row for row in json.loads((BASE/'visual-cases.json').read_text())['cases'] if row['case'] in ['dfine-car-no-positive','dfine-person-no-positive','rtv4-person-no-positive']];assert len(cases)==3
names={int(value):name for name,value in re.findall(r'^\s+(\w+)\s*=\s*(\d+)u', (ANNEX/'ObjectLabel.h').read_text(),re.M)}
inputs={str(p.relative_to(ROOT)):sha(p) for p in [capture,DEV/'rgb.json',DEV/'evaluation-only-gt.json',BASE/'analysis.json',BASE/'visual-cases.json',ANNEX/'ObjectLabel.h',Path(__file__).resolve(),ROOT/'docs/test-plan/perception-model-diagnostics-v1-mask-annex.md']}
for case in cases:
 frame=next(f for f in c['frames'] if f['scene']==case['source']['scene']);assert frame['frame']==case['source']['frame'] and frame['source_ns']==case['source']['source_ns']
 for kind in ['rgb','instance']:
  p=local_path(DATA,frame[kind]['path']);assert sha(p)==frame[kind]['sha256'];inputs[str(p.relative_to(ROOT))]=sha(p)
freeze=ANNEX/'freeze.json'
if not freeze.exists():write(freeze,dict(schema='m10-diagnostic-mask-annex-freeze-v1',inputs=inputs,case_names=[case['case'] for case in cases],holdout_access=False,gt_modified=False))
else:assert json.loads(freeze.read_text())['inputs']==inputs
truth=json.loads((DEV/'evaluation-only-gt.json').read_text());rows=[]
for case in cases:
 row=case['source'];frame=next(f for f in c['frames'] if f['scene']==row['scene']);rgb=np.frombuffer(local_path(DATA,frame['rgb']['path']).read_bytes(),np.uint8).reshape(384,640,4)[:,:,2::-1].copy();assert hashlib.sha256(rgb.tobytes()).hexdigest()==row['rgb_sha256'];raw=local_path(DATA,frame['instance']['path']).read_bytes();included,excluded=visible_boxes_v2(raw);gt=next(f for f in truth['frames'] if f['scene']==row['scene']);assert included==gt['objects'] and excluded==gt['excluded']
 tags=np.frombuffer(raw,np.uint8).reshape(384,640,4)[:,:,2];box=row['prediction']['box'];roi=[max(0,math.floor(box[0])),max(0,math.floor(box[1])),min(640,math.ceil(box[2])),min(384,math.ceil(box[3]))];region=tags[roi[1]:roi[3],roi[0]:roi[2]];values,counts=np.unique(region,return_counts=True);hist=[dict(tag=int(v),name=names.get(int(v),'unknown'),pixels=int(n),fraction=float(n/region.size)) for v,n in sorted(zip(values,counts),key=lambda p:-p[1])];target=SEMANTICS_BY_CLASS[row['class_id']];rows.append(dict(case=case['case'],model=case['model'],dataset='v4',scene=row['scene'],frame=row['frame'],rgb_sha256=row['rgb_sha256'],raw_rgb_sha256=frame['rgb']['sha256'],raw_instance_sha256=frame['instance']['sha256'],prediction=row['prediction'],roi=roi,roi_pixels=int(region.size),target_semantic_tags=list(target),target_semantic_pixels=int(np.isin(region,target).sum()),histogram=hist,full_frame_gt_reconstructed=True))
result=dict(status='PASS',freeze_sha256=sha(freeze),rows=rows,scope='Three deterministic development cases only; no relabeling or primary-score change',holdout_access=False,gt_modified=False,selection_modified=False)
output=ANNEX/'review.json'
if output.exists():assert json.loads(output.read_text())==result
else:write(output,result)
print(json.dumps(result,indent=2))
