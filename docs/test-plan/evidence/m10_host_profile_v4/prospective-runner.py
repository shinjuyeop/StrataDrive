import gzip,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
root=Path.cwd();py=root/'build/m10-perception/cuda-venv/bin/python';scripts=root/'tests/integration/perception'
series=root/'docs/test-plan/evidence/m10_host_profile_v4';work=root/'build/m10-profile-v1';freeze=series/'sources.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plans={'f-readback20':['--park-preparation','--renderer-max-fps','60','--preprocess-cv-threads','4','--resize-threads','4','--cuda-blocking','--raw-recording','--camera-period-ms','100']}
name=sys.argv[1];extra=plans[name];index=0
prior=root/'docs/test-plan/evidence/m10_host_profile_v3/e-raw-rr/future-exclusion.json'
base=json.loads((root/'docs/test-plan/evidence/m10_endurance_v8/normal-30s-01/case.json').read_text())
run=Path('/tmp/stratadrive-m10-profile-v1')/name;bundle=series/name;bundle.mkdir();casework=work/name;casework.mkdir()
argv=base['argv'][:]
for flag,value in [('--freeze',freeze),('--output',run),('--endurance-build',root/'build/m10-remediation/server-build-01/manifest.json'),('--resource-profile',root/'profiles/perception-endurance-host-v1.json')]:argv[argv.index(flag)+1]=str(value)
argv[argv.index('--renderer-wall-hz')+1]='20'
argv+=['--profile-host',*extra]
case=dict(base,declared_utc=datetime.now(timezone.utc).isoformat(),attempt=1,run=str(run),freeze_sha256=sha(freeze),protocol='docs/test-plan/perception-host-profile-v4-protocol.md',comparison_case=name,argv=argv)
(bundle/'case.json').write_text(json.dumps(case,indent=2)+'\n')
sys.path.insert(0,str(scripts))
from profile_host_v1 import host
preflight=[];until=time.monotonic()+180
while True:
 h=host();temperature=max(v/1000 for k,v in h.items() if '/temp' in k)
 preflight.append(dict(wall_ns=time.monotonic_ns(),max_cpu_c=temperature))
 if temperature<=70 or time.monotonic()>until:break
 time.sleep(2)
(casework/'preflight.json').write_text(json.dumps(dict(scope='idle temperature observation before starting owned servers; no host settings changed',samples=preflight),indent=2)+'\n')
print('START',name,flush=True)
with (casework/'runner.log').open('w') as log:
 runner=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 with (casework/'monitor.log').open('w') as out:
  monitor=subprocess.Popen(['taskset','-c','0,8',str(py),str(scripts/'profile_host_v1.py'),'--pid',str(runner.pid),'--seconds','1100','--output',str(casework/'profile.jsonl')],stdout=out,stderr=subprocess.STDOUT)
  code=runner.wait();monitorcode=monitor.wait(timeout=10)
print('SERVER EXIT',code,'MONITOR',monitorcode,flush=True)
assert monitorcode==0
with (casework/'profile.jsonl').open('rb') as source,gzip.open(run/'host-profile.jsonl.gz','wb') as out:shutil.copyfileobj(source,out)
shutil.copy2(casework/'profile.summary.json',run/'host-profile-summary.json')
def call(script,args,log):
 with (bundle/log).open('w') as out:return subprocess.run([str(py),str(scripts/script),*map(str,args)],stdout=out,stderr=subprocess.STDOUT).returncode
audit=call('audit_paired_v1.py',[run,'--output',bundle/'audit.json'],'audit.log')
shadow=call('audit_control_shadow_v1.py',[run,'--output',bundle/'shadow-integrity.json'],'shadow-integrity.log')
replay=casework/'replay'
replay_code=call('replay_wall_startup_v1.py',['--capture',run/'capture','--binary',root/'build/m10-endurance-v3/native/tests/integration/carla/m7_1g/m7_wall_startup_replay','--scenario',root/'tests/integration/carla/scenarios/m10_endurance_hold_v1.txt','--output',replay,'--require-exact'],'replay.log')
if (replay/'validation.json').exists():shutil.copy2(replay/'validation.json',bundle/'replay.json')
print('AUDIT',(bundle/'audit.json').read_text()[:300],'REPLAY',replay_code,flush=True)
assert call('seal_endurance_v1.py',['--run',run,'--bundle',bundle,'--prior',prior],'seal.log')==0
assert call('check_endurance_archive_v1.py',['--series',series,'--bundle',bundle,'--work',casework/'archive-check'],'archive-check.log')==0
shutil.copy2(casework/'archive-check/validation.json',bundle/'archive-validation.json')
assert run.parent==Path('/tmp/stratadrive-m10-profile-v1');shutil.rmtree(run)
(bundle/'disposition.json').write_text(json.dumps(dict(runner=code,physical_audit=audit,shadow_audit=shadow,replay=replay_code,archive='PASS',normal_endurance_accepted=False),indent=2)+'\n')
print('SEALED',name,flush=True)
