from pathlib import Path
import json,subprocess,sys
root=Path('/d/shin/StrataDrive');work=Path('/d/shin/stratadrive-tools/m7-source/m7-hv50-v1')
base=[sys.executable,str(root/'tests/integration/carla/m7_1o_run.py'),'--engine','/d/shin/stratadrive-tools/UnrealEngine_4.26','--source','/d/shin/stratadrive-tools/m7-source/carla-0.9.16','--python','/d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python','--fixture','/d/shin/stratadrive-tools/m7-source/m7-1m-fixture','--vehicle-substeps','320','--native-actual',str(root/'build/m7-functional/tests/integration/carla/m7_1g/m7_carla_wall_owner'),'--solver-work','--compact-work','--wall-native','--wall-step-ms','5','--wall-hv-dependency-ms','50','--held-steer-sleep','--scenario',str(root/'tests/integration/carla/scenarios/m7_integrated_v1.txt'),'--ticks','900','--wall-inline-render','--wall-nullrhi']
summary=[]
for i,fault in [(1,'none'),(2,'none'),(3,'wall-gap'),(4,'protection')]:
 name=f'run{i:02}';argv=base+['--runtime',str(work/f'runtime{i:02}'),'--output',str(work/name),'--native-fault',fault]
 (work/(name+'-args.json')).write_text(json.dumps(argv,indent=2)+'\n')
 with (work/(name+'-runner.log')).open('w') as log:r=subprocess.run(argv,cwd=root,stdout=log,stderr=subprocess.STDOUT)
 audit=subprocess.run([sys.executable,str(root/'tests/integration/carla/audit_m7_wall_carla.py'),str(work/name),'--output',str(work/name/'audit.json')],cwd=root,capture_output=True,text=True)
 (work/(name+'-audit.log')).write_text(audit.stdout+audit.stderr)
 s=dict(case=name,fault=fault,run_exit=r.returncode,audit_exit=audit.returncode)
 if (work/name/'audit.json').exists():s['audit']=json.loads((work/name/'audit.json').read_text())
 summary.append(s);(work/'optimized-batch.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(s),flush=True)

