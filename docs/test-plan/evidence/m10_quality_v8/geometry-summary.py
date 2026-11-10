from pathlib import Path
import json,math,sys
sys.path[:0]=['.','tests/integration/perception']
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from quality_benchmark import write_new
from quality_geometry_v4 import angle_delta
root=Path(__file__).parent
prior=set(read_json('profiles/perception-quality-evaluation-exclusion-v8.json')['rgb_sha256']);future=set(prior)
summary={}
plan=read_json('profiles/perception-road-evaluation-v8b.json')
for part in ('development','holdout'):
 cap=read_json(root/read_json(root/'evaluation-runs.json')[part]/'dataset/capture.json');truth=read_json(root/f'{part}-data/evaluation-only-gt.json')
 future.update(f['rgb_sha256'] for f in read_json(root/f'{part}-data/rgb.json')['frames'])
 dist=[];angles=[];projection=[];clearance=[];support=[];riders=[]
 for case,scene,gt in zip(plan['partitions'][part]['cases'],cap['scenes'],truth['frames']):
  objects={(o['class_id'],o['instance_id']):o for o in gt['objects']}
  for wanted,actual in zip(case['actors'],scene['actors']):
   dist.append(math.dist(list(wanted['pose']['location'].values()),list(actual['pose']['location'].values())))
   angles.extend(abs(angle_delta(actual['pose']['rotation'][k],wanted['pose']['rotation'][k])) for k in ('pitch','yaw','roll'))
   projection.append(actual['road_readback']['projection_m']);clearance.append(abs(actual['road_readback']['clearance_error_m']))
   key=(actual['class_id'],actual['actor_id']%65536);support.append(objects[key]['visible_pixels'])
   if actual['class_id'] in (1,3):riders.append(objects[(0,key[1])]['visible_pixels'])
 summary[part]=dict(actors=len(dist),riders=len(riders),maximum_position_error_m=max(dist),maximum_angle_error_degrees=max(angles),
  maximum_projection_m=max(projection),maximum_clearance_error_m=max(clearance),minimum_planned_visible_pixels=min(support),minimum_rider_visible_pixels=min(riders),
  objects=sum(len(f['objects']) for f in truth['frames']),excluded=sum(len(f['excluded']) for f in truth['frames']))
assert len(prior)==read_json('profiles/perception-quality-protocol-v8.json')['prior_rgb_excluded']
assert future==set(read_json(root/'future-evaluation-exclusion.json')['rgb_sha256'])
write_new(root/'geometry-summary.json',summary)
print(json.dumps(dict(geometry=summary)))
