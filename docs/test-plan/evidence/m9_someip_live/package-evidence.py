from pathlib import Path
import gzip,hashlib,json,platform,runpy,shutil,subprocess,xml.etree.ElementTree as ET
root=Path.cwd();work=root/'build/m9-someip-work';out=root/'docs/test-plan/evidence/m9_someip_live'
assert not (out/'SHA256SUMS').exists(), 'Never change a sealed bundle'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,indent=2)+'\n')
def copy(p,d,compress=False):
 d.parent.mkdir(parents=True,exist_ok=True)
 if compress or p.suffix in ('.csv','.log','.err','.pcap','.maps','.stderr','.stdout','.txt'):
  Path(str(d)+'.gz').write_bytes(gzip.compress(p.read_bytes(),mtime=0))
 else:shutil.copy2(p,d)
for mode in ('normal','asan','tsan'):
 src=root/('build/m9-someip-final-'+mode)
 for p in src.rglob('*'):
  if p.is_file():copy(p,out/mode/p.relative_to(src))
for p in (root/'build/m9-someip-probe').rglob('*'):
 if p.is_file():copy(p,out/'probe'/p.relative_to(root/'build/m9-someip-probe'))
for p in work.iterdir():
 if p.is_file():copy(p,out/p.name)
for name in ('probe-source','compile-probe-source','before-language-source'):shutil.copytree(work/name,out/name,dirs_exist_ok=True)
changed=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()+subprocess.check_output(['git','ls-files','--others','--exclude-standard'],text=True).splitlines()
changed+=['CMakeLists.txt','tests/integration/diagnostics/audit_control_diagnostics.py','tests/integration/runtime/check_m4_async.py','tests/unit/m4_source_fingerprint_test.py','tests/integration/someip/run.py']
overlay=[]
for n in sorted(set(changed)):
 if n.startswith('docs/test-plan/evidence/'):continue
 p=root/n;d=out/'sources'/n;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);overlay.append(dict(path=n,sha256=sha(p)))
binaries=[]
for mode,directory in [('normal','build/m1-angle'),('asan','build/m1-angle-sanitized')]:
 args=['ctest','--test-dir',directory,'-L','^(unit|integration.logical)$']
 if mode=='asan':args+=['-R','Diagnostic|^NativePower\\.|ControlRecoverySil|Session|M4']
 inventory=json.loads(subprocess.check_output(args+['--show-only=json-v1'],text=True));(out/('test-inventory-'+mode+'.json.gz')).write_bytes(gzip.compress(json.dumps(inventory,indent=2).encode(),mtime=0))
 paths={Path(t['command'][0]) for t in inventory['tests']}
 for p in sorted(paths):
  if p.is_file():binaries.append(dict(mode=mode,path=str(p.relative_to(root)) if p.is_relative_to(root) else str(p),sha256=sha(p)))
 copy(root/directory/'CMakeCache.txt',out/('CMakeCache-core-'+mode+'.txt'))
for mode in ('normal','asan','tsan'):
 directory=root/('build/m5-someip-'+mode);project=directory/'project'
 for p in [project/'tests/integration/someip/someip_diagnostics_live',project/'tests/integration/someip/libsomeip_diagnostic_transport.a',project/'libdiagnostics_delivery.a']:
  binaries.append(dict(mode='sdk-'+mode,path=str(p.relative_to(root)),sha256=sha(p)))
 libraries={p.resolve() for p in (directory/'install/lib').glob('*.so*') if p.is_file()}
 for p in sorted(libraries):binaries.append(dict(mode='sdk-'+mode,path=str(p.relative_to(root)),sha256=sha(p)))
 copy(project/'CMakeCache.txt',out/('CMakeCache-sdk-'+mode+'.txt'));copy(directory/'sdk/CMakeCache.txt',out/('CMakeCache-vendor-'+mode+'.txt'))
copy(root/'build/m9-someip-release/CMakeCache.txt',out/'CMakeCache-release.txt')
p=root/'build/m9-someip-release/tests/integration/someip/libsomeip_diagnostic_transport.a';binaries.append(dict(mode='release',path=str(p.relative_to(root)),sha256=sha(p)))
versions={}
for name,cmd in [('cxx',['c++','--version']),('clang_tidy',['clang-tidy','--version']),('cppcheck',['cppcheck','--version']),('cmake',['cmake','--version']),('python',['python3','--version']),('git',['git','--version'])]:
 r=subprocess.run(cmd,capture_output=True,text=True);versions[name]=(r.stdout+r.stderr).strip()
sdk=root/'build/m5-someip-deps/vsomeip';pin=subprocess.check_output(['git','-C',str(sdk),'rev-parse','HEAD'],text=True).strip();clean=subprocess.check_output(['git','-C',str(sdk),'status','--porcelain'],text=True)
assert pin=='4187431d2815bd351845a09d01aa85b2a3163cab' and not clean
manifest=dict(document_date='2026-11-03',base_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,source_fingerprint=runpy.run_path('tests/integration/runtime/check_m4_async.py')['fingerprint'](),source_overlay=overlay,binaries=binaries,sdk=dict(version='3.7.6',commit=pin,clean=True),tools=versions,platform=platform.platform(),scope='Live logical source over actual SOMEIP/TCP; native 3-ECU owner merge and DDS gate remain OPEN')
write(out/'manifest.json',manifest)
checks={}
for name,expected in [('normal.xml',1172),('asan.xml',239),('wall.xml',2),('binding.xml',2)]:
 cases=ET.parse(work/name).getroot().findall('.//testcase');fails=sum(c.find('failure') is not None or c.find('error') is not None for c in cases);skips=sum(c.find('skipped') is not None for c in cases)
 assert len(cases)==expected and fails==skips==0,(name,len(cases),fails,skips)
 checks[name]=dict(tests=len(cases),failures=fails,skipped=skips,xml=name)
audits={};campaigns={}
for mode,names in [('normal',['normal','loss','drop-ack','restart']),('asan',['normal','loss','drop-ack','restart']),('tsan',['loss'])]:
 rows=json.loads((out/mode/'results.json').read_text());assert len(rows)==len(names) and all(r['exit']==0 for r in rows);campaigns[mode]=dict(cases=len(rows),failed=0,results=mode+'/results.json')
 for case in names:audits[mode+'/'+case]=json.loads((work/('audit-'+mode+'-'+case+'.json')).read_text())
write(out/'results.json',dict(checks=checks,sdk_campaigns=campaigns,audits=audits,static=json.loads((work/'static-result.json').read_text()),fingerprint_tests=2,identical_profiles=40,identical_language_candidates=72,previous_evidence=json.loads((work/'previous-evidence-integrity.json').read_text()),technical_scope=manifest['scope']))
print('overlays',len(overlay),'binary/library hashes',len(binaries),'SDK datasets',len(audits))
