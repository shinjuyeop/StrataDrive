from pathlib import Path
import hashlib,json,os,time
root=Path('/d/shin/StrataDrive');site=root/'build/m10-perception/cuda-venv/lib/python3.10/site-packages/nvidia';dest=root/'build/m10-gc-recovery-v1/diagnostics/private-libraries';dest.mkdir(exist_ok=False)
items=[]
for folder in ('cuda_runtime','cublas','cudnn'):
 for source in sorted((site/folder/'lib').glob('*.so*')):
  if not source.is_file():continue
  target=dest/source.name;assert not target.exists();h=hashlib.sha256();begin=time.monotonic_ns()
  with source.open('rb') as src,target.open('xb') as out:
   for chunk in iter(lambda:src.read(1024*1024),b''):h.update(chunk);out.write(chunk)
   out.flush();os.fsync(out.fileno())
  items.append(dict(source=str(source),path=str(target),bytes=target.stat().st_size,sha256=h.hexdigest(),copy_ns=time.monotonic_ns()-begin))
manifest=dict(scope='private byte-identical diagnostic copies only; no original cache eviction or runtime installation',files=items)
(dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
# Advise only these newly created, unshared diagnostic inodes out of cache.
# This is advisory; actual major faults are measured by the probe.
for item in items:
 with open(item['path'],'rb') as f:os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED)
print(json.dumps(dict(files=len(items),bytes=sum(x['bytes'] for x in items))),flush=True)
