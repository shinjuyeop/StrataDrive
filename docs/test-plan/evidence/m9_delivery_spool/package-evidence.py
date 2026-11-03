from pathlib import Path
import gzip,hashlib,json,runpy,shutil,subprocess,xml.etree.ElementTree as ET
root=Path.cwd();work=root/'build/m9-delivery-work';out=root/'docs/test-plan/evidence/m9_delivery_spool'
assert not (out/'SHA256SUMS').exists(), 'Never refresh a sealed bundle'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj): p.write_text(json.dumps(obj,indent=2)+'\n')
def copy(p,d):
 d.parent.mkdir(parents=True,exist_ok=True)
 if p.suffix in ('.csv','.log','.err'): Path(str(d)+'.gz').write_bytes(gzip.compress(p.read_bytes(),mtime=0))
 else: shutil.copy2(p,d)
for mode in ('normal','asan'):
 target=out/mode
 if target.exists(): shutil.rmtree(target)
 source=root/('build/m9-delivery-final-'+mode)
 for p in source.rglob('*'):
  if p.is_file():copy(p,target/p.relative_to(source))
for p in work.iterdir():
 if p.is_file():copy(p,out/p.name)
for name in ('probe-source','before-injection-source'):shutil.copytree(work/name,out/name,dirs_exist_ok=True)
m=json.loads((out/'manifest.json').read_text())
for e in m['source_overlay']:
 p=root/e['path'];shutil.copy2(p,out/'sources'/e['path']);e['sha256']=digest(p)
for e in m['binaries']+m['native_fixture']:e['sha256']=digest(root/e['path'])
m['source_fingerprint']=runpy.run_path('tests/integration/runtime/check_m4_async.py')['fingerprint']();write(out/'manifest.json',m)
r=json.loads((out/'results.json').read_text())
for name,expected in [('normal.xml',1170),('asan.xml',234),('transport-normal.xml',1),('transport-asan.xml',1),('wall.xml',2)]:
 cases=ET.parse(work/name).getroot().findall('.//testcase');fails=sum(c.find('failure') is not None or c.find('error') is not None for c in cases);skips=sum(c.find('skipped') is not None for c in cases)
 assert len(cases)==expected and fails==skips==0,(name,len(cases),fails,skips)
 r['checks'][name]=dict(tests=len(cases),failures=fails,skipped=skips,xml=name)
r['audits']={mode:json.loads((work/('audit-'+mode+'.json')).read_text()) for mode in ('normal','asan')};r['identical_artifacts']=94
r.pop('packaged_audit',None);write(out/'results.json',r)
print('Refreshed final source/binary metadata and datasets; not sealed')
