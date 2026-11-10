from pathlib import Path
import subprocess,json
root=Path(__file__).parent;results={}
for config in ('debug','release','asan'):
 with (root/f'ctest-{config}.log').open('w') as log:
  r=subprocess.run(['ctest','--test-dir',f'build/m10-perception/{config}','-R','Perception|perception','--output-on-failure'],stdout=log,stderr=subprocess.STDOUT)
 results[config]=r.returncode
 assert r.returncode==0,config
print(json.dumps(results))
