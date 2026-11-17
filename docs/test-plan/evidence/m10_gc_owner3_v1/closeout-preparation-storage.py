"""Remove the byte-checked frozen-test extraction, retaining its source archive."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[4]
SERIES=Path(__file__).resolve().parent
source=ROOT/'build/m10-gc-owner3-v1/frozen-tests/source'
manifest=json.loads((SERIES/'sources.json').read_text())
proof=json.loads((SERIES/'frozen-tests.json').read_text())
assert proof['status']=='PASS' and proof['focused_tests']==114
assert hashlib.sha256((SERIES/'sources.tar.gz').read_bytes()).hexdigest()==manifest['archive_sha256']
files={str(p.relative_to(source)):p for p in source.rglob('*') if p.is_file()}
extra=set(files)-set(manifest['files'])
assert all('__pycache__' in Path(n).parts and n.endswith('.pyc') for n in extra)
for name,item in manifest['files'].items():
    path=files[name]
    assert not path.is_symlink() and path.stat().st_size==item['bytes'],name
    assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],name
result=dict(status='PASS_CHECKED_DUPLICATE_REMOVAL',path=str(source.relative_to(ROOT)),
    source_files=len(manifest['files']),generated_bytecode_files=len(extra),
    removed_bytes=sum(p.stat().st_size for p in files.values()),
    retained_archive='sources.tar.gz',archive_sha256=manifest['archive_sha256'])
target=SERIES/'preparation-storage.json'
assert not target.exists()
shutil.rmtree(source)
result['final_free_bytes']={p:shutil.disk_usage(p).free for p in ('/tmp','/d')}
target.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
