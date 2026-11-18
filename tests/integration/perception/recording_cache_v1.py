"""Bounded Linux cache hints for closed raw shards; never delete or rewrite data."""
import ctypes
import mmap
import os
from pathlib import Path
import queue
import stat
import threading
import time


def resident_pages(fd, size):
    pages=(size+mmap.PAGESIZE-1)//mmap.PAGESIZE
    with mmap.mmap(fd,size,access=mmap.ACCESS_COPY) as view:
        address=ctypes.addressof(ctypes.c_char.from_buffer(view))
        vector=(ctypes.c_ubyte*pages)()
        libc=ctypes.CDLL(None,use_errno=True)
        if libc.mincore(ctypes.c_void_p(address),ctypes.c_size_t(size),vector):
            raise OSError(ctypes.get_errno(),'mincore')
        return sum(bool(value&1) for value in vector)


def release(path):
    begin=time.monotonic_ns()
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size<=0:
            raise ValueError('closed nonempty regular shard required')
        resident_before=resident_pages(fd,before.st_size)
        os.fdatasync(fd)
        synced=time.monotonic_ns()
        os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED)
        resident_after=resident_pages(fd,before.st_size)
        after=os.fstat(fd)
        fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
        if any(getattr(before,k)!=getattr(after,k) for k in fields):
            raise ValueError('shard changed during read-only cache release')
        return dict(archive=Path(path).name,bytes=before.st_size,begin_ns=begin,
                    synced_ns=synced,end_ns=time.monotonic_ns(),
                    resident_pages_before=resident_before,resident_pages_after=resident_after,
                    page_bytes=mmap.PAGESIZE,status='HINT_APPLIED')
    finally:os.close(fd)


class CacheRelease:
    def __init__(self):
        self.queue=queue.Queue(2);self.records=[];self.errors=[]
        self.thread=threading.Thread(target=self.run,name='closed-shard-cache',daemon=True)
        self.thread.start()

    def offer(self,path):
        try:self.queue.put_nowait(Path(path))
        except queue.Full:self.errors.append('cache release queue full: '+Path(path).name)

    def run(self):
        from endurance_host_v1 import mark_thread
        mark_thread('m10-cache')
        while True:
            path=self.queue.get()
            try:
                if path is None:return
                try:self.records.append(release(path))
                except Exception as error:self.errors.append(f'{path.name}: {type(error).__name__}: {error}')
            finally:self.queue.task_done()

    def close(self,until):
        try:self.queue.put(None,timeout=max(0,until-time.monotonic()))
        except queue.Full:return False
        self.thread.join(max(0,until-time.monotonic()))
        return not self.thread.is_alive()

    def report(self):
        return dict(enabled=True,workers=1,capacity=2,stopped=not self.thread.is_alive(),
                    records=list(self.records),errors=list(self.errors),
                    operation='closed shard fdatasync then POSIX_FADV_DONTNEED; bytes retained')
