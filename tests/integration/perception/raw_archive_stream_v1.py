"""One sequential pass over every raw tar byte, member and optional image hash."""
import hashlib
import gzip
import os
from pathlib import Path
import tarfile

CHUNK=1024*1024


class DigestingReader:
    def __init__(self,source,destination=None):
        self.source,self.destination=source,destination
        self.digest=hashlib.sha256();self.bytes=0

    def read(self,size=-1):
        block=self.source.read(size)
        self.digest.update(block);self.bytes+=len(block)
        if self.destination is not None:self.destination.write(block)
        return block


def identity(stat):
    return (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)


def inspect(path,expected=None,*,destination=None,frames=None,expanded_expected=None):
    """Inspect a raw tar transport, optionally copying or decoding original images.

    `expected` covers every byte including headers, padding and bytes after tar EOF.
    `frames` supplies the complete original image inventory for this shard.
    A caller copying across devices must inspect the durable destination separately.
    """
    path=Path(path);members={};frame_map=None;codec=None
    if frames is not None:
        frame_map={r['path']:r for r in frames}
        if len(frame_map)!=len(frames):raise ValueError('duplicate original image member')
    with path.open('rb') as source:
        before=identity(os.fstat(source.fileno()))
        compressed=source.read(2)==b'\x1f\x8b';source.seek(0)
        reader=DigestingReader(source,destination)
        # Hash both the stored gzip transport and every expanded original byte,
        # including padding/footer after tar EOF. This also verifies gzip's CRC.
        expanded=DigestingReader(gzip.GzipFile(fileobj=reader,mode='rb')) if compressed else reader
        with tarfile.open(fileobj=expanded,mode='r|',bufsize=CHUNK) as tar:
            for item in tar:
                name=Path(item.name)
                if (not item.isfile() or name.is_absolute() or '..' in name.parts
                        or item.name in members):raise ValueError('raw shard membership')
                h=hashlib.sha256();count=0;blocks=[]
                if frame_map is not None and (item.name not in frame_map or item.size>32*CHUNK):
                    raise ValueError('bounded original image inventory')
                with tar.extractfile(item) as stream:
                    for block in iter(lambda:stream.read(CHUNK),b''):
                        h.update(block);count+=len(block)
                        if frame_map is not None:blocks.append(block)
                if count!=item.size:raise ValueError('truncated raw member')
                member=dict(bytes=count,sha256=h.hexdigest());members[item.name]=member
                if expected is not None and expected['members'].get(item.name)!=member:
                    raise ValueError('raw member identity')
                if frame_map is not None:
                    row=frame_map[item.name];stored=b''.join(blocks)
                    if row['stored_bytes']!=count or row['stored_sha256']!=h.hexdigest():
                        raise ValueError('stored image identity')
                    width,height=row['width'],row['height']
                    if (type(width) is not int or type(height) is not int
                            or not 1<=width<=2560 or not 1<=height<=1536
                            or row['raw_bytes']!=width*height*4):raise ValueError('bounded image dimensions')
                    if row['codec']=='zstd1':
                        if codec is None:
                            from endurance_recording_v1 import Zstd
                            codec=Zstd()
                        bgra=codec.decompress(stored,row['raw_bytes'])
                    elif row['codec']=='bgra':bgra=stored
                    else:raise ValueError('declared raw encoding')
                    if len(bgra)!=row['raw_bytes'] or hashlib.sha256(bgra).hexdigest()!=row['bgra_sha256']:
                        raise ValueError('original BGRA identity')
                    from PIL import Image
                    rgb=Image.frombytes('RGB',(width,height),bgra,'raw','BGRX').tobytes()
                    if hashlib.sha256(rgb).hexdigest()!=row['rgb_sha256']:
                        raise ValueError('original RGB identity')
        # tar iteration stops at its end marker. Hash/copy the entire remaining
        # file too; otherwise padding/footer corruption could escape detection.
        while expanded.read(CHUNK):pass
        if compressed:
            expanded.source.close()
            while reader.read(CHUNK):pass
        if (identity(os.fstat(source.fileno()))!=before or identity(path.stat())!=before
                or reader.bytes!=before[2]):raise ValueError('raw archive changed during inspection')
    result=dict(bytes=reader.bytes,sha256=reader.digest.hexdigest(),members=members)
    if compressed:result['expanded']=dict(bytes=expanded.bytes,sha256=expanded.digest.hexdigest())
    if expected is not None and any(result[k]!=expected[k] for k in ('bytes','sha256','members')):
        raise ValueError('complete raw archive identity')
    expanded_expected=expanded_expected or (expected.get('expanded') if expected else None)
    if expanded_expected is not None and result.get('expanded')!=expanded_expected:
        raise ValueError('expanded original tar identity')
    if frame_map is not None and set(frame_map)!=set(members):
        raise ValueError('complete original image inventory')
    return result
