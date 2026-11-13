import os,sys,json,time,resource,hashlib
from pathlib import Path
import numpy as np
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'tests/integration/perception')]
from endurance_recording_v1 import RawReader
from physical_ai.perception.staged_kernel_2k_v1 import StagedKernelBackend
from physical_ai.perception.async_native_2k_v1 import BgraPacket
from physical_ai.perception.contract import FrameIdentity
mode=sys.argv[1];out=Path('build/m10-endurance-v7')
if mode=='passive':os.environ['STRATADRIVE_ORT_PASSIVE_THREADS']='1'
else:os.environ.pop('STRATADRIVE_ORT_PASSIVE_THREADS',None)
os.environ['OMP_WAIT_POLICY']='PASSIVE'
p=Path('build/m10-endurance-v6/normal-30s-01-archive-check/run/capture/paired/renderer');rows=json.loads((p/'result.json').read_text())['raw'][:3];reader=RawReader(p)
backend=StagedKernelBackend('build/m10-resolution-v2/models/dfine-960.onnx','build/m10-resolution-v2/models.json','build/m10-source-compare-v1/native/libstrata_resize_2k_v1.so','f851fa22a24576d4e76fa2fa8749f3f4517d5ee625b64de390a360fd32fb0721')
feeds=[]
for i,row in enumerate(rows):
 raw=reader.read(row);feed,*_=backend.resize.prepare(BgraPacket(FrameIdentity(42,1,i+1,0),raw,time.monotonic_ns()));feeds.append({k:v.copy() for k,v in feed.items()})
reader.close()
for feed in feeds:backend.detector.raw(feed)
begin=time.monotonic();cpu=time.process_time();outputs={}
for repeat in range(4):
 for i,feed in enumerate(feeds):
  value=backend.detector.raw(feed)
  for k,v in value.items():outputs[f'{repeat}-{i}-{k}']=v
summary=dict(mode=mode,calls=12,wall_seconds=time.monotonic()-begin,cpu_seconds=time.process_time()-cpu,raw_rgb_hashes=[r['rgb_sha256'] for r in rows],holdout_access=False)
np.savez(out/(mode+'-outputs.npz'),**outputs);(out/(mode+'-check.json')).write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
