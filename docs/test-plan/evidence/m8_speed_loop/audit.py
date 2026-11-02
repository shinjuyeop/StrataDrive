import gzip, hashlib, importlib.util, json, re, shutil, tarfile, tempfile
from pathlib import Path
root=Path.cwd(); evidence=root/'docs/test-plan/evidence/m8_speed_loop'
def sha(data):return hashlib.sha256(data).hexdigest()
archive=json.loads((evidence/'archive-map.json').read_text())
for row in archive:
    data=(evidence/row['archive']).read_bytes()
    if row['gzip']:data=gzip.decompress(data)
    assert len(data)==row['bytes'] and sha(data)==row['sha256'],row
manifest=json.loads((evidence/'build-manifest.json').read_text())
with tarfile.open(evidence/'source.tar.gz') as tar:
    for path,digest in manifest['source_hashes'].items():
        assert sha(tar.extractfile(path).read())==digest,path
        assert sha((root/path).read_bytes())==digest,path
for cohort in ('normal','sanitized'):
    run=json.loads((evidence/cohort/'manifest.json').read_text())
    for path,digest in run['sources'].items():
        assert manifest['source_hashes'][path]==digest,(cohort,path)
    assert run['binary_sha256']==manifest['binaries'][f'build/m8-speed-pi/{cohort}/speed_loop_run']
spec=importlib.util.spec_from_file_location('judge',root/'tests/integration/longitudinal/check_speed_loop.py')
judge=importlib.util.module_from_spec(spec);spec.loader.exec_module(judge)
checks=[]
with tempfile.TemporaryDirectory() as temp:
    work=Path(temp)
    for cohort in ('normal','sanitized'):
        for mode in ('nominal','feedback-loss','command-loss'):
            target=work/cohort/mode;target.mkdir(parents=True)
            for p in (evidence/cohort/mode).iterdir():
                if p.suffix=='.gz':(target/p.stem).write_bytes(gzip.decompress(p.read_bytes()))
                else:shutil.copy2(p,target/p.name)
            actual=judge.judge(target)
            expected=json.loads((target/'verdict.json').read_text())
            assert actual['pass'] and all(expected[k]==v for k,v in actual.items()),(cohort,mode)
            checks.append(cohort+'/'+mode)
# Previous component evidence remains byte-identical.
old=root/'docs/test-plan/evidence/m8_speed_pi';old_count=0
for line in (old/'SHA256SUMS').read_text().splitlines():
    digest,path=line.split(maxsplit=1);path=path.lstrip('*')
    assert sha((old/path).read_bytes())==digest,path;old_count+=1
files=[root/p for p in ('docs/project-status.md','docs/roadmap.md','docs/interfaces/simple-vehicle-model.md','docs/interfaces/vehicle-energy.md','docs/learning/vehicle-models-guide.md','docs/test-plan/README.md','docs/test-plan/verification-strategy.md','docs/test-plan/speed-loop-protocol.md','docs/archive/design-decisions.md')]+[evidence/'README.md']
links=0
link_targets=[]
for p in files:
    for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text()):
        link=link.split('#')[0].strip('<>')
        if not link or '://' in link or link.startswith('mailto:'):continue
        link_targets.append((p,p.parent/link))
        links+=1
# Preserve the audit program itself, then seal the evidence package.
shutil.copy2(Path(__file__),evidence/'audit.py')
result=dict(pass_=True,archive_files=len(archive),snapshot_sources=len(manifest['source_hashes']),rechecked_cohorts=checks,prior_component_checksum_files=old_count,local_links=links)
(evidence/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
for origin,target in link_targets:
    assert target.exists(),(origin,target)
paths=sorted(p for p in evidence.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
(evidence/'SHA256SUMS').write_text(''.join(sha(p.read_bytes())+'  '+str(p.relative_to(evidence))+'\n' for p in paths))
print(json.dumps(result));print('checksum files',len(paths))
