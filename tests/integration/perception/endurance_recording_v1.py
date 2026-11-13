"""Bounded lossless raw recording into immutable tar shards during endurance runs."""
import ctypes
import ctypes.util
import hashlib
import io
import os
from pathlib import Path
import queue
import tarfile
import threading
import time

from PIL import Image


class Zstd:
    def __init__(self):
        self.buffers=threading.local()
        self.lib=ctypes.CDLL(ctypes.util.find_library('zstd'))
        self.lib.ZSTD_compressBound.argtypes=[ctypes.c_size_t];self.lib.ZSTD_compressBound.restype=ctypes.c_size_t
        self.lib.ZSTD_compress.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int]
        self.lib.ZSTD_compress.restype=ctypes.c_size_t
        self.lib.ZSTD_decompress.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t]
        self.lib.ZSTD_decompress.restype=ctypes.c_size_t
        self.lib.ZSTD_isError.argtypes=[ctypes.c_size_t];self.lib.ZSTD_isError.restype=ctypes.c_uint

    def compress(self,raw):
        required=self.lib.ZSTD_compressBound(len(raw))
        buffer=getattr(self.buffers,'compress',None)
        if buffer is None or len(buffer)<required:
            buffer=ctypes.create_string_buffer(required);self.buffers.compress=buffer
        size=self.lib.ZSTD_compress(buffer,len(buffer),raw,len(raw),1)
        if self.lib.ZSTD_isError(size):raise ValueError('zstd compression')
        return ctypes.string_at(buffer,size)

    def decompress(self,raw,size):
        buffer=ctypes.create_string_buffer(size)
        result=self.lib.ZSTD_decompress(buffer,size,raw,len(raw))
        if self.lib.ZSTD_isError(result) or result!=size:raise ValueError('zstd original size')
        return buffer.raw


def digest(raw):return hashlib.sha256(raw).hexdigest()


class ShardRecorder:
    """Two workers, queue8, no discarded real frames, finite bytes/frame budget."""
    def __init__(self,root,max_frames,max_bytes,*,capacity=8,shard_bytes=256*1024**2,codec=None,encoding='zstd1'):
        if not 1<=capacity<=16 or not 1<=max_frames<=6400 or max_bytes<=0 or shard_bytes<=0:
            raise ValueError('finite recorder budget')
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        if encoding not in ('zstd1','bgra'):raise ValueError('declared lossless encoding')
        self.encoding=encoding
        self.max_frames,self.max_bytes=max_frames,max_bytes
        self.shard_bytes=shard_bytes;self.codec=codec or Zstd();self.queue=queue.Queue(capacity)
        self.lock=threading.Lock();self.records=[];self.errors=[];self.overflow=[];self.archives=[]
        self.offered=0;self.peak=0;self.closed=False;self.total=0;self.current=None;self.archive_bytes=0
        self.threads=[threading.Thread(target=self.run,name=f'lossless-shard-{i}',daemon=True) for i in range(2)]
        for thread in self.threads:thread.start()

    def offer(self,row,raw):
        if self.closed or type(raw) is not bytes or type(row.get('frame')) is not int or row['frame']<=0:
            raise ValueError('open recorder with immutable frame')
        self.offered+=1
        if self.offered>self.max_frames:
            self.overflow.append(row['frame']);self.write(dict(row),raw);return False
        try:
            self.queue.put_nowait((dict(row),raw));self.peak=max(self.peak,self.queue.qsize());return True
        except queue.Full:
            # Only the renderer callback waits on emergency preservation. This
            # marks FAIL; the physical owner never waits on this recorder.
            self.overflow.append(row['frame']);self.write(dict(row),raw);return False

    def write(self,row,raw):
        try:
            begin=time.monotonic_ns();cpu_begin=time.thread_time_ns();stored=self.codec.compress(raw) if self.encoding=='zstd1' else raw
            compressed=time.monotonic_ns();cpu_compressed=time.thread_time_ns()
            rgb=Image.frombytes('RGB',(row['width'],row['height']),raw,'raw','BGRX').tobytes()
            raw_digest=digest(raw)
            item=dict(row,path=f"{row['frame']}.bgra"+('.zst' if self.encoding=='zstd1' else ''),codec=self.encoding,raw_bytes=len(raw),
                stored_bytes=len(stored),stored_sha256=raw_digest if stored is raw else digest(stored),bgra_sha256=raw_digest,rgb_sha256=digest(rgb),
                write_begin_ns=begin)
            if os.environ.get('STRATADRIVE_M10_PROFILE')=='1':
                item['profile']=dict(thread_id=threading.get_native_id(),compression_ns=compressed-begin,
                    compression_cpu_ns=cpu_compressed-cpu_begin,hash_conversion_ns=time.monotonic_ns()-compressed,
                    hash_conversion_cpu_ns=time.thread_time_ns()-cpu_compressed)
            with self.lock:
                if self.current is None or self.archive_bytes+len(stored)>self.shard_bytes:
                    if self.current:self.current.close()
                    name=f'raw-camera-{len(self.archives)+1:03d}.tar';self.archives.append(name)
                    self.current=tarfile.open(self.root/name,'x');self.archive_bytes=0
                info=tarfile.TarInfo(item['path']);info.size=len(stored);info.mtime=0
                self.current.addfile(info,io.BytesIO(stored));self.archive_bytes+=len(stored);self.total+=len(stored)
                item.update(archive=self.archives[-1],write_end_ns=time.monotonic_ns());self.records.append(item)
                if self.total>self.max_bytes:self.errors.append('declared stored-byte budget exceeded')
        except Exception as error:
            with self.lock:self.errors.append(f'{type(error).__name__}: {error}')

    def run(self):
        from endurance_host_v1 import mark_thread
        mark_thread('m10-recorder')
        while True:
            value=self.queue.get()
            try:
                if value is None:return
                self.write(*value)
            finally:self.queue.task_done()

    def close(self,timeout=30):
        self.closed=True;until=time.monotonic()+timeout
        for _ in self.threads:
            try:self.queue.put(None,timeout=max(0,until-time.monotonic()))
            except queue.Full:return False
        for thread in self.threads:thread.join(max(0,until-time.monotonic()))
        stopped=not any(t.is_alive() for t in self.threads)
        if stopped and self.current:self.current.close();self.current=None
        return stopped

    def report(self):
        with self.lock:
            return dict(mode='bounded-zstd-shards' if self.encoding=='zstd1' else 'bounded-bgra-shards',offered=self.offered,records=sorted(self.records,key=lambda x:x['frame']),
                capacity=self.queue.maxsize,workers=2,peak_queue_frames=self.peak,stored_bytes=self.total,
                max_frames=self.max_frames,max_stored_bytes=self.max_bytes,archives=list(self.archives),
                errors=list(self.errors),overflow=list(self.overflow),stopped=not any(t.is_alive() for t in self.threads))

    def failed(self):
        with self.lock:return bool(self.errors or self.overflow)


class RawReader:
    def __init__(self,root):self.root=Path(root);self.archive=None;self.name=None;self.codec=Zstd()
    def read(self,row):
        if self.name!=row['archive']:
            self.close();self.name=row['archive'];self.archive=tarfile.open(self.root/self.name)
        stored=self.archive.extractfile(row['path']).read()
        if len(stored)!=row['stored_bytes'] or digest(stored)!=row['stored_sha256']:raise ValueError('stored raw identity')
        if row['codec']=='zstd1':return self.codec.decompress(stored,row['raw_bytes'])
        if row['codec']=='bgra' and len(stored)==row['raw_bytes']:return stored
        raise ValueError('declared raw encoding/size')
    def close(self):
        if self.archive:self.archive.close();self.archive=None
