#!/usr/bin/env python3
"""Build an isolated exact CUDA resize candidate; never install or start CARLA."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = root/'physical_ai/perception/cuda_resize_2k_v1.cu'
    runtime = args.runtime_lib.resolve()
    if not (runtime/'libcudart.so.12').is_file():
        raise ValueError('explicit CUDA12 runtime library directory required')
    nvcc = Path(args.nvcc).resolve()
    library = output/'libresize-cuda.so'
    command = [str(nvcc), '-std=c++17', '-O3', '-Xcompiler=-fPIC,-ffp-contract=off',
               '--fmad=false', '--cudart=shared',
               '-gencode', 'arch=compute_86,code=sm_86',
               '-gencode', 'arch=compute_86,code=compute_86',
               '-shared', str(source), '-o', str(library),
               '-Xlinker', '-rpath', '-Xlinker', str(runtime)]
    with (output/'build.log').open('x') as log:
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
    manifest = dict(schema='m10-cuda-resize-2k-v1', status='BUILT_NOT_ACCEPTED',
        scope='Host RTX3090 SM86/PTX86 candidate; rebuild and validate on each Jetson in M12',
        compiler=str(nvcc), compiler_version=subprocess.check_output([str(nvcc), '--version'], text=True),
        command=command, source=dict(path=str(source.relative_to(root)), sha256=sha(source)),
        library=dict(path=str(library), sha256=sha(library)),
        runtime=dict(path=str(runtime/'libcudart.so.12'), sha256=sha(runtime/'libcudart.so.12')),
        arithmetic='original host-generated coefficients; two integer 22-bit passes; CPU tensor conversion unchanged',
        input=[1536,2560,4], output=[960,960,3], persistent_workspace=True,
        host_wait='cudaEventBlockingSync', cpu_resize_threads=0, live_execution=False)
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--nvcc', default=shutil.which('nvcc'))
    parser.add_argument('--runtime-lib', type=Path, required=True)
    main(parser.parse_args())
