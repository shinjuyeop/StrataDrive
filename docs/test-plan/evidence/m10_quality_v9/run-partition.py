from pathlib import Path
import sys
import json
sys.path[:0] = ['.', 'tests/integration/perception']
from run_quality_v9 import run
from quality_benchmark_v9 import score, nominate
from quality_benchmark import write_new
from physical_ai.perception.quality_candidates_v9 import CANDIDATES

root = Path(__file__).parent
phase = sys.argv[1]
frozen = root / 'experiment-freeze.json'
data = root / f'{phase}-data'
selection = root / 'candidate-selection.json' if phase == 'holdout' else None
candidates = CANDIDATES if phase == 'development' else ('baseline', json.loads(selection.read_text())['selected'])
for candidate in candidates:
    model = Path('build/m10-perception/yolox.onnx' if candidate == 'baseline' else 'build/m10-model-screen-v2/upstream/dfine-m.onnx')
    output = root / f'{phase}-{candidate}'
    result = run(data / 'rgb.json', model, output, candidate, phase, frozen, selection)
    print(json.dumps({k: result[k] for k in ('status', 'candidate', 'model_valid', 'admitted', 'errors', 'latency')}), flush=True)
    assert result['status'] == 'PASS', result.get('error')
    result = score(data, output / 'result.json', frozen)
    write_new(root / f'{phase}-{candidate}-score.json', result)
    print(json.dumps({k: result[k] for k in ('candidate', 'micro', 'absolute_quality', 'gates')}), flush=True)
if phase == 'development':
    result = nominate([root / f'development-{c}-score.json' for c in CANDIDATES], frozen, root / 'candidate-selection.json')
    print(json.dumps(result), flush=True)
