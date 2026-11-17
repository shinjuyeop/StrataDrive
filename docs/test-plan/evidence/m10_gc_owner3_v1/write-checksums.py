"""Catalog final artifacts, reusing independently verified large archive hashes."""
import hashlib,json
from pathlib import Path
SERIES=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
known={};basis={}
def add(path,item,proof):
 if not path.exists():raise ValueError('missing retained archive: '+str(path))
 if 'bytes' in item and path.stat().st_size!=item['bytes']:raise ValueError('stored archive size changed')
 known[str(path.relative_to(SERIES))]=item['sha256'];basis[str(path.relative_to(SERIES))]=proof
source=read(SERIES/'sources.json');add(SERIES/'sources.tar.gz',dict(sha256=source['archive_sha256']),'frozen-source extraction and archive validation')
for case in ('normal-30s-01','normal-30s-02','normal-300s-01'):
 bundle=SERIES/case
 if not (bundle/'disposition.json').exists():continue
 assert read(bundle/'archive-validation.json')['status']=='PASS'
 assert read(bundle/'compaction-validation.json')['status']=='PASS'
 raw=read(bundle/'raw-manifest.json');proof=read(bundle/'archive-compaction.json')
 assert len(raw['archives'])==len(proof['archives'])
 for item,check in zip(raw['archives'],proof['archives']):
  assert check['stored']=={k:item[k] for k in ('bytes','sha256')}
  add(bundle/item['archive'],item,'lossless compactor stored-file SHA256 plus independent expanded original-tar SHA256')
 for stem in ('run-manifest','retained-metadata','bounded-review'):
  item=read(bundle/(stem+'.json'));add(bundle/item['archive'],item,stem+' with independent extraction/member checks')
metadata=dict(scope='Large archive hashes reused from completed independent checks; file sizes rechecked. All other final files freshly hashed. This catalog is not an additional full archive reread.',reused=basis)
(SERIES/'checksum-basis.json').write_text(json.dumps(metadata,indent=2)+'\n')
rows=[]
for p in sorted(SERIES.rglob('*')):
 if not p.is_file() or '__pycache__' in p.parts or p.name=='SHA256SUMS':continue
 name=str(p.relative_to(SERIES));digest=known.get(name)
 if digest is None:digest=hashlib.sha256(p.read_bytes()).hexdigest()
 rows.append(digest+'  '+name+'\n')
(SERIES/'SHA256SUMS').write_text(''.join(rows))
print(json.dumps(dict(files=len(rows),reused_independently_verified_archives=len(known))))
