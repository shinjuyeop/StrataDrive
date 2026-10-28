import gzip,json,hashlib
from pathlib import Path
from itertools import zip_longest
root=Path('/d/shin/StrataDrive/docs/test-plan/evidence')
run=Path('/d/shin/stratadrive-tools/m7-source/m7-batch-close/suite-v2')
def rows(path):
    with (gzip.open(path,'rt') if path.suffix=='.gz' else path.open()) as file:
        for line in file:
            r=json.loads(line)
            if 'receipt' in r:yield r['receipt']
def compare(old,new,normal):
    count=0;first=None;equal_work=0;equal_effort=0;motor_work_equal=0
    for i,(a,b) in enumerate(zip_longest(rows(old),rows(new))):
        assert a is not None and b is not None
        p=dict(a['physics']);q=dict(b['physics']);p.pop('generation');q.pop('generation')
        if p!=q and first is None:first=i
        equal_work+=a['solver_work']['steps']==b['solver_work']['steps']
        motor_work_equal+=a['solver_work']['motor_work_j']==b['solver_work']['motor_work_j']
        equal_effort+=all(a['original_actual']['admitted_actual'][k]==b['original_actual']['admitted_actual'][k] for k in ('angle_rad','torque_nm','pressure_pa'))
        count+=1
    assert count==(900 if normal else 400)
    assert equal_effort==motor_work_equal==count
    if normal:assert first is None and equal_work==count
    else:assert first==279 and equal_work==279
    return dict(old=str(old),new=str(new),intervals=count,first_physics_difference=first,
                exact_solver_steps_equal_intervals=equal_work,exact_motor_work_equal_intervals=motor_work_equal,
                exact_original_actual_values_equal_intervals=equal_effort,excluded_physics_field='generation',
                timestamps_rewritten=False,full_EV_float_equality_claimed=False)
result={'normal':compare(root/'m7_carla_integrated/driving-b/trace.jsonl.gz',run/'camera-a/trace.jsonl',True),
        'protection':compare(root/'m7_carla_recovery/causal-followup/protection/trace.jsonl.gz',run/'protected-sleep/trace.jsonl',False)}
print(json.dumps(result,indent=2))
