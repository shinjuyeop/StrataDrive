"""Post-hoc error panels; predictions/GT and strict gates remain unchanged."""
from pathlib import Path
import json,sys
import cv2,numpy as np
sys.path[:0]=['.','tests/integration/perception']
from physical_ai.perception.dataset import read_json,RgbDataset
from physical_ai.perception.contract import CLASSES
root=Path(__file__).parent
nominee=read_json(root/'candidate-selection.json')['selected']
errors=read_json(root/f'holdout-{nominee}-errors.json')['records']
selected=[];seen=set()
for row in errors:
 gt=row['best_visible_gt'];key=(gt['class_id'],row['prediction']['class_id']) if gt else None
 if row['reason']=='class_confusion' and key not in seen:
  selected.append(row);seen.add(key)
images={s['scene']:np.frombuffer(frame.rgb,np.uint8).reshape(384,640,3) for s,frame in RgbDataset(root/'holdout-data/rgb.json').frames()}
panels=[]
for row in selected:
 gt=row['best_visible_gt'];pred=row['prediction'];box=gt['box']
 x=max(0,min(440,round((box[0]+box[2])/2)-100));y=max(0,min(234,round((box[1]+box[3])/2)-75))
 panel=cv2.resize(cv2.cvtColor(images[row['scene']][y:y+150,x:x+200],cv2.COLOR_RGB2BGR),(400,300),interpolation=cv2.INTER_NEAREST)
 for obj,color in ((gt,(255,255,0)),(pred,(0,110,255))):
  a,b,c,d=[round(v) for v in obj['box']]
  cv2.rectangle(panel,((a-x)*2,(b-y)*2),((c-x)*2,(d-y)*2),color,1)
 header=np.zeros((58,400,3),np.uint8)
 lines=[row['scene'],f"GT {CLASSES[gt['class_id']]} -> V8 {CLASSES[pred['class_id']]} {pred['score']:.3f}"]
 for i,line in enumerate(lines):cv2.putText(header,line,(5,20+i*24),cv2.FONT_HERSHEY_SIMPLEX,.43,(255,255,255),1,cv2.LINE_AA)
 panels.append(np.concatenate([header,panel]))
while len(panels)%3:panels.append(np.zeros_like(panels[0]))
canvas=np.concatenate([np.concatenate(panels[i:i+3],axis=1) for i in range(0,len(panels),3)]) if panels else np.zeros((100,1200,3),np.uint8)
assert cv2.imwrite(str(root/'holdout-confusions.png'),canvas)
with (root/'holdout-confusion-panels.json').open('x') as f:
 json.dump(dict(scope='First occurrence of each V8 heldout wrong-class overlap, post-hoc diagnostic only; cyan GT/orange prediction; display crop does not alter inputs',records=selected),f,indent=2);f.write('\n')
