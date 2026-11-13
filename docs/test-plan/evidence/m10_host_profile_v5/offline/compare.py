"""Recompute retained CUDA-wait comparisons without GPU inference or new images."""
import json
from pathlib import Path
import sys
import numpy as np

root=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(root))
from physical_ai.perception.camera_resolution_v1 import decode

here=Path(__file__).resolve().parent
reference=json.loads((here/'offline-reference-02/result.json').read_text())
candidate=json.loads((here/'offline-cuda-blocking/result.json').read_text())
assert reference['raw_hashes']==candidate['raw_hashes']
assert reference['tensor_sha256']==candidate['tensor_sha256']
rows=[]
with np.load(here/'offline-reference-02/model-outputs.npz') as a, np.load(here/'offline-cuda-blocking/model-outputs.npz') as b:
    for index in range(len(reference['raw_hashes'])):
        left={k:a[f'{index}-{k}'] for k in ('labels','boxes','scores')}
        right={k:b[f'{index}-{k}'] for k in left}
        original,changed=decode(left,4),decode(right,4)
        assert [d.class_id for d in original]==[d.class_id for d in changed]
        rows.append(dict(frame=index,detections=len(original),
            raw_bit_exact=all(np.array_equal(left[k],right[k]) for k in left),
            max_score_delta=max((abs(x.score-y.score) for x,y in zip(original,changed)),default=0),
            max_box_delta=max((abs(v-w) for x,y in zip(original,changed) for v,w in zip(x.box,y.box)),default=0)))
result=dict(status='PASS_EXCLUDED_INPUT_DIAGNOSTIC',rows=rows,holdout=False,new_images=0,cuda_policy=candidate['cuda_wait_policy'])
assert result==json.loads((here/'comparison.json').read_text()),'retained numerical comparison changed'
print(json.dumps(dict(status='PASS',frames=len(rows),retained_comparison_exact=True)))
