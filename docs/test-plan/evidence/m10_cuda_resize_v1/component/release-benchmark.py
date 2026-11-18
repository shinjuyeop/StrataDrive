"""Post-run GPU-only resize comparison; no live or perception acceptance."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent/'release'
assert not any(n.startswith(('UE4Editor','CarlaUE4-Linux','m7_carla_wall')) for n in subprocess.check_output(['ps','-eo','comm='],text=True).splitlines())
host_cap=Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct').read_text().strip()
assert host_cap in ('70','100') if '--check-only' in sys.argv else host_cap=='70'
os.environ['OMP_WAIT_POLICY']='PASSIVE'
sys.path[:0]=[str(ROOT),str(ROOT/'tests/integration/perception')]
import cv2
import numpy as np
import PIL
from PIL import Image
from physical_ai.perception.cuda_resize_2k_v1 import CudaResize
from endurance_recording_v1 import RawReader
from physical_ai.perception.native_kernel_2k_v1 import NativeResize
from physical_ai.perception.tensor_2k_v1 import TensorWorkspace
from physical_ai.perception.async_native_2k_v1 import BgraPacket
from physical_ai.perception.contract import FrameIdentity
assert (cv2.__version__,np.__version__,PIL.__version__)==('4.11.0','1.23.5','11.3.0')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
case=json.loads((ROOT/'docs/test-plan/evidence/m10_service_half_v1/normal-30s-01/case.json').read_text())
baseline=Path(case['argv'][case['argv'].index('--library')+1])
cpu=NativeResize(baseline,sha(baseline));gpu=CudaResize(OUT/'libresize-cuda.so',sha(OUT/'libresize-cuda.so'))
capture=ROOT/'build/m10-service-half-v1/normal-30s-01/archive-check/run/capture/paired/renderer'
originals=json.loads((capture/'result.json').read_text())['raw'][:3]
reader=RawReader(capture);images=[]
try:
    for row in originals:
        raw=reader.read(row);assert hashlib.sha256(raw).hexdigest()==row['bgra_sha256'];images.append(raw)
finally:reader.close()
equivalence=[]
for i in range(12):
    if i<3:raw=images[i]
    else:
        array=np.random.default_rng(i).integers(0,256,(1536,2560,4),dtype=np.uint8)
        if i==3:array[:]=np.arange(2560,dtype=np.uint16)[None,:,None]%256
        if i==4:array[:]=np.arange(1536,dtype=np.uint16)[:,None,None]%256
        if i==5:array[:]=np.indices((1536,2560)).sum(axis=0)[:,:,None]%2*255
        if i==6:array[:]=0
        if i==7:array[:]=255
        raw=array.tobytes()
    expected=np.asarray(Image.frombytes('RGB',(2560,1536),raw,'raw','BGRX').resize((960,960),Image.Resampling.BILINEAR))
    got=gpu.resize(raw)
    assert np.array_equal(got,expected),(i,int(np.count_nonzero(got!=expected)))
    assert np.array_equal(got,cpu.resize(raw))
    want=np.ascontiguousarray(np.asarray(expected,np.float32).transpose(2,0,1)[None]/255.0)
    assert np.array_equal(TensorWorkspace().convert(got)['images'],want)
    equivalence.append(dict(index=i,bgra_sha256=hashlib.sha256(raw).hexdigest(),resized_sha256=hashlib.sha256(got.tobytes()).hexdigest()))
for length in (0,2560*1536*4-1,2560*1536*4+1):
    before=gpu.output.copy()
    assert gpu.call(gpu.handle,ctypes.c_char_p(images[0]),length,gpu.output.ctypes.data,gpu.output.nbytes)==10001
    assert np.array_equal(before,gpu.output)
assert gpu.call(None,None,0,None,0)==10001
assert gpu.create(None)==10001
if '--check-only' in sys.argv:
    gpu.close()
    (OUT/'sanitizer-check.json').write_text(json.dumps(dict(status='PASS_EXACT_PIXEL_CHECK_ONLY',host_max_perf_pct=int(host_cap),equivalence=equivalence,invalid_size_cases=3),indent=2)+'\n')
    print('PASS exact pixel and tensor cases; all CUDA workspace allocations released')
    raise SystemExit(0)
groups=[('cpu',4,4),('cpu',2,4),('gpu',4,0),('gpu',2,0),('gpu',1,0)]
packets=[BgraPacket(FrameIdentity(42,1,i+1,0),raw,time.monotonic_ns()) for i,raw in enumerate(images)]
workspace=TensorWorkspace();records=[]
for round in range(33):
    for name,cv,threads in (groups if round%2==0 else list(reversed(groups))):
        cv2.setNumThreads(cv);resize=cpu if name=='cpu' else gpu
        if name=='cpu':resize.threads=threads
        row={};wall=time.monotonic_ns();cpu_time=time.thread_time_ns()
        feed,values,fallback=workspace.prepare(resize,packets[round%3],row)
        row['owner_cpu_ns']=time.thread_time_ns()-cpu_time
        if round>=3:records.append(dict(kernel=name,cv_threads=cv,resize_threads=threads,round=round,stages=row))
summary=[]
for name,cv,threads in groups:
    rows=[r['stages'] for r in records if (r['kernel'],r['cv_threads'],r['resize_threads'])==(name,cv,threads)]
    item=dict(kernel=name,cv_threads=cv,resize_threads=threads,count=len(rows))
    for label,a,b in [('total','begin','tensor'),('resize','health','resize')]:
        values=[(r[b]-r[a])/1e6 for r in rows]
        item[label]=dict(median_ms=statistics.median(values),p95_ms=statistics.quantiles(values,n=100,method='inclusive')[94])
    item['owner_cpu_median_ms']=statistics.median(r['owner_cpu_ns']/1e6 for r in rows);summary.append(item)
gpu.close();gpu.close()
try:gpu.resize(images[0]);raise AssertionError('closed GPU workspace accepted')
except RuntimeError:pass
report=dict(status='PASS_EXACT_PIXELS_AND_TENSORS',scope='offline post-run comparison; raw images already future-excluded; no live acceptance',
    versions=dict(cv=cv2.__version__,numpy=np.__version__,pillow=PIL.__version__),cpu_affinity=sorted(os.sched_getaffinity(0)),
    source_sha256=sha(OUT/'resize.cu'),library_sha256=sha(OUT/'libresize-cuda.so'),runtime_maps=[r for r in Path('/proc/self/maps').read_text().splitlines() if 'libcudart.so' in r],
    original_frames=[dict(frame=r['frame'],bgra_sha256=r['bgra_sha256']) for r in originals],equivalence=equivalence,
    invalid_size_cases=3,records=records,summary=summary)
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(status=report['status'],summary=summary),indent=2))
