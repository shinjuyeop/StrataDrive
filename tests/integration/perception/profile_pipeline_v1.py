"""Offline CPU-stage comparison using already-excluded, verified raw images."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import cv2
import numpy as np
from PIL import Image
from endurance_recording_v1 import RawReader, Zstd
from physical_ai.perception.staged_kernel_2k_v1 import StagedKernelBackend, prepare_staged
from physical_ai.perception.async_native_2k_v1 import BgraPacket
from physical_ai.perception.contract import FrameIdentity


def measure(fn, count=24):
    rows=[]
    for index in range(count):
        cpu=time.process_time_ns(); wall=time.monotonic_ns(); fn(index)
        rows.append(dict(wall_ms=(time.monotonic_ns()-wall)/1e6, cpu_ms=(time.process_time_ns()-cpu)/1e6))
    return dict(samples=rows, median_ms=statistics.median(r['wall_ms'] for r in rows),
                p95_ms=sorted(r['wall_ms'] for r in rows)[int(.95*(len(rows)-1))],
                cpu_ms_per_call=statistics.mean(r['cpu_ms'] for r in rows))


def main(a):
    a.output.mkdir(parents=True, exist_ok=False)
    assert os.environ.get('OMP_WAIT_POLICY')=='PASSIVE'
    assert os.environ.get('STRATADRIVE_ORT_PASSIVE_THREADS')=='1'
    results=json.loads((a.capture/'result.json').read_text()); rows=results['raw'][8:14]
    reader=RawReader(a.capture); raw=[reader.read(row) for row in rows]; reader.close()
    packets=[BgraPacket(FrameIdentity(42,1,index+1,0),value,time.monotonic_ns()) for index,value in enumerate(raw)]
    backend=StagedKernelBackend('build/m10-resolution-v2/models/dfine-960.onnx',
        'build/m10-resolution-v2/models.json','build/m10-source-compare-v1/native/libstrata_resize_2k_v1.so',
        'f851fa22a24576d4e76fa2fa8749f3f4517d5ee625b64de390a360fd32fb0721')
    report=dict(scope='excluded offline inputs; no live throughput or control claim',
                affinity=sorted(os.sched_getaffinity(0)), cv2_initial_threads=cv2.getNumThreads(),
                raw_hashes=[r['bgra_sha256'] for r in rows], providers=backend.detector.session.get_providers(),
                preprocessing=[], stages={})
    report['cuda_wait_policy']=getattr(backend.detector,'cuda_wait_policy',None)
    reference=[]; feeds=[]
    for packet in packets:
        feed,*_=prepare_staged(backend.resize,packet,{})
        reference.append(hashlib.sha256(feed['images'].tobytes()).hexdigest()); feeds.append(feed)
        backend.detector.raw(feed)
    outputs={}
    for i,feed in enumerate(feeds):
        for key,value in backend.detector.raw(feed).items():outputs[f'{i}-{key}']=value
    np.savez(a.output/'model-outputs.npz',**outputs)
    for cv in (1,2,4):
        cv2.setNumThreads(cv)
        for resize in (1,2,4):
            backend.resize.threads=resize
            def call(index):
                feed,*_=prepare_staged(backend.resize,packets[index%len(packets)],{})
                return feed
            for index in range(len(packets)):
                assert hashlib.sha256(call(index)['images'].tobytes()).hexdigest()==reference[index]
            report['preprocessing'].append(dict(cv2_threads=cv, resize_threads=resize, **measure(call)))
    report['tensor_sha256']=reference; report['all_preprocessing_tensors_bit_exact']=True
    report['stages']['cuda_session']=measure(lambda i:backend.detector.raw(feeds[i%len(feeds)]))
    codec=Zstd()
    report['stages']['zstd1']=measure(lambda i:codec.compress(raw[i%len(raw)]))
    report['stages']['bgra_hash']=measure(lambda i:hashlib.sha256(raw[i%len(raw)]).digest())
    def rgb_hash(index):
        row=rows[index%len(rows)];value=raw[index%len(raw)]
        return hashlib.sha256(Image.frombytes('RGB',(row['width'],row['height']),value,'raw','BGRX').tobytes()).digest()
    report['stages']['rgb_conversion_hash']=measure(rgb_hash)
    (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(preprocessing=[{k:v for k,v in r.items() if k!='samples'} for r in report['preprocessing']],
                         stages={k:{n:x for n,x in v.items() if n!='samples'} for k,v in report['stages'].items()})))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);main(p.parse_args())
