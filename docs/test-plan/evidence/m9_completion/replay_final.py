import sys,json,subprocess,hashlib,pathlib
sys.path.insert(0,'tests/integration/carla')
from evidence_io import json_rows
root=pathlib.Path('build/m9-completion');binary=pathlib.Path('build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow').resolve();results=[]
for name,fault in [('nominal-01','none'),('input-loss-01','input-loss'),('stop-ack-loss-01','stop-ack-loss'),('front-link-failure-01','front-link-failure'),('braking-timeout-02','braking-timeout')]:
 d=root/'carla'/name;r=json.load(open(d/'result.json'))
 cmd=[str(binary),'--native-solver-work','1','42','7',str(r['binding']['actor']),'--sim-horizon-ms','60000','--route',str((d/'route.txt').resolve()),'--diagnostic-fault',fault]
 count=0;verdict='PASS_EXACT_NATIVE_REPLAY';error=None;digest=hashlib.sha256()
 with (root/'logs'/('replay-'+name+'.stderr')).open('w') as err:
  p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True)
  try:
   for row in json_rows(d/'trace.jsonl'):
    for field in ['work_input','pose_input','native_input']:
     if row.get(field):p.stdin.write(row[field]+'\n')
    p.stdin.flush();line=p.stdout.readline();actual=json.loads(line);digest.update(line.encode())
    assert actual==row['native'],('original native mismatch',row['index'])
    count+=1
   p.stdin.close();assert p.wait(timeout=10)==0
  except Exception as e:
   verdict='FAIL';error=repr(e);p.kill();p.wait()
 result=dict(name=name,status=verdict,observations=count,argv=cmd,original_physics_only=True,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),replayed_native_sha256=digest.hexdigest(),error=error)
 results.append(result);print(name,verdict,count,error,flush=True)
 (root/'replay-results.json').write_text(json.dumps(results,indent=2)+'\n')
