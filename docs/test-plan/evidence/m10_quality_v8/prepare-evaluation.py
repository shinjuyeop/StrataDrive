from pathlib import Path
import sys,time,json
sys.path[:0]=['.','tests/integration/perception']
from prepare_quality_v8 import prepare
from review_quality_v8 import review
root=Path(__file__).parent;part=sys.argv[1]
server=root/json.loads((root/'evaluation-runs.json').read_text())[part]/'server.json';end=time.monotonic()+700
while not server.exists() and time.monotonic()<end:time.sleep(.5)
assert json.loads(server.read_text())['status']=='PASS','Failed server not accepted or inferred'
r=prepare(server.parent/'dataset/capture.json',root/f'{part}-data',root/'experiment-freeze.json')
print(json.dumps(r),flush=True)
assert r['status']=='PASS','Failed actual visibility: no quality inference'
print(json.dumps(review(root/f'{part}-data',root,part)),flush=True)
