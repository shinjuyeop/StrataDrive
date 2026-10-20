import json,subprocess,shutil,hashlib
from pathlib import Path
r=Path.cwd();o=r/'build/m4-dds-full-tsan';o.mkdir(exist_ok=False)
src=r/'build/m4-communication-research/deps/cyclonedds-src/eclipse-cyclonedds-cyclonedds-e54e991';prefix=o/'install'
commands=[['cmake','-S',str(src),'-B',str(o/'sdk-build'),'-DCMAKE_BUILD_TYPE=Debug','-DCMAKE_INSTALL_PREFIX='+str(prefix),'-DBUILD_TESTING=OFF','-DBUILD_EXAMPLES=OFF','-DBUILD_DDSPERF=OFF','-DENABLE_SECURITY=OFF','-DENABLE_ICEORYX=OFF','-DBUILD_IDLC=OFF','-DCMAKE_C_FLAGS=-fsanitize=thread -fno-omit-frame-pointer','-DCMAKE_SHARED_LINKER_FLAGS=-fsanitize=thread','-DCMAKE_INTERPROCEDURAL_OPTIMIZATION=OFF'],['cmake','--build',str(o/'sdk-build'),'-j4'],['cmake','--install',str(o/'sdk-build')]]
for i,c in enumerate(commands):
 with (o/f'sdk-{i}.log').open('w') as log:subprocess.run(c,stdout=log,stderr=subprocess.STDOUT,check=True)
# Reuse the already instrumented probe executable, select the fully instrumented
# libddsc explicitly in its private loader environment; no system library changes.
results=[]
for case in ('normal','overflow'):
 folder=o/case;folder.mkdir()
 command=['unshare','-Urnm','setarch','x86_64','-R','env','LD_LIBRARY_PATH='+str(prefix/'lib'),'python3',str(r/'tests/integration/middleware/run_probe.py'),'--child',str(folder),str(r/'build/m4-probe-tsan/tests/integration/middleware/dds_candidate_probe'),case]
 commands.append(command)
 with (folder/'runner.log').open('w') as log:code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT).returncode
 result=json.load(open(folder/'result.json')) if (folder/'result.json').exists() else {'verdict':'FAIL','runner_exit':code}
 warnings=[role for role in ('central','zone') if (folder/(role+'.stderr')).exists() and 'WARNING: ThreadSanitizer' in (folder/(role+'.stderr')).read_text()]
 if warnings:result['verdict']='FAIL'
 row={'case':case,'warnings':warnings,**result};results.append(row);print(json.dumps(row),flush=True)
(o/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
(o/'results.json').write_text(json.dumps(results,indent=2)+'\n')
(o/'metadata.json').write_text(json.dumps({'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'dependency':'CycloneDDS11.0.1 fully C TSan-instrumented Debug, no LTO','library_sha256':hashlib.sha256((prefix/'lib/libddsc.so.11.0.1').read_bytes()).hexdigest(),'source_sha256':'472a0aade963891961ee8fd52ed02d138c6eedf288856e020090f8eb662948a5'},indent=2)+'\n')
