#!/usr/bin/env python3
"""Prospective source/import/build freeze for one declared startup-fixed trial."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser()
    for name in ('output','native','source','engine','model','models','library'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();root=Path(__file__).resolve().parents[3];bundle=a.output.resolve()
    if (bundle/'sources.json').exists() or (bundle/'sources.tar.gz').exists():raise FileExistsError('immutable freeze already exists')
    bundle.mkdir(parents=True,exist_ok=True)
    prior=root/'docs/test-plan/evidence/m10_live_shadow_v1/sources.json'
    names=set(json.loads(prior.read_text())['files'])
    prefixes=('central/','cmake/','interfaces/','physical_ai/','profiles/','simulation/','tests/','tools/','vecu/','zone/')
    paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root).decode().split('\0')
    names.update(n for n in paths if n.startswith(prefixes) and (root/n).is_file())
    names.add('docs/test-plan/perception-startup-v1-protocol.md')
    names.update('docs/test-plan/evidence/m10_live_shadow_v1/run-01/capture/'+n for n in ('result.json','native.json','native.csv','trace.jsonl'))
    names.update(str((bundle/'baseline-runtime'/n).relative_to(root)) for n in ('async_leaf_owner.cpp','async_leaf_owner.hpp'))
    names.add(str((bundle/'check-evidence.py').relative_to(root)))
    files={n:dict(bytes=(root/n).stat().st_size,sha256=sha(root/n)) for n in sorted(names)}
    archive=bundle/'sources.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for n in sorted(names):tar.add(root/n,arcname=n,recursive=False)
    import carla
    profile=json.loads((root/'profiles/perception-source-compare-server-v2.json').read_text())
    external=[a.native.resolve(),a.model.resolve(),a.models.resolve(),a.library.resolve(),Path(sys.executable).resolve(),Path(carla.libcarla.__file__),
              a.engine/'Engine/Binaries/Linux/UE4Editor',a.engine/'Engine/Plugins/Runtime/PhysXVehicles/Binaries/Linux/libUE4Editor-PhysXVehicles.so',
              Path('/tmp/stratadrive-readback-source-v2/manifest.json')]
    external.extend(a.source/n for n in profile['external_files'])
    manifest=dict(schema='m10-wall-startup-frozen-v1',git_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                  archive_sha256=sha(archive),files=files,external={str(f):sha(f) for f in external})
    (bundle/'sources.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(files=len(files),archive_bytes=archive.stat().st_size,archive_sha256=manifest['archive_sha256'])))


if __name__=='__main__':main()
