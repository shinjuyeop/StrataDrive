"""Compress sealed raw tar transport after live work; preserve every original byte."""
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path


def identity(stream):
    h=hashlib.sha256();size=0
    for block in iter(lambda:stream.read(1024*1024),b''):
        h.update(block);size+=len(block)
    return dict(bytes=size,sha256=h.hexdigest())


def file_identity(path):
    with path.open('rb') as stream:return identity(stream)


def local_name(value):
    p=Path(value)
    if p.is_absolute() or '..' in p.parts or len(p.parts)!=1:raise ValueError('local archive name')
    return p


def compact(bundle,checked_run=None):
    bundle=Path(bundle).resolve();manifest_path=bundle/'raw-manifest.json'
    original=manifest_path.read_bytes();manifest=json.loads(original);updated=copy.deepcopy(manifest)
    backup=bundle/'raw-manifest-uncompressed.json';proof_path=bundle/'archive-compaction.json'
    if backup.exists() or proof_path.exists():raise ValueError('compaction already declared')
    changes=[]
    for old,new in zip(manifest['archives'],updated['archives']):
        path=bundle/local_name(old['archive'])
        # Already compressed frame payloads do not benefit from this transport.
        if not old['members'] or not all(n.endswith('.bgra') for n in old['members']):continue
        if path.suffix!='.tar' or path.is_symlink():raise ValueError('owned original raw tar required')
        target=path.with_suffix('.tar.gz')
        if target.exists():raise ValueError('archive destination exists')
        link=None
        if checked_run is not None:
            relative=Path(old['original'])
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('relative run member')
            link=Path(checked_run)/relative
            if not link.is_symlink() or link.resolve()!=path:raise ValueError('checked run link identity')
        expected={k:old[k] for k in ('bytes','sha256')}
        # Hash while writing, then independently hash decompression. Until every
        # archive passes, neither manifest nor any original tar is removed.
        h=hashlib.sha256();size=0
        try:
            with path.open('rb') as source,target.open('xb') as destination:
                with gzip.GzipFile(filename='',mode='wb',fileobj=destination,compresslevel=1,mtime=0) as out:
                    for block in iter(lambda:source.read(1024*1024),b''):
                        h.update(block);size+=len(block);out.write(block)
                destination.flush();os.fsync(destination.fileno())
            if dict(bytes=size,sha256=h.hexdigest())!=expected:raise ValueError('original archive identity')
            with gzip.open(target,'rb') as stream:
                if identity(stream)!=expected:raise ValueError('expanded archive identity')
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        stored=file_identity(target)
        new.update(archive=target.name,**stored)
        changes.append(dict(original=path.name,expanded=expected,archive=target.name,stored=stored,
                            checked_link=str(link) if link else None))
    if not changes:raise ValueError('no uncompressed BGRA archives')
    if manifest_path.read_bytes()!=original:raise ValueError('manifest changed during compaction')
    backup.write_bytes(original)
    proof=dict(schema='m10-post-run-tar-compaction-v1',scope='lossless archive transport only; live records unchanged',
               original_manifest_sha256=hashlib.sha256(original).hexdigest(),archives=changes)
    proof_path.write_text(json.dumps(proof,indent=2)+'\n')
    temporary=bundle/'raw-manifest.compacting.json'
    temporary.write_text(json.dumps(updated,indent=2)+'\n');os.replace(temporary,manifest_path)
    for change in changes:
        if change['checked_link']:
            link=Path(change['checked_link']);replacement=link.with_name(link.name+'.compacting')
            replacement.symlink_to(bundle/change['archive']);os.replace(replacement,link)
    # The durable transport and its expanded whole-tar identity now preserve all
    # member bytes, headers and padding, including unused BGRA alpha channels.
    for change in changes:(bundle/change['original']).unlink()
    return dict(status='PASS',archives=len(changes),
                original_bytes=sum(c['expanded']['bytes'] for c in changes),
                stored_bytes=sum(c['stored']['bytes'] for c in changes))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--checked-run',type=Path)
    a=p.parse_args();print(json.dumps(compact(a.bundle,a.checked_run)))
