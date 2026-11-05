#!/usr/bin/env python3
"""Offline, exclusive byte-preserving diagnostic journal archive/verify/restore.

Does not clear DTCs, rotate a live store, reclaim capacity, or authenticate data.
The native Recorder remains responsible for semantic replay and service admission.
"""
import argparse
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import tarfile
import tempfile
import zlib

NAMES={'manifest','commit','journal','lock','incomplete','pending'}
REQUIRED={'manifest','commit','journal','lock'}
MAX_BYTES=64*1024*1024


def require(ok, message):
    if not ok:raise ValueError(message)


def digest(data):return hashlib.sha256(data).hexdigest()


def crc(data,magic,size=None):
    require((size is None or len(data)==size) and len(data)>=12 and data[:8]==magic and
            struct.unpack_from('<I',data,len(data)-4)[0]==zlib.crc32(data[:-4]), 'journal CRC/format')


def describe(files):
    require(REQUIRED<=files.keys()<=NAMES,'store file set')
    m,c,j=files['manifest'],files['commit'],files['journal']
    crc(m,b'SDDMAN\x01\0',40);crc(c,b'SDDCMT\x01\0',28)
    store,events,records,occurrences,clears,registry=struct.unpack_from('<QIIIII',m,8)
    require(store and 1<=registry<=4 and 1<=events<=4096 and 1<=records<=4096 and 1<=occurrences<=4096 and 1<=clears<=4096,'manifest bounds')
    count,end=struct.unpack_from('<QQ',c,8)
    require(end<=len(j)<=MAX_BYTES and count<=events+clears,'committed bounds')
    cursor=0;event_count=clear_count=0
    for ordinal in range(1,count+1):
        require(cursor+24<=end,'truncated frame');number,length=struct.unpack_from('<QI',j,cursor+8)
        require(number==ordinal and 1<=length<=256*1024 and cursor+length+24<=end,'frame ordinal/length')
        frame=j[cursor:cursor+length+24];crc(frame,b'SDDEVT\x01\0');tag=frame[20]
        require(tag in (0,1,2),'entry tag')
        event_count+=tag==0;clear_count+=tag!=0;cursor+=length+24
    require(cursor==end and event_count<=events and clear_count<=clears,'capacity/watermark')
    return dict(schema=1,store_id=store,registry=registry,entries=count,event_entries=event_count,
                event_capacity=events,service_entries=clear_count,service_capacity=clears,
                uncommitted_bytes=len(j)-end,incomplete='incomplete' in files,
                semantic_replay_checked=False,files={name:dict(size=len(data),sha256=digest(data)) for name,data in sorted(files.items())})


def read_file(directory,name):
    fd=os.open(name,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
    try:
        info=os.fstat(fd);limit=MAX_BYTES if name=='journal' else 4096
        require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_nlink==1 and not info.st_mode&0o077 and info.st_size<=limit,'private regular store file')
        with os.fdopen(fd,'rb',closefd=False) as f:data=f.read(limit+1)
        require(len(data)==info.st_size,'store changed during read');return data
    finally:os.close(fd)


def verify(path):
    files={};metadata=None;total=0
    with tarfile.open(path,'r:gz') as archive:
        for member in archive:
            require(member.isfile() and member.name not in files and member.size>=0,'archive regular unique member')
            require(member.name=='archive.json' or member.name in NAMES,'archive path')
            limit=MAX_BYTES if member.name=='journal' else 4096
            total+=member.size;require(member.size<=limit and total<=MAX_BYTES+16384,'archive bounds')
            data=archive.extractfile(member).read(limit+1)
            require(len(data)==member.size,'archive member length')
            if member.name=='archive.json':
                require(metadata is None,'duplicate metadata');metadata=json.loads(data)
            else:files[member.name]=data
    expected=describe(files);require(metadata==expected,'archive content hashes/metadata')
    return expected,files


def archive_store(source,destination):
    source=Path(source);destination=Path(destination)
    directory=os.open(source,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW)
    lock=None;temporary=None
    try:
        info=os.fstat(directory);require(info.st_uid==os.getuid() and not info.st_mode&0o077,'private store directory')
        lock=os.open('lock',os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        names=set(os.listdir(directory));require(REQUIRED<=names<=NAMES,'unknown/missing store file')
        files={name:read_file(directory,name) for name in sorted(names)};metadata=describe(files)
        fd,temporary=tempfile.mkstemp(prefix='.diagnostic-archive-',dir=destination.parent)
        with os.fdopen(fd,'wb') as output:
            with tarfile.open(fileobj=output,mode='w:gz') as archive:
                for name,data in [('archive.json',(json.dumps(metadata,sort_keys=True)+'\n').encode()),*files.items()]:
                    item=tarfile.TarInfo(name);item.size=len(data);item.mode=0o600;archive.addfile(item,io.BytesIO(data))
            output.flush();os.fsync(output.fileno())
        verify(temporary)
        os.link(temporary,destination) # exclusive publication; never replace an older archive
        os.unlink(temporary);temporary=None
        parent=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(parent)
        finally:os.close(parent)
        return metadata
    finally:
        if temporary is not None:os.unlink(temporary)
        if lock is not None:os.close(lock)
        os.close(directory)


def restore(archive,destination):
    metadata,files=verify(archive);destination=Path(destination);destination.mkdir(mode=0o700)
    directory=os.open(destination,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW)
    try:
        # Native FileJournal cannot open until the final lock file exists.
        for name in [n for n in files if n!='lock']+['lock']:
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_CLOEXEC|os.O_NOFOLLOW,0o600,dir_fd=directory)
            with os.fdopen(fd,'wb') as output:output.write(files[name]);output.flush();os.fsync(output.fileno())
            os.fsync(directory)
        parent=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(parent)
        finally:os.close(parent)
    finally:os.close(directory)
    return metadata


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='operation',required=True)
    for name in ('archive','restore'):
        q=sub.add_parser(name);q.add_argument('source',type=Path);q.add_argument('destination',type=Path)
    q=sub.add_parser('verify');q.add_argument('source',type=Path);args=p.parse_args()
    if args.operation=='archive':result=archive_store(args.source,args.destination)
    elif args.operation=='restore':result=restore(args.source,args.destination)
    else:result=verify(args.source)[0]
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
