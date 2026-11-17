"""Read pinned library bytes before model construction; never invoke inference."""

import hashlib
import json
from pathlib import Path
import time

READ_BUDGET_NS = 30_000_000_000
MAX_BYTES = 3 * 1024**3


def prefetch(manifest, root, report, *, clock=time.monotonic_ns):
    """Explicit Host setup I/O, recorded separately from original model probes.

    A completed read does not pin pages or guarantee future residency. Failure
    must prevent model construction. This does not change the loader or files.
    """
    root=Path(root).resolve();manifest=Path(manifest)
    encoded=manifest.read_bytes();spec=json.loads(encoded)
    if (spec.get('schema')!='m10-inference-library-prefetch-v1'
            or spec.get('read_budget_ns')!=READ_BUDGET_NS):
        raise ValueError('explicit library read profile')
    files=spec['files']
    if not isinstance(files,list) or not 1<=len(files)<=32:
        raise ValueError('bounded library list')
    names=set();total=0
    for item in files:
        name=Path(item['path'])
        if (name.is_absolute() or '..' in name.parts or name.as_posix() in names
                or '.so' not in name.name or type(item['bytes']) is not int or item['bytes']<=0
                or len(item['sha256'])!=64 or any(c not in '0123456789abcdef' for c in item['sha256'])):
            raise ValueError('unique relative pinned library identity')
        names.add(name.as_posix());total+=item['bytes']
    if total>MAX_BYTES:raise ValueError('bounded library bytes')
    started=clock();last=started
    if type(started) is not int or started<0:raise ValueError('library read clock type')
    report.update(status='READING',manifest_sha256=hashlib.sha256(encoded).hexdigest(),
        begin_wall_ns=started,read_budget_ns=READ_BUDGET_NS,declared_bytes=total,
        model_calls=0,control_writes=0,files=[])
    def observe():
        nonlocal last
        now=clock()
        if type(now) is not int or now<last:raise ValueError('library read clock regression')
        last=now
        if now-started>=READ_BUDGET_NS:raise TimeoutError('library read deadline')
        return now
    try:
        for item in files:
            observe();path=root/item['path'];resolved=path.resolve()
            if not resolved.is_relative_to(root) or not path.is_file():
                raise ValueError('owned library path')
            before=path.stat()
            if before.st_size!=item['bytes']:raise ValueError('library size changed')
            digest=hashlib.sha256();count=0;begin=observe()
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):
                    digest.update(block);count+=len(block);observe()
                after=path.stat()
                if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
                    raise ValueError('library changed while reading')
            if count!=item['bytes'] or digest.hexdigest()!=item['sha256']:
                raise ValueError('library content changed')
            report['files'].append(dict(**item,begin_wall_ns=begin,end_wall_ns=observe()))
        report.update(status='PASS',end_wall_ns=observe())
    except Exception as error:
        report.update(status='FAIL',error=str(error),end_wall_ns=last)
        raise
    return report
