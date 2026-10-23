#!/usr/bin/env python3
"""Usage: python check_oracle.py <repository> <uncompressed run directory>."""
import importlib.util,json,shutil,sys,tempfile
from pathlib import Path
repo,run=map(Path,sys.argv[1:])
spec=importlib.util.spec_from_file_location('oracle',repo/'tests/integration/carla/analyze_m7_1e.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
results=[]
for mutation in ['wall_order','delta_50ms','camera_timestamp','missing_camera']:
 with tempfile.TemporaryDirectory() as tmp:
  folder=Path(tmp)/'case';shutil.copytree(run/'matrix_TERM/attempt/1-camera_metadata',folder)
  path=folder/('ticks.jsonl' if mutation in ['wall_order','delta_50ms'] else 'cameras.jsonl')
  data=m.read(path)
  if mutation=='wall_order':data[150]['snapshot_end_ns']=data[150]['begin_ns']-1
  elif mutation=='delta_50ms':data[150]['delta_s']=.05
  elif mutation=='camera_timestamp':data[60]['sim_s']+=.01
  else:data.pop(60)
  path.write_text(''.join(json.dumps(t)+'\n' for t in data))
  try:m.analyze_case(folder)
  except ValueError as e:results.append({'mutation':mutation,'rejected':True,'reason':str(e)})
  else:raise AssertionError(mutation+' was accepted')
print(json.dumps({'status':'PASS','scope':'offline corrupted copies only','tests':results},indent=2))
