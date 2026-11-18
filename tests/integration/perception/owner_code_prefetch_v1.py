"""Bounded, read-only file preparation before native START; no residency claim."""
import hashlib
import os
from pathlib import Path
import stat
import time

MAX_BYTES = 2*1024**3
MAX_SECONDS = 60


def ranges(maps):
    """Select non-writable mappings of files having an executable segment."""
    files = {}
    for line in maps.splitlines():
        row = line.split(None, 5)
        if len(row) != 6 or not row[5].startswith('/'):
            continue
        address, perms, offset, device, inode, name = row
        begin, end = (int(v, 16) for v in address.split('-'))
        entry = files.setdefault(name, dict(device=device, inode=int(inode), executable=False, spans=[]))
        if (entry['device'],entry['inode']) != (device,int(inode)):
            raise ValueError('inconsistent mapped file identity')
        entry['executable'] |= 'x' in perms
        if 'r' in perms and 'w' not in perms:
            entry['spans'].append((int(offset,16),int(offset,16)+end-begin))
    selected = []
    for name, entry in sorted(files.items()):
        if not entry['executable']: continue
        if name.endswith(' (deleted)'):
            raise ValueError('deleted mapped executable cannot be prepared')
        merged = []
        for begin, end in sorted(entry['spans']):
            if merged and begin <= merged[-1][1]: merged[-1][1] = max(merged[-1][1],end)
            else: merged.append([begin,end])
        selected.append(dict(path=name, device=entry['device'], inode=entry['inode'], spans=merged))
    if not selected: raise ValueError('no executable file mappings')
    return selected


def owner_identity(pid):
    proc = Path('/proc')/str(pid)
    if proc.stat().st_uid != os.getuid(): raise ValueError('same-user owner required')
    argv = (proc/'cmdline').read_bytes().split(b'\0')
    if (not argv[0].endswith(b'/UE4Editor') or b'-carla-rpc-port=2200' not in argv
            or b'-StrataM7WallNative' not in argv or b'-nullrhi' not in argv):
        raise ValueError('dedicated native physical owner required')
    fields = (proc/'stat').read_text().rsplit(')',1)[1].split()
    return dict(pid=pid, uid=os.getuid(), start_ticks=int(fields[19]), executable=os.fsdecode(argv[0]))


def prefetch(pid):
    begin = time.monotonic_ns(); deadline = begin+MAX_SECONDS*1_000_000_000
    identity = owner_identity(pid)
    mappings = (Path('/proc')/str(pid)/'maps').read_text()
    plan = ranges(mappings); total = 0
    # Validate the complete size/identity plan before doing I/O. ELF page tails
    # may extend beyond EOF; only existing file bytes can be prepared.
    for item in plan:
        info = Path(item['path']).stat()
        device = tuple(int(v,16) for v in item['device'].split(':'))
        if (not stat.S_ISREG(info.st_mode) or info.st_ino != item['inode']
                or (os.major(info.st_dev),os.minor(info.st_dev)) != device):
            raise ValueError('mapped file identity changed')
        item['file_bytes'] = info.st_size; item['mtime_ns'] = info.st_mtime_ns
        item['spans'] = [[lo,min(hi,info.st_size)] for lo,hi in item['spans'] if lo<info.st_size]
        total += sum(hi-lo for lo,hi in item['spans'])
    if total > MAX_BYTES: raise ValueError('owner code preparation exceeds 2GiB bound')
    for item in plan:
        h = hashlib.sha256(); count = 0
        with open(item['path'],'rb',buffering=0) as stream:
            before = os.fstat(stream.fileno())
            if (before.st_ino,before.st_size,before.st_mtime_ns) != (item['inode'],item['file_bytes'],item['mtime_ns']):
                raise ValueError('mapped file replaced before read')
            for lo,hi in item['spans']:
                stream.seek(lo)
                while lo<hi:
                    if time.monotonic_ns()>=deadline: raise TimeoutError('owner code preparation 60s bound')
                    block = stream.read(min(1024*1024,hi-lo))
                    if not block: raise ValueError('mapped file truncated')
                    h.update(block);lo+=len(block);count+=len(block)
            after = os.fstat(stream.fileno())
            if (after.st_ino,after.st_size,after.st_mtime_ns)!=(before.st_ino,before.st_size,before.st_mtime_ns):
                raise ValueError('mapped file changed during read')
        item.update(read_bytes=count,read_sha256=h.hexdigest())
    if owner_identity(pid)!=identity: raise ValueError('physical owner identity changed')
    end = time.monotonic_ns()
    if end>=deadline: raise TimeoutError('owner code preparation 60s bound')
    return dict(status='PREPARED_BEFORE_NATIVE_START',begin_ns=begin,end_ns=end,owner=identity,
        maps_sha256=hashlib.sha256(mappings.encode()).hexdigest(),files=plan,read_bytes=total,
        limit_bytes=MAX_BYTES,limit_seconds=MAX_SECONDS,control_writes=0,
        scope='read-only mapped file bytes; no forced GC, page lock, source retiming or guaranteed residency')
