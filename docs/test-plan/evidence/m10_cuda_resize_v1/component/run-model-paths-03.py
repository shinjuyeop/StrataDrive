"""Wait for the existing archive/restoration, then validate actual model paths."""
import json
import os
from pathlib import Path
import subprocess
import time

root=Path('/d/shin/StrataDrive')
prior=root/'docs/test-plan/evidence/m10_service_half_v1'
deadline=time.monotonic()+1800
while Path('/proc/4036436').exists():
    if time.monotonic()>deadline:raise TimeoutError('existing sequence still owns postprocessing')
    time.sleep(2)
assert json.loads((prior/'cache-execution.json').read_text())['restoration']['status']=='PASS_ORIGINALS_RESTORED'
assert json.loads((prior/'normal-300s-01/disposition.json').read_text())['finite_diagnostic_pass']
lib=root/'build/m10-cuda-resize-v1/release/libresize-cuda.so'
env=dict(os.environ,STRATADRIVE_M10_CPU_PLAN=json.dumps(json.loads((root/'profiles/perception-endurance-host-v5.json').read_text())['cpus']),
    STRATADRIVE_M10_PROFILE='1',STRATADRIVE_M10_PREFETCH_LIBRARIES='1',
    STRATADRIVE_M10_TENSOR_WORKSPACE='1',STRATADRIVE_M10_CUDA_RESIZE_LIBRARY=str(lib),
    STRATADRIVE_M10_CUDA_RESIZE_SHA256='0be28cf15bc07f76710e4b88ea3b57d516ff5aec12b12efa5dfe72ef07be7312',
    STRATADRIVE_M10_CV_THREADS='4',STRATADRIVE_M10_RESIZE_THREADS='0',
    STRATADRIVE_CUDA_BLOCKING_SYNC='1',STRATADRIVE_ORT_PASSIVE_THREADS='1',
    OMP_WAIT_POLICY='PASSIVE',PYTHONDONTWRITEBYTECODE='1')
libs=list((root/'build/m10-perception/cuda-venv/lib/python3.10/site-packages/nvidia').glob('*/lib'))
env['LD_LIBRARY_PATH']=':'.join(map(str,libs))+':'+env.get('LD_LIBRARY_PATH','')
raise SystemExit(subprocess.call([str(root/'build/m10-perception/cuda-venv/bin/python'),
    str(root/'build/m10-cuda-resize-v1/check-model-paths.py'),'--output',
    str(root/'build/m10-cuda-resize-v1/model-paths-03')],env=env))
