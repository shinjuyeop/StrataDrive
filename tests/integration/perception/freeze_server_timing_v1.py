"""Freeze one instrumentation-only trial before server launch."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--build',type=Path,required=True)
    p.add_argument('--protocol',default='docs/test-plan/perception-server-timing-v1-protocol.md')
    p.add_argument('--prior',default='docs/test-plan/evidence/m10_startup_v1/sources.json');a=p.parse_args()
    root=Path(__file__).resolve().parents[3];bundle=a.output.resolve();bundle.mkdir(parents=True,exist_ok=True)
    assert not (bundle/'sources.json').exists() and not (bundle/'sources.tar.gz').exists(),'immutable freeze'
    prior=json.loads((root/a.prior).read_text())
    names=set(prior['files']);prefixes=('central/','cmake/','interfaces/','physical_ai/','profiles/','simulation/','tests/','tools/','vecu/','zone/')
    tracked=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root).decode().split('\0')
    names.update(n for n in tracked if n.startswith(prefixes) and (root/n).is_file())
    names.update((a.protocol,str((bundle/'check-evidence.py').relative_to(root))))
    files={n:dict(bytes=(root/n).stat().st_size,sha256=sha(root/n)) for n in sorted(names)}
    with tarfile.open(bundle/'sources.tar.gz','w:gz') as tar:
        for name in sorted(names):tar.add(root/name,arcname=name,recursive=False)
    manifest=a.build.resolve();build=json.loads(manifest.read_text());external={Path(p) for p in prior['external']}
    external.add(manifest);external.update(Path(item['path']) for item in build['installed'].values())
    for path,digest in build['inputs'].items():assert sha(Path(path))==digest,'build input changed: '+path
    for name,digest in build['generated'].items():assert sha(manifest.parent/name)==digest,'generated build changed: '+name
    result=dict(schema='m10-server-timing-frozen-v1',git_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                archive_sha256=sha(bundle/'sources.tar.gz'),files=files,external={str(p):sha(p) for p in sorted(external)})
    (bundle/'sources.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(files=len(files),archive_sha256=result['archive_sha256'])))


if __name__=='__main__':main()
