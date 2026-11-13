"""Seal finite endurance evidence without duplicating lossless raw tar shards."""
import argparse
import json
import os
import errno
import shutil
from pathlib import Path
import tarfile
from seal_paired_v1 import archive,sha


def seal(run,bundle,prior):
    bundle.mkdir(parents=True,exist_ok=True)
    paths=sorted(p for p in run.rglob('*') if p.is_file() and p.name!='wall-signal')
    shards=[p for p in paths if p.name.startswith('raw-camera-') and p.suffix=='.tar']
    regular=[p for p in paths if p not in shards]
    manifest=archive(run,regular,bundle/'run.tar.gz')
    (bundle/'run-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    manifests=[]
    for path in shards:
        target=bundle/path.name
        try:os.link(path,target)
        except OSError as error:
            if error.errno!=errno.EXDEV:raise
            # Move only after every byte has a durable archive/checksum below.
            # The caller retains its NVMe source until full sealing succeeds.
            with path.open('rb') as source,target.open('xb') as destination:
                shutil.copyfileobj(source,destination,1024*1024)
                destination.flush();os.fsync(destination.fileno())
            if sha(path)!=sha(target):raise ValueError('cross-device shard copy changed')
        members={}
        with tarfile.open(target) as tar:
            for item in tar:
                name=Path(item.name)
                if not item.isfile() or name.is_absolute() or '..' in name.parts or item.name in members:
                    raise ValueError('raw shard membership')
                import hashlib
                h=hashlib.sha256()
                with tar.extractfile(item) as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
                members[item.name]=dict(bytes=item.size,sha256=h.hexdigest())
        manifests.append(dict(archive=target.name,original=str(path.relative_to(run)),bytes=target.stat().st_size,
            sha256=sha(target),members=members))
    (bundle/'raw-manifest.json').write_text(json.dumps(dict(schema='m10-endurance-shards-v1',archives=manifests),indent=2)+'\n')
    old=json.loads(prior.read_text());hashes=set(old['rgb_sha256']);new=[]
    result=run/'capture/paired/renderer/result.json'
    if result.exists():new=[r['rgb_sha256'] for r in json.loads(result.read_text())['raw']]
    added=set(new)-hashes;hashes.update(new)
    exclusion=dict(schema='m10-paired-future-exclusion-v1',prior=os.path.relpath(prior,bundle),prior_sha256=sha(prior),
        prior_count=old['count'],new_raw_packets=len(new),new_unique=len(added),count=len(hashes),holdout_access=False,rgb_sha256=sorted(hashes))
    (bundle/'future-exclusion.json').write_text(json.dumps(exclusion,indent=2)+'\n')
    return dict(run_files=len(regular),raw_shards=len(shards),raw_packets=len(new),future_exclusion=len(hashes))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('run','bundle','prior'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(seal(a.run,a.bundle,a.prior)))
