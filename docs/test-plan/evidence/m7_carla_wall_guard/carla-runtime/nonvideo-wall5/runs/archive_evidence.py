from pathlib import Path
import gzip,hashlib,json,subprocess,shutil
root=Path('/d/shin/StrataDrive');work=Path('/d/shin/stratadrive-tools/m7-source/m7-wall-stabilize')
dest=root/'docs/test-plan/evidence/m7_carla_wall_guard/carla-runtime/nonvideo-wall5'
dest.mkdir(parents=True,exist_ok=True);records=[];excluded=[]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''):h.update(c)
 return h.hexdigest()
def copy(p,relative):
 if '__pycache__' in p.parts or p.suffix=='.pyc':return
 with p.open('rb') as f:magic=f.read(4)
 if magic==b'\x7fELF' or p.name=='wall-signal' or p.name=='install-before.json':
  excluded.append(dict(source=str(p),bytes=p.stat().st_size,sha256=sha(p),reason='executed binary identified by hash; not vendored' if magic==b'\x7fELF' else 'transient IPC image or private installer originals; original public proof/source retained separately'));return
 compress=p.suffix in ('.log','.csv','.jsonl','.txt') or (p.suffix=='.json' and p.stat().st_size>150000)
 q=dest/(str(relative)+('.gz' if compress else ''));q.parent.mkdir(parents=True,exist_ok=True)
 if q.exists():raise RuntimeError(f'refuse overwrite: {q}')
 if compress:
  with p.open('rb') as inp,q.open('wb') as out,gzip.GzipFile(fileobj=out,filename='',mode='wb',mtime=0,compresslevel=6) as z:shutil.copyfileobj(inp,z)
 else:shutil.copy2(p,q)
 records.append(dict(source=str(p),stored=str(q.relative_to(dest)),source_bytes=p.stat().st_size,stored_bytes=q.stat().st_size,source_sha256=sha(p),stored_sha256=sha(q),encoding='gzip' if compress else 'identity'))
for p in sorted(work.rglob('*')):
 if p.is_file():copy(p,Path('runs')/p.relative_to(work))
tracked=subprocess.check_output(['git','ls-files','tools/carla/m7_nodrive','tests/integration/carla'],cwd=root,text=True).splitlines()
for name in tracked:copy(root/name,Path('sources')/name)
for p in (root/'build/m7-functional/tests/integration/carla/m7_1f').glob('wall_leaf_owner.*'):copy(p,Path('generated')/p.name)
(dest/'artifact-manifest.json').write_text(json.dumps(dict(base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),files=records,excluded=excluded),indent=2)+'\n')
print(json.dumps(dict(files=len(records),bytes=sum(x['stored_bytes'] for x in records),excluded=len(excluded))))
