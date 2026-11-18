#!/usr/bin/env python3
"""Reversible, byte-verified NVMe placement of observed CARLA asset reads.

Original files are renamed beside their original path, never deleted. A durable
plan makes interrupted install/restore recoverable. No engine may run during
installation or restoration. This changes storage placement, not asset bytes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time

ALLOWED=(Path('/d/shin/stratadrive-tools/UnrealEngine_4.26/Engine'),
    Path('/d/shin/stratadrive-tools/m7-source/carla-0.9.16/Unreal/CarlaUE4'))
SUFFIXES={'.uasset','.umap','.udd','.ddc','.xodr'}
MAX_BYTES=8*1024**3
RESERVE_BYTES=57227083776+4*1024**3  # unchanged300s recorder ceiling plus4GiB


def identity(path):
    h=hashlib.sha256();size=0
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            h.update(block);size+=len(block)
    return dict(bytes=size,sha256=h.hexdigest())


def save(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w') as out:
        json.dump(value,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
    os.replace(temporary,path)
    fd=os.open(path.parent,os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def stopped():
    names=subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()
    if any(n.startswith(('UE4Editor','CarlaUE4-Linux')) for n in names):
        raise RuntimeError('stop all engine processes before changing asset storage')


def stage(inventory,cache):
    stopped();cache=Path(cache).absolute()
    if cache.exists():raise ValueError('fresh cache directory required')
    files=json.loads(Path(inventory).read_text())['files']
    selected=[]
    for name in sorted(files):
        path=Path(name)
        if path.suffix not in SUFFIXES:continue
        if not path.is_absolute() or path.is_symlink() or not any(path.is_relative_to(root) for root in ALLOWED):
            raise ValueError('only observed regular engine/project asset paths')
        info=path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid():
            raise ValueError('owned, unaliased regular source asset required')
        selected.append((path,info))
    total=sum(s.st_size for _,s in selected)
    if not selected or total>MAX_BYTES:raise ValueError('bounded8GiB observed asset set')
    if shutil.disk_usage(cache.parent).free-total<RESERVE_BYTES:
        raise ValueError('preserve the complete300s raw-recording budget on NVMe')
    cache.mkdir(mode=0o700);(cache/'files').mkdir()
    plan=dict(schema='m10-observed-asset-cache-v1',status='STAGING',
        inventory=str(Path(inventory).resolve()),inventory_identity=identity(inventory),
        cache=str(cache),bytes=total,entries=[],scope=__doc__)
    for i,(path,info) in enumerate(selected):
        target=cache/'files'/f'{i:05d}{path.suffix}'
        expected=identity(path);shutil.copy2(path,target)
        if identity(target)!=expected:raise ValueError('copied asset differs')
        after=path.stat()
        if (info.st_ino,info.st_size,info.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('asset changed while copied')
        backup=path.with_name(path.name+'.stratadrive-m10-original')
        if backup.exists() or backup.is_symlink():raise ValueError('existing original backup must be recovered first')
        plan['entries'].append(dict(path=str(path),target=str(target),backup=str(backup),
            original_device=info.st_dev,original_inode=info.st_ino,mode=stat.S_IMODE(info.st_mode),
            mtime_ns=info.st_mtime_ns,**expected))
        if (i+1)%1000==0:print('staged',i+1,'/',len(selected),flush=True)
    plan['status']='STAGED_ORIGINALS_UNCHANGED';save(cache/'plan.json',plan)
    return plan


def load(cache):
    cache=Path(cache).absolute();plan=json.loads((cache/'plan.json').read_text())
    if plan['schema']!='m10-observed-asset-cache-v1' or plan['cache']!=str(cache):raise ValueError('cache plan identity')
    originals=set();targets=set()
    for item in plan['entries']:
        path,target,backup=(Path(item[k]) for k in ('path','target','backup'))
        if (not path.is_absolute() or not any(path.is_relative_to(root) for root in ALLOWED)
                or '..' in path.parts or path.parent.resolve()/path.name!=path
                or path.suffix not in SUFFIXES or backup!=path.with_name(path.name+'.stratadrive-m10-original')
                or target.parent!=cache/'files' or path in originals or target in targets):
            raise ValueError('bounded original/backup/cache path mapping')
        originals.add(path);targets.add(target)
    if not originals or sum(i['bytes'] for i in plan['entries'])>MAX_BYTES:raise ValueError('bounded cache plan')
    return plan


def expected(item):return {k:item[k] for k in ('bytes','sha256')}


def validate_installed(cache):
    plan=load(cache)
    if plan['status']!='INSTALLED':raise ValueError('declared cache installation required')
    mutable=[]
    for item in plan['entries']:
        path,target,backup=(Path(item[k]) for k in ('path','target','backup'))
        if not path.is_symlink() or os.readlink(path)!=str(target) or not backup.is_file() or backup.is_symlink():
            raise ValueError('original retained and exact cache link required')
        got=identity(target)
        if got!=expected(item):
            if path.suffix not in ('.udd','.ddc'):raise ValueError('immutable asset cache bytes changed')
            mutable.append(dict(path=str(path),original=expected(item),current=got))
    return dict(status='PASS_ASSET_BYTES_AND_STORAGE_LINKS',files=len(plan['entries']),
        bytes=plan['bytes'],cache_device=Path(cache).stat().st_dev,
        original_devices=sorted({i['original_device'] for i in plan['entries']}),
        mutable_derived_cache_changes=mutable,checked_ns=time.monotonic_ns())


def install(cache):
    stopped();plan=load(cache)
    # Validate all sources and cache bytes before the first namespace change.
    for item in plan['entries']:
        path,target,backup=(Path(item[k]) for k in ('path','target','backup'))
        if backup.exists() or backup.is_symlink() or path.is_symlink():raise ValueError('restore an earlier installation first')
        info=path.stat()
        if (info.st_dev,info.st_ino)!=(item['original_device'],item['original_inode']):raise ValueError('original inode changed')
        if identity(path)!=expected(item) or identity(target)!=expected(item):raise ValueError('original/cache bytes changed')
    plan['status']='INSTALLING';save(Path(cache)/'plan.json',plan)
    try:
        for item in plan['entries']:
            path,target,backup=(Path(item[k]) for k in ('path','target','backup'))
            info=path.stat()
            if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)!=(item['original_device'],item['original_inode'],item['bytes'],item['mtime_ns']):
                raise ValueError('original changed after preflight')
            path.rename(backup);path.symlink_to(target)
        os.sync()
        plan['status']='INSTALLED';save(Path(cache)/'plan.json',plan)
    except BaseException:
        restore(cache)
        raise
    return dict(status='INSTALLED',files=len(plan['entries']),bytes=plan['bytes'],plan=identity(Path(cache)/'plan.json'))


def restore(cache):
    stopped();plan=load(cache);restored=0;changed=[]
    # Refuse an unrelated replacement, but support the crash between rename and
    # symlink. Changed cache contents are retained; never overwrite originals.
    for item in plan['entries']:
        path,target,backup=(Path(item[k]) for k in ('path','target','backup'))
        original=backup if backup.exists() else path
        if original.is_symlink() or identity(original)!=expected(item):raise ValueError('preserved original identity')
        info=original.stat()
        if (info.st_dev,info.st_ino)!=(item['original_device'],item['original_inode']):raise ValueError('preserved original inode')
        if backup.exists() and (path.exists() or path.is_symlink()) and (not path.is_symlink() or os.readlink(path)!=str(target)):
            raise ValueError('unexpected replacement at original asset path')
    for item in plan['entries']:
        path,target,backup=(Path(item[k]) for k in ('path','target','backup'))
        if identity(target)!=expected(item):changed.append(str(target))
        if backup.exists():os.replace(backup,path);restored+=1
    os.sync()
    plan['status']='RESTORED';save(Path(cache)/'plan.json',plan)
    result=dict(status='PASS_ORIGINALS_RESTORED',files=len(plan['entries']),restored=restored,
        modified_cache_files=changed,cache_retained=True,checked_ns=time.monotonic_ns())
    save(Path(cache)/('restoration-'+str(result['checked_ns'])+'.json'),result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('stage','install','restore'))
    p.add_argument('--cache',type=Path,required=True);p.add_argument('--inventory',type=Path)
    a=p.parse_args()
    result=stage(a.inventory,a.cache) if a.action=='stage' else globals()[a.action](a.cache)
    print(json.dumps({k:v for k,v in result.items() if k!='entries'}))
