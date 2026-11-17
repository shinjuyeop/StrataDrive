"""Remove only this investigation's byte-checked extracted duplicates."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[4]

def read(path):
    return json.loads(path.read_text())

def identity(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return dict(bytes=path.stat().st_size, sha256=h.hexdigest())

result = dict(scope='checked extraction duplicates only; retained source/run/raw/review archives and active builds stay local',
              removed=[], removed_bytes=0, raw_compaction_saved_bytes=0)
for case_name in ('normal-30s-01', 'normal-30s-02', 'normal-300s-01'):
    series = ROOT/'docs/test-plan/evidence/m10_purge_slice_v1'
    bundle = series/case_name
    work = ROOT/'build/m10-purge-slice-v1'
    run = work/case_name/'archive-check/run'
    archive = read(bundle/'run-manifest.json')
    raw = read(bundle/'raw-manifest.json')
    assert read(bundle/'archive-validation.json')['status']=='PASS'
    assert identity(bundle/archive['archive']) == {k: archive[k] for k in ('bytes', 'sha256')}
    links = {item['original']: bundle/item['archive'] for item in raw['archives']}
    if links:
        proof = read(bundle/'archive-compaction.json')
        original = read(bundle/'raw-manifest-uncompressed.json')
        assert len(proof['archives']) == len(raw['archives']) == len(original['archives'])
        for old, new, check in zip(original['archives'], raw['archives'], proof['archives']):
            assert check['expanded'] == {k: old[k] for k in ('bytes', 'sha256')}
            assert check['stored'] == {k: new[k] for k in ('bytes', 'sha256')}
            assert check['original'] == old['archive'] and check['archive'] == new['archive']
            assert (bundle/new['archive']).stat().st_size == new['bytes']
        compact = read(bundle/'compaction-validation.json')
        assert compact['status']=='PASS'
        result['raw_compaction_saved_bytes'] += compact['original_bytes']-compact['stored_bytes']
    files = {str(p.relative_to(run)): p for p in run.rglob('*') if p.is_file() or p.is_symlink()}
    assert set(files) == set(archive['members']) | set(links)
    for name, expected in archive['members'].items():
        assert not files[name].is_symlink() and identity(files[name])==expected
    for name, target in links.items():
        assert files[name].is_symlink() and files[name].resolve()==target.resolve()
    count = sum(v['bytes'] for v in archive['members'].values())
    shutil.rmtree(run)
    result['removed'].append(dict(path=str(run.relative_to(ROOT)), bytes=count, basis='all run-manifest member hashes; raw links point to independently checked compacted archives'))
    result['removed_bytes'] += count
    frozen = read(series/'sources.json')
    for source in (work/case_name/'archive-check/source', work/'frozen-tests/source'):
        if not source.exists():
            continue
        files = {str(p.relative_to(source)): p for p in source.rglob('*') if p.is_file()}
        extra = set(files)-set(frozen['files'])
        assert all('__pycache__' in Path(n).parts and n.endswith('.pyc') for n in extra)
        for name, expected in frozen['files'].items():
            assert identity(files[name])==expected
        count = sum(p.stat().st_size for p in files.values())
        shutil.rmtree(source)
        result['removed'].append(dict(path=str(source.relative_to(ROOT)), bytes=count, basis='all frozen source hashes; optional generated Python bytecode'))
        result['removed_bytes'] += count
result['final_free_bytes'] = {p: shutil.disk_usage(p).free for p in ('/tmp', '/d')}
target = Path(__file__).with_name('storage-closeout.json')
assert not target.exists()
target.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
