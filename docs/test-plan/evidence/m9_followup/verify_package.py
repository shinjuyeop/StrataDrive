from pathlib import Path
import hashlib,json,tarfile
base=Path('build/m9-followup');out=Path('docs/test-plan/evidence/m9_followup')
def digest(f):
 h=hashlib.sha256()
 for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def sha(p):
 with p.open('rb') as f:return digest(f)
rows=[]
for path in sorted(out.glob('*.tar.gz')):
 if path.name=='validation.tar.gz':continue # Captures original logs while packaging runs.
 root=Path('.') if path.name=='sources.tar.gz' else base
 count=0;total=0
 with tarfile.open(path,'r:gz') as tar:
  for member in tar:
   if not member.isfile():continue
   original=root/member.name
   with tar.extractfile(member) as f:actual=digest(f)
   assert original.stat().st_size==member.size and sha(original)==actual,(path,member.name)
   count+=1;total+=member.size
 rows.append(dict(artifact=path.name,files=count,original_bytes=total,all_original_hashes_equal=True))
 print(path.name,count,'PASS',flush=True)
for dest in sorted((out/'carla').rglob('*')):
 if not dest.is_file():continue
 source=base/'carla-v2'/dest.relative_to(out/'carla')
 assert sha(dest)==sha(source),str(dest)
rows.append(dict(artifact='carla/',all_original_hashes_equal=True,files=sum(p.is_file() for p in (out/'carla').rglob('*'))))
(out/'package-integrity.json').write_text(json.dumps(dict(passed=True,artifacts=rows),indent=2)+'\n')
