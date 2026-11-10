"""Post-hoc error localization only. Does not change matching, selection, or gates."""
from pathlib import Path
import sys,json
from collections import Counter
sys.path[:0]=[str(Path('.').resolve()),str(Path('tests/integration/perception').resolve())]
from physical_ai.perception.dataset import read_json
from physical_ai.perception.contract import sha256_file
from evaluate import overlap
from quality_benchmark import write_new
root=Path(__file__).parent
phase=sys.argv[1]
truth=read_json(root/f'{phase}-data/evaluation-only-gt.json')['frames']
selection=read_json(root/'candidate-selection.json')
candidates=('baseline','large-v8') if phase=='development' else ('baseline',selection['selected'])
for candidate in candidates:
 run_path=root/f'{phase}-{candidate}/result.json';run=read_json(run_path)
 counts=Counter();confusions=Counter();records=[];fn_count=0
 for row,gt in zip(run['rows'],truth):
  used=set();preds=row['detections'] if row['model_valid'] else []
  for d in sorted(preds,key=lambda d:-d['score']):
   matches=[(overlap(d['box'],g['box']),n) for n,g in enumerate(gt['objects']) if n not in used and g['class_id']==d['class_id']]
   best=max(matches,default=(0,-1),key=lambda x:(x[0],-x[1]))
   if best[0]>=.5:used.add(best[1]);counts['tp']+=1;continue
   all_matches=[(overlap(d['box'],g['box']),n) for n,g in enumerate(gt['objects'])]
   closest=max(all_matches,default=(0,-1),key=lambda x:(x[0],-x[1]))
   obj=gt['objects'][closest[1]] if closest[1]>=0 else None
   small=max((overlap(d['box'],g['box']) for g in gt['excluded'] if g['class_id']==d['class_id']),default=0)
   if obj and closest[0]>=.5:
    if obj['class_id']==d['class_id']:reason='duplicate_same_class'
    else:
     reason='class_confusion';confusions[f"{obj['class_id']}->{d['class_id']}"]+=1
   elif small>=.5:reason='small_excluded_same_class'
   elif obj and obj['class_id']==d['class_id'] and closest[0]>0:reason='visible_localization_miss'
   else:reason='background_or_low_overlap'
   counts[reason]+=1;counts['fp']+=1
   records.append(dict(scene=row['scene'],prediction=d,reason=reason,best_visible_iou=closest[0],best_visible_gt=obj,small_same_class_iou=small))
  fn_count+=len(gt['objects'])-len(used)
 score=read_json(root/f'{phase}-{candidate}-score.json')
 assert (counts['tp'],counts['fp'],fn_count)==tuple(score['micro'][k] for k in ('tp','fp','fn'))
 write_new(root/f'{phase}-{candidate}-errors.json',dict(schema='m10-quality-error-diagnostic-v8',phase=phase,candidate=candidate,
  run_sha256=sha256_file(run_path),counts=dict(counts,fn=fn_count),class_confusions=dict(confusions),records=records,
  scope='Post-hoc categories at unchanged strict matching; not extra TPs or candidate tuning; no gate/selection change'))
 print(json.dumps(dict(phase=phase,candidate=candidate,counts=dict(counts,fn=fn_count),confusions=dict(confusions))),flush=True)
