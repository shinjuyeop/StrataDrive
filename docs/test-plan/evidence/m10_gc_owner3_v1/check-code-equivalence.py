"""Check byte-identical computation/module inputs; only the declared CPU plan changes."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent;PRIOR=SERIES.with_name('m10_purge_slice_v1')
read=lambda p:json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
frozen=read(PRIOR/'sources.json');checked=[]
for name,item in frozen['files'].items():
 if name.startswith(('central/','interfaces/','simulation/','vecu/','zone/','tools/carla/m7_nodrive/')):
  assert sha(ROOT/name)==item['sha256'],name;checked.append(name)
engine=read(PRIOR/'code-equivalence.json')['engine_source_and_binary_hashes']
for name,expected in engine.items():assert sha(Path(name))==expected,name
new=read(ROOT/'profiles/perception-endurance-host-v4.json')['cpus'];old=read(ROOT/'profiles/perception-endurance-host-v1.json')['cpus']
assert new['native']==old['native']==[1,9] and new['observer']==old['observer']==[0,8]
assert new['owner']==[2,3,4,10,11,12] and new['renderer']==[5,6,7,13,14,15]
assert set(new['owner'])-set(old['owner'])==set(old['renderer'])-set(new['renderer'])=={4,12}
result=dict(status='PASS_UNCHANGED_COMPUTATION_AND_LAYOUT',baseline_archive_sha256=frozen['archive_sha256'],unchanged_native_and_module_source_files=len(checked),final_admission_body_unchanged=True,original_physics_and_sensor_clock_unchanged=True,physical_age_ns=30000000,preview_reserve_ns=1000000,requested_purge_slice_ns=100000,engine_source_and_binary_hashes=engine,cpu_plan_before=old,cpu_plan_after=new,changes=['transfer physical core 4 and SMT sibling12 from shared renderer/image role to owner','strict declared/observed placement audits; unchanged native and observer cores'])
(SERIES/'code-equivalence.json').write_text(json.dumps(result,indent=2)+'\n');print('Native/model/module sources and engine binaries unchanged; explicit CPU transfer checked.')
