"""A fixed alternating cold-start study, independent of original live verdicts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
study=SERIES/'preparation-study';study.mkdir(exist_ok=False)
plan=[dict(number=i+1,workspace=bool(i%2)) for i in range(40)]
files=[ROOT/'physical_ai/perception/tensor_2k_v1.py',ROOT/'tests/integration/perception/control_shadow_capture_v1.py',
       ROOT/'tests/integration/perception/endurance_host_v1.py',SERIES/'profile-preparation.py',Path(__file__).resolve()]
declaration=dict(scope='40 fixed alternating fresh processes; record all outcomes, no result-dependent retries; no CARLA, original cap100',
    plan=plan,files={str(p.relative_to(ROOT)):sha(p) for p in files},unchanged_gate='10s total, exactly three calls, final two <100ms')
(study/'declaration.json').write_text(json.dumps(declaration,indent=2)+'\n')
assert Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct').read_text().strip()=='100'
base=dict(os.environ,OMP_WAIT_POLICY='PASSIVE',STRATADRIVE_ORT_PASSIVE_THREADS='1',STRATADRIVE_CUDA_BLOCKING_SYNC='1',
    STRATADRIVE_M10_CV_THREADS='4',STRATADRIVE_M10_RESIZE_THREADS='4',
    STRATADRIVE_M10_CPU_PLAN=json.dumps(json.loads((ROOT/'profiles/perception-endurance-host-v1.json').read_text())['cpus']))
base.pop('STRATADRIVE_M10_TENSOR_WORKSPACE',None)
results=[]
for item in plan:
    env=dict(base)
    if item['workspace']:env['STRATADRIVE_M10_TENSOR_WORKSPACE']='1'
    output=study/f"case-{item['number']:02}"
    process=subprocess.run(['taskset','-c','0,8',str(ROOT/'build/m10-perception/cuda-venv/bin/python'),
        str(SERIES/'profile-preparation.py'),'--output',str(output)],env=env,capture_output=True,text=True,timeout=30)
    row=dict(**item,exit=process.returncode,stdout=process.stdout,stderr=process.stderr);results.append(row)
    (study/'processes.json').write_text(json.dumps(results,indent=2)+'\n')
    if process.returncode:raise RuntimeError('study infrastructure failure; retain completed original results')
    print(process.stdout.strip(),flush=True)
assert all(sha(ROOT/name)==digest for name,digest in declaration['files'].items())
summary={}
for workspace in (False,True):
    records=[json.loads((study/f"case-{r['number']:02}/profile.json").read_text()) for r in results if r['workspace']==workspace]
    summary['workspace' if workspace else 'baseline']=dict(processes=len(records),ready=sum(r['preparation_state']=='READY' for r in records),
        failed=sum(r['preparation_state']!='READY' for r in records),
        maximum_settled_ms=max(v for r in records for v in r['calls_ms'][1:]),
        maximum_preprocess_ms=max(p['delta']['wall_ns']/1e6 for r in records for p in r['preprocessing']),
        maximum_preprocess_cpu_ms=max(p['delta']['cpu_ns']/1e6 for r in records for p in r['preprocessing']))
(study/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
