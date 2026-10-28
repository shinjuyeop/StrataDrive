import json,gzip,math,hashlib
from pathlib import Path
from itertools import zip_longest
base=Path('/d/shin/stratadrive-tools/m7-source/m7-wall-pipeline')
reference=Path('/d/shin/StrataDrive/docs/test-plan/evidence/m7_carla_recovery/batch-closeout/suite-v2/camera-a/trace.jsonl.gz')
protected=Path('/d/shin/StrataDrive/docs/test-plan/evidence/m7_carla_recovery/batch-closeout/suite-v3/protected-sleep/trace.jsonl.gz')
def rows(path):
    with (gzip.open(path,'rt') if path.suffix=='.gz' else path.open()) as f:
        for line in f:
            r=json.loads(line)
            if 'receipt' in r:yield r

def compare(old,new,count):
    found=0
    for a,b in zip_longest(rows(old),rows(new)):
        assert a is not None and b is not None
        ar=a['receipt'];br=b['receipt'];p=dict(ar['physics']);q=dict(br['physics']);p.pop('generation');q.pop('generation')
        assert p==q,(found,'physics')
        assert ar['solver_work']['steps']==br['solver_work']['steps'],(found,'solver steps')
        assert ar['solver_work']['motor_work_j']==br['solver_work']['motor_work_j'],(found,'work')
        assert all(ar['original_actual']['admitted_actual'][k]==br['original_actual']['admitted_actual'][k] for k in ('angle_rad','torque_nm','pressure_pa'))
        found+=1
    assert found==count
    return {'reference':str(old),'new':str(new),'exact_physics_except_generation':count,'exact_solver_steps':count,'exact_motor_work':count,'exact_actual_values':count}

def timing(path):
    data=list(rows(path));delays=[];periods=[]
    for a,b in zip(data,data[1:]):
        if a['index']==150:continue
        ra=a['receipt'];rb=b['receipt']
        delays.append(b['wall_native_end_ns']-int(ra['physics_acquisition_begin_ns']))
        periods.append(int(rb['physics_acquisition_begin_ns'])-int(ra['physics_acquisition_begin_ns']))
    def stats(values):
        v=sorted(values)
        return dict(count=len(v),mean_ms=sum(v)/len(v)/1e6,median_ms=v[len(v)//2]/1e6,p95_ms=v[math.ceil(.95*len(v))-1]/1e6,max_ms=v[-1]/1e6,over_30ms=sum(x>30000000 for x in v))
    return dict(excluded_intentional_pause_after_index=150,excludes_terminal_no_receipt_row=True,acquisition_to_next_native_end=stats(delays),postphysics_period=stats(periods),diagnostic_model_to_wall_rate=len(periods)*10000000/sum(periods),hard_real_time_accepted=False)
paths=['compact/normal-a','compact/camera-a','legacy-final/camera-a','compact-final/camera-a']
result={'comparisons':[compare(reference,base/p/'trace.jsonl',900) for p in paths],
        'protected_comparison':compare(protected,base/'compact/protected-sleep/trace.jsonl',400),
        'timing':{p:timing(base/p/'trace.jsonl') for p in paths}}
print(json.dumps(result,indent=2))
