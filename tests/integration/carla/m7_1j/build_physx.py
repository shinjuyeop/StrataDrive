#!/usr/bin/env python3
"""Build public PhysX 3.4 CHECKED SDK for an isolated probe, never UE/CARLA.

The 2018 makefiles promote modern compiler warnings to errors. Retain warnings
but disable that promotion for this external SDK only. Project tests retain
their own quality flags. One tracked const-correctness compatibility patch is
applied; no equations, solver settings, or physical constants are changed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

PIN = '5e42a5f112351a223c19c17bb331e6c55037b8eb'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    src, out = args.source.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    head = subprocess.check_output(['git', '-C', str(src), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise RuntimeError('unexpected SDK commit')
    compat = 'PhysX_3.4/Source/GeomUtils/src/gjk/GuGJKType.h'
    old = subprocess.check_output(['git', '-C', str(src), 'show', 'HEAD:'+compat])
    before = b'PX_FORCE_INLINE Ps::aos::PsMatTransformV& getRelativeTransform(){ return mAToB; }'
    after = b'PX_FORCE_INLINE const Ps::aos::PsMatTransformV& getRelativeTransform(){ return mAToB; }'
    if old.count(before) != 1:
        raise RuntimeError('unexpected compatibility patch context')
    expected = old.replace(before, after)
    changed = subprocess.check_output(['git', '-C', str(src), 'diff', 'HEAD', '--name-only'], text=True).splitlines()
    patch = Path(__file__).with_name('physx-clang14.patch').resolve()
    if not changed:
        subprocess.run(['git', '-C', str(src), 'apply', '--unidiff-zero', str(patch)], check=True)
    elif changed != [compat]:
        raise RuntimeError('unrelated SDK source changes')
    if (src/compat).read_bytes() != expected:
        raise RuntimeError('SDK modification differs from declared compatibility patch')
    (out/'compatibility.patch').write_bytes(patch.read_bytes())
    compiler = shutil.which('clang++-14')
    if compiler is None:
        raise RuntimeError('clang++-14 missing')
    # Fixed, discovered executable; shell arguments passed through without eval.
    wrapper = out/'clang-cxx'
    wrapper.write_text('#!/bin/sh\nexec '+compiler+' "$@" -Wno-error\n')
    wrapper.chmod(0o755)
    command = ['make', '-C', str(src/'PhysX_3.4/Source/compiler/linux64'),
               '-j', '4', 'checked', 'CXX='+str(wrapper), 'CC=clang-14']
    with (out/'build.log').open('w') as log:
        run = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    result = dict(source=str(src), commit=head, command=command, exit=run.returncode,
                  compiler=subprocess.check_output([compiler, '--version'], text=True),
                  sdk_mode='CHECKED', sdk_instrumented=False, ue_build=False,
                  warning_policy='External SDK warnings retained; -Werror promotion disabled',
                  compatibility_patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest(),
                  build_log_sha256=hashlib.sha256((out/'build.log').read_bytes()).hexdigest())
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()
