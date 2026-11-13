"""Lossless bounded-case archives and cumulative raw-image future exclusion."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def archive(root,paths,destination):
    if destination.exists():raise ValueError('immutable archive exists')
    members={str(p.relative_to(root)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in paths}
    with tarfile.open(destination,'w:gz' if destination.name.endswith('.gz') else 'w') as tar:
        for p in paths:tar.add(p,arcname=str(p.relative_to(root)),recursive=False)
    with tarfile.open(destination,'r:*') as tar:
        found=tar.getmembers()
        if {m.name for m in found}!=set(members) or len(found)!=len(members):raise ValueError('archive membership')
        for m in found:
            data=tar.extractfile(m).read();expected=members[m.name]
            if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:
                raise ValueError('archive roundtrip '+m.name)
    return dict(archive=destination.name,bytes=destination.stat().st_size,sha256=sha(destination),members=members)


def main(a):
    a.bundle.mkdir(parents=True,exist_ok=True)
    paths=sorted(p for p in a.run.rglob('*') if p.is_file() and p.name!='wall-signal')
    raw=[p for p in paths if p.name.endswith(('.bgra.z','.bgra'))]
    regular=[p for p in paths if p not in raw]
    manifest=archive(a.run,regular,a.bundle/'run.tar.gz')
    (a.bundle/'run-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if raw:
        raw_manifest=archive(a.run,raw,a.bundle/'raw-camera-01.tar')
        (a.bundle/'raw-manifest.json').write_text(json.dumps(raw_manifest,indent=2)+'\n')
    prior=json.loads(a.prior.read_text());hashes=set(prior['rgb_sha256']);new=[];packets=0
    for path in a.run.rglob('result.json'):
        result=json.loads(path.read_text())
        if result.get('schema')=='m10-paired-renderer-v1':
            packets+=len(result['raw']);new.extend(r['rgb_sha256'] for r in result['raw'])
    added=set(new)-hashes;hashes.update(new)
    import os
    exclusion=dict(schema='m10-paired-future-exclusion-v1',prior=os.path.relpath(a.prior,a.bundle),prior_sha256=sha(a.prior),
        prior_count=prior['count'],new_raw_packets=packets,new_unique=len(added),count=len(hashes),
        holdout_access=False,rgb_sha256=sorted(hashes))
    (a.bundle/'future-exclusion.json').write_text(json.dumps(exclusion,indent=2)+'\n')
    print(json.dumps(dict(run_files=len(regular),raw_files=len(raw),raw_packets=packets,future_exclusion=len(hashes))))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('run','bundle','prior'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
