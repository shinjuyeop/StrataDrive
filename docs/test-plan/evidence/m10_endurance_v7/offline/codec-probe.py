import sys,ctypes,time,json,hashlib
from pathlib import Path
sys.path[:0]=[str(Path.cwd()/'tests/integration/perception')]
from endurance_recording_v1 import Zstd,RawReader
p=Path('build/m10-endurance-v6/normal-30s-01-archive-check/run/capture/paired/renderer');rows=json.loads((p/'result.json').read_text())['raw'][::5];reader=RawReader(p);raw=[reader.read(r) for r in rows];reader.close();codec=Zstd();stats=[]
for level in [1,-1,-3]:
 start=time.monotonic();cpu=time.process_time();sizes=[]
 for value in raw:
  buf=ctypes.create_string_buffer(codec.lib.ZSTD_compressBound(len(value)));n=codec.lib.ZSTD_compress(buf,len(buf),value,len(value),level);assert not codec.lib.ZSTD_isError(n)
  stored=ctypes.string_at(buf,n);assert codec.decompress(stored,len(value))==value;sizes.append(n)
 stats.append(dict(level=level,frames=len(raw),seconds=time.monotonic()-start,cpu_seconds=time.process_time()-cpu,sizes=sizes))
Path('build/m10-endurance-v7/codec-probe.json').write_text(json.dumps(stats,indent=2));print(json.dumps(stats))
