import json,subprocess,os
from pathlib import Path
root=Path.cwd();out=root/'build/m4-probe-sanitizers';out.mkdir(exist_ok=False)
common=['-DBUILD_TESTING=OFF','-DSTRATADRIVE_MIDDLEWARE_PROBES=ON','-DCMAKE_PREFIX_PATH='+str(root/'build/m4-communication-research/install'),'-DSTRATADRIVE_ZENOH_INCLUDE='+str(root/'build/m4-communication-research/deps/zenoh-c/include'),'-DSTRATADRIVE_ZENOH_LIBRARY='+str(root/'build/m4-communication-research/deps/zenoh-c/lib/libzenohc.so')]
results=[];commands=[]
for profile,san,option in [('asan','address,undefined','STRATADRIVE_SANITIZERS'),('tsan','thread','STRATADRIVE_TSAN')]:
 build=root/('build/m4-probe-'+profile)
 steps=[['cmake','-S','.', '-B',str(build),'-DCMAKE_BUILD_TYPE=Debug','-D'+option+'=ON','-DCMAKE_C_FLAGS=-fsanitize='+san+' -fno-omit-frame-pointer','-DCMAKE_CXX_FLAGS=-fsanitize='+san+' -fno-omit-frame-pointer','-DCMAKE_EXE_LINKER_FLAGS=-fsanitize='+san,*common],['cmake','--build',str(build),'--target','dds_candidate_probe','zenoh_candidate_probe','-j4']]
 ready=True
 for i,cmd in enumerate(steps):
  commands.append(cmd)
  with (out/f'{profile}-build-{i}.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
  if r.returncode:ready=False;break
 for candidate in ('dds','zenoh'):
  for condition in ('normal','overflow'):
   folder=out/f'{profile}-{candidate}-{condition}';folder.mkdir()
   cmd=['unshare','-Urnm',*(['setarch','x86_64','-R'] if profile=='tsan' else []),'python3',str(root/'tests/integration/middleware/run_probe.py'),'--child',str(folder),str(build/'tests/integration/middleware'/(candidate+'_candidate_probe')),condition]
   commands.append(cmd)
   with (folder/'runner.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT) if ready else None
   data=json.load(open(folder/'result.json')) if (folder/'result.json').exists() else {'verdict':'BLOCKED' if not ready else 'FAIL'}
   warnings=[]
   for role in ('central','zone'):
    f=folder/(role+'.stderr')
    if f.exists():
     t=f.read_text()
     if any(x in t for x in ['WARNING: ThreadSanitizer','ERROR: AddressSanitizer','runtime error:','LeakSanitizer']):warnings.append(role)
     if 'FATAL: ThreadSanitizer: unexpected memory mapping' in t:data['verdict']='BLOCKED'
   if warnings:data['verdict']='FAIL'
   row={'profile':profile,'candidate':candidate,'condition':condition,'warnings':warnings,**data};results.append(row);print(json.dumps(row),flush=True)
(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
(out/'metadata.json').write_text(json.dumps({'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'scope':'instrumented application/C wrapper; Cyclone/Zenoh DSOs remain upstream Release and uninstrumented','tsan_aslr':'process-local setarch -R'},indent=2)+'\n')
