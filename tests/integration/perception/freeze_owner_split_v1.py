"""Prospective source/import/runtime freeze for one explicit owner5ms trial."""
import argparse
import json
from pathlib import Path
import subprocess
import tarfile
from run_carla_control_shadow_v1 import sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prior',default='docs/test-plan/evidence/m10_fence_compare_v1/sources.json')
    p.add_argument('--protocol',default='docs/test-plan/perception-owner-split-v1-protocol.md')
    p.add_argument('--external',type=Path,action='append',default=[]);a=p.parse_args()
    root=Path(__file__).resolve().parents[3];bundle=a.output.resolve();bundle.mkdir(parents=True,exist_ok=True)
    assert not (bundle/'sources.json').exists() and not (bundle/'sources.tar.gz').exists(),'immutable freeze'
    prior=json.loads((root/a.prior).read_text())
    names=set(prior['files']);prefixes=('central/','cmake/','interfaces/','physical_ai/','profiles/','simulation/','tests/','tools/','vecu/','zone/')
    paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root).decode().split('\0')
    names.update(n for n in paths if n.startswith(prefixes) and (root/n).is_file())
    names.update((a.protocol,str((bundle/'check-evidence.py').relative_to(root))))
    names.add('docs/test-plan/evidence/m10_fence_compare_v1/build-02/manifest.json')
    files={n:dict(bytes=(root/n).stat().st_size,sha256=sha(root/n)) for n in sorted(names)}
    with tarfile.open(bundle/'sources.tar.gz','w:gz') as tar:
        for n in sorted(names):tar.add(root/n,arcname=n,recursive=False)
    # Re-hash the currently restored baseline; this does not reuse instrumented
    # hashes from the previous run. The runner also checks the original profile.
    external={n:sha(n) for n in prior['external']}
    external.update({str(p.resolve()):sha(p) for p in a.external})
    replay=root/'build/m10-live-shadow-v1/normal/tests/integration/carla/m7_1g/m7_wall_startup_replay'
    external[str(replay)]=sha(replay)
    result=dict(schema='m10-owner-split-frozen-v1',git_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                archive_sha256=sha(bundle/'sources.tar.gz'),files=files,external=external)
    (bundle/'sources.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(files=len(files),archive_sha256=result['archive_sha256'])))


if __name__=='__main__':main()
