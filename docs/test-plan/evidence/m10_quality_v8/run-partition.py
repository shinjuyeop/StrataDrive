from pathlib import Path
import sys,json,subprocess
sys.path[:0]=['.','tests/integration/perception']
from run_quality_v8 import run
from quality_benchmark_v8 import score,nominate
from quality_benchmark import write_new
from physical_ai.perception.quality_candidates_v8 import CANDIDATES
root=Path(__file__).parent;phase=sys.argv[1];frozen=root/'experiment-freeze.json';data=root/f'{phase}-data'
selection_path=root/'candidate-selection.json' if phase=='holdout' else None
candidates=CANDIDATES if phase=='development' else ('baseline',json.loads(selection_path.read_text())['selected'])
for candidate in candidates:
 model=Path('build/m10-perception/yolox.onnx') if candidate=='baseline' else Path('build/m10-quality-v6-design/upstream/yolox_l.onnx')
 output=root/f'{phase}-{candidate}'
 r=run(data/'rgb.json',model,output,candidate,phase,frozen,selection_path)
 print(json.dumps({k:r[k] for k in ('status','candidate','model_valid','admitted','errors','latency')}),flush=True);assert r['status']=='PASS',r.get('error')
 r=score(data,output/'result.json',frozen);write_new(root/f'{phase}-{candidate}-score.json',r)
 print(json.dumps({k:r[k] for k in ('candidate','micro','absolute_quality','gates')}),flush=True)
if phase=='development':
 result=nominate([root/f'development-{c}-score.json' for c in CANDIDATES],frozen,root/'candidate-selection.json');print(json.dumps(result),flush=True)
