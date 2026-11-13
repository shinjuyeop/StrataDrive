"""Re-extract sealed evidence and run its frozen paired auditor."""
import argparse,hashlib,importlib.util,json,os,sys,tarfile
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def unpack(bundle,manifest,target):
 m=json.loads((bundle/manifest).read_text());p=bundle/m['archive']
 assert p.stat().st_size==m['bytes'] and sha(p)==m['sha256']
 with tarfile.open(p,'r:*') as t:
  members=t.getmembers();assert len(members)==len(m['members']) and {x.name for x in members}==set(m['members'])
  for x in members:
   n=Path(x.name);assert x.isfile() and not n.is_absolute() and '..' not in n.parts
   data=t.extractfile(x).read();v=m['members'][x.name]
   assert len(data)==v['bytes'] and hashlib.sha256(data).hexdigest()==v['sha256']
   p=target/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)

def main(a):
 bundle=Path(__file__).resolve().parent;a.work.mkdir(parents=True,exist_ok=False)
 seal=json.loads((bundle/'evidence-manifest.json').read_text())
 for n,v in seal['files'].items():
  p=bundle/n;assert p.stat().st_size==v['bytes'] and sha(p)==v['sha256'],n
 source,frozen=module('source_check',bundle/'check-evidence.py').extract(bundle,a.work)
 run=a.work/'run';run.mkdir();unpack(bundle,'run-manifest.json',run)
 if (bundle/'raw-manifest.json').exists():unpack(bundle,'raw-manifest.json',run)
 sys.path[:0]=[str(source),str(source/'tests/integration/perception'),str(source/'tests/integration/carla')]
 server=json.loads((run/'server.json').read_text());case=json.loads((bundle/'case.json').read_text())
 assert server['freeze_sha256']==case['freeze_sha256']==sha(bundle/'sources.json')
 if case['condition']=='stall-crash':
  prior=bundle/case['prior_normal_audit'];assert sha(prior)==case['prior_normal_audit_sha256']
  assert json.loads(prior.read_text())['status']=='PASS_DIAGNOSTIC_CASE_ONLY'
 exclusions=json.loads((bundle/'future-exclusion.json').read_text());prior=bundle/exclusions['prior']
 assert sha(prior)==exclusions['prior_sha256'] and exclusions['holdout_access'] is False
 expected=set(json.loads(prior.read_text())['rgb_sha256']);new=[]
 renderer=run/'capture/paired/renderer/result.json'
 if renderer.exists():new=[x['rgb_sha256'] for x in json.loads(renderer.read_text())['raw']]
 expected.update(new)
 assert sorted(expected)==exclusions['rgb_sha256'] and len(expected)==exclusions['count'] and len(new)==exclusions['new_raw_packets']
 rejected=[]
 if (bundle/'audit.json').exists() and json.loads((bundle/'audit.json').read_text())['status']=='PASS_DIAGNOSTIC_CASE_ONLY':
  audit=module('frozen_paired',source/'tests/integration/perception/audit_paired_v1.py').audit
  result=audit(run);assert result==json.loads((bundle/'audit.json').read_text())
  def reject(name,relative,edit):
   path=run/relative;old=path.read_bytes();data=json.loads(old);edit(data);path.write_text(json.dumps(data))
   try:
    try:audit(run)
    except (ValueError,KeyError,AssertionError):rejected.append(name)
    else:raise AssertionError('mutant accepted: '+name)
   finally:path.write_bytes(old)
  reject('renewed-scene-age','capture/paired/source.json',lambda d:d['exports'][0].update(acquired_begin_ns=d['exports'][0]['acquired_begin_ns']+1))
  reject('wrong-physical-frame','capture/paired/renderer/result.json',lambda d:d['mapped'][0].update(physical_frame=1))
  reject('camera-drift','capture/paired/renderer/result.json',lambda d:d['ticks'][0]['camera_world_matrix'][0].__setitem__(3,999))
  reject('diagnostic-authority','capture/paired/renderer/result.json',lambda d:d['inference'][0].update(accepted_for_control=True))
  reject('forced-server-exit','server.json',lambda d:d['shutdown']['renderer'].update(forced_stop=True))
  reject('undeclared-observation-rate','server.json',lambda d:d.update(export_hz=50))
  reject('reversed-query-bracket','capture/paired/source.json',lambda d:d['query_timings'][0].update(end_ns=0))
  reject('incorrect-walker-placement','capture/paired/catalog.json',lambda d:d['catalog']['actor_preparation']['walker_requested_matrix'][0].__setitem__(3,0))
  if case['condition']=='stall-crash':
   reject('death-observed-after-physical-end','server.json',lambda d:d.update(renderer_exit_observed_ns=2**63))
   reject('cleanup-without-actual-death','capture/paired/renderer/result.json',lambda d:d['dead_server_cleanup'].update(observed_exit_ns=0))
   reject('incomplete-dead-actor-cleanup','capture/paired/renderer/result.json',lambda d:d['dead_server_cleanup']['skipped_actor_ids'].pop())
   reject('stop-request-without-observation','capture/paired/source.json',lambda d:d['events'][0].pop('observed_stopped_ns'))
  verdict=result['status']
 else:
  assert server['status']=='FAIL' or json.loads((bundle/'audit.json').read_text())['status']=='FAIL'
  audit=module('frozen_paired',source/'tests/integration/perception/audit_paired_v1.py').audit
  try:audit(run)
  except ValueError as e:assert str(e)==json.loads((bundle/'audit.json').read_text())['error']
  else:raise AssertionError('original failed audit unexpectedly passed')
  verdict='ORIGINAL_FAILURE_REPRODUCED'
 result=dict(status='PASS',case_verdict=verdict,source_files=len(frozen['files']),raw_packets=len(new),future_exclusion=len(expected),rejected_mutations=rejected)
 (a.work/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);main(p.parse_args())
