"""Seal finite endurance evidence without duplicating lossless raw tar shards."""
import argparse
import json
import os
import errno
import gzip
import shutil
from pathlib import Path
import tarfile
from seal_paired_v1 import archive,sha
from raw_archive_stream_v1 import inspect as inspect_raw


def seal(run,bundle,prior,compress_raw=False):
    bundle.mkdir(parents=True,exist_ok=True)
    paths=sorted(p for p in run.rglob('*') if p.is_file() and p.name!='wall-signal')
    shards=[p for p in paths if p.name.startswith('raw-camera-') and p.suffix=='.tar']
    regular=[p for p in paths if p not in shards]
    manifest=archive(run,regular,bundle/'run.tar.gz')
    (bundle/'run-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    manifests=[]
    for path in shards:
        target=bundle/path.name
        if compress_raw:
            target=target.with_suffix('.tar.gz')
            with target.open('xb') as destination:
                with gzip.GzipFile(filename='',mode='wb',fileobj=destination,compresslevel=1,mtime=0) as compressed:
                    copied=inspect_raw(path,destination=compressed)
                destination.flush();os.fsync(destination.fileno())
            sealed=inspect_raw(target,expanded_expected={k:copied[k] for k in ('bytes','sha256')})
            if sealed['members']!=copied['members']:raise ValueError('compressed raw members differ')
            manifests.append(dict(archive=target.name,original=str(path.relative_to(run)),**sealed))
            continue
        try:os.link(path,target)
        except OSError as error:
            if error.errno!=errno.EXDEV:raise
            # Copy and hash every original byte/member in one sequential pass.
            # Re-read the durable target independently before retaining a manifest.
            with target.open('xb') as destination:
                copied=inspect_raw(path,destination=destination)
                destination.flush();os.fsync(destination.fileno())
            sealed=inspect_raw(target,copied)
        else:sealed=inspect_raw(target)
        manifests.append(dict(archive=target.name,original=str(path.relative_to(run)),**sealed))
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
    p.add_argument('--compress-raw-transport',action='store_true')
    a=p.parse_args();print(json.dumps(seal(a.run,a.bundle,a.prior,a.compress_raw_transport)))
