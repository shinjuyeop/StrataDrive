from pathlib import Path
import sys,json,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageOps
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from physical_ai.perception.dataset import RgbDataset
BASE=ROOT/'build/m10-model-diagnostics-v1';report=json.loads((BASE/'analysis.json').read_text());v2=json.loads((ROOT/'build/m10-model-screen-v2/freeze.json').read_text())
def group(model):return report['candidates'][model]['groups']['calibration']
def identity(r):return (r['dataset'],r['scene'],r.get('prediction_index',r.get('gt_index',0)))
def high(rows):return min(rows,key=lambda r:(-r['prediction']['score'],identity(r)))
cases=[('dfine-car-no-positive', 'dfine-m',high([r for r in group('dfine-m')['false_positives'] if r['class_id']==2 and r['bucket']=='no_positive_iou_ge_0p1'])),('dfine-person-no-positive','dfine-m',high([r for r in group('dfine-m')['false_positives'] if r['class_id']==0 and r['bucket']=='no_positive_iou_ge_0p1'])),('rtv4-person-no-positive','rtv4-s',high([r for r in group('rtv4-s')['false_positives'] if r['class_id']==0 and r['bucket']=='no_positive_iou_ge_0p1']))]
bikes=[r for r in group('rtv4-s')['false_negatives'] if r['class_id']==1 and r['bucket']=='below_selected_confidence'];median=float(np.median([r['max_same_class_support_score'] for r in bikes]));cases.append(('rtv4-bicycle-below-threshold','rtv4-s',min(bikes,key=lambda r:(abs(r['max_same_class_support_score']-median),identity(r)))))
riders=[r for r in group('rtv4-s')['false_negatives'] if r['person_kind']=='rider13' and r['bucket']=='below_selected_confidence'];cases.append(('rtv4-rider-below-threshold','rtv4-s',min(riders,key=lambda r:(-r['max_same_class_support_score'],identity(r)))))
cases.append(('dfine-rider-localization','dfine-m',min([r for r in group('dfine-m')['false_negatives'] if r['bucket']=='same_class_localization_overlap'],key=identity)))
manifest=[]
for name,model,row in cases:
 data=ROOT/v2['datasets']['calibration'][row['dataset']]['path'];rgb=RgbDataset(data/'rgb.json');source,frame=next((s,f) for s,f in rgb.frames() if s['scene']==row['scene']);assert source['rgb_sha256']==row['rgb_sha256'];truth=next(g for g in json.loads((data/'evaluation-only-gt.json').read_text())['frames'] if g['scene']==row['scene']);run=json.loads((ROOT/'build/m10-model-screen-v2/runs'/model/'calibration/run.json').read_text());preds=next(r for r in run['rows'] if r['scene']==row['scene'])['predictions']['0.5']['detections'];original=Image.fromarray(np.frombuffer(frame.rgb,np.uint8).reshape(384,640,3));im=original.copy();draw=ImageDraw.Draw(im)
 for obj in truth['objects']:
  draw.rectangle(obj['box'],outline=(30,255,70),width=2);draw.text((obj['box'][0],obj['box'][1]-12),f"GT {obj['class_id']}",fill=(30,255,70),stroke_width=1,stroke_fill='black')
 for p in preds:draw.rectangle(p['box'],outline=(255,70,70),width=1)
 if 'prediction' in row:
  focus=row['prediction']['box'];draw.rectangle(focus,outline=(255,200,0),width=3);caption=f"FP class={row['class_id']} score={row['prediction']['score']:.4f}"
 else:
  focus=row['gt']['box'];proposal=row['highest_score_supported'] or row['best_same_class'];draw.rectangle(proposal['box'],outline=(0,220,255),width=2);caption=f"FN class={row['class_id']} bestIoU={row['max_same_class_iou']:.3f} supportScore={row['max_same_class_support_score']}"
 side=max(96,max(focus[2]-focus[0],focus[3]-focus[1])+48);cx=(focus[0]+focus[2])/2;cy=(focus[1]+focus[3])/2;crop=(max(0,int(cx-side/2)),max(0,int(cy-side/2)),min(640,int(cx+side/2)),min(384,int(cy+side/2)))
 panel=Image.new('RGB',(1280,450),(22,26,34));panel.paste(im,(0,66));zoom=ImageOps.contain(im.crop(crop),(384,384),Image.Resampling.NEAREST);panel.paste(zoom,(650,66));d=ImageDraw.Draw(panel);d.text((8,8),f'{name} | {model} | {row["dataset"]} {row["scene"]}',fill='white');d.text((8,26),caption,fill='white');d.text((8,44),'GREEN=GT RED=published YELLOW=focus FP CYAN=native same-class proposal | RIGHT=display-only zoom',fill=(190,210,230));path=BASE/(name+'.png');panel.save(path);manifest.append(dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),case=name,model=model,source=row,crop=list(crop),display_only_zoom=True))
(BASE/'visual-cases.json').write_text(json.dumps(dict(status='PASS',analysis_sha256=hashlib.sha256((BASE/'analysis.json').read_bytes()).hexdigest(),cases=manifest,selection_modified=False,gt_modified=False,holdout_access=False),indent=2)+'\n')
