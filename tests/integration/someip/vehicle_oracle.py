"""M6 physical evidence, in addition to unchanged ECU/session/timing oracles."""
import csv
import json
import math
from pathlib import Path

def vehicle_oracle(folder,case):
    out={'pass':False,'errors':[]}
    try:
        folder=Path(folder)
        with (folder/'physical.csv').open() as stream:rows=list(csv.DictReader(stream))
        if len(rows)<10:raise ValueError('missing vehicle samples')
        values=[[float(r[k]) for k in ('speed_mps','distance_m','x_m','y_m','yaw_rad','vehicle_balance_j')] for r in rows]
        if not all(math.isfinite(x) for v in values for x in v):raise ValueError('nonfinite vehicle state')
        if not all(v[0]>=0 for v in values):raise ValueError('reverse outside forward-only model')
        if not all(b[1]>=a[1] for a,b in zip(values,values[1:])):raise ValueError('physical distance reset/regressed')
        if len({r['model_epoch'] for r in rows})!=1:raise ValueError('ECU rejoin reset physical model epoch')
        if not all(int(b['model_sequence'])>int(a['model_sequence']) for a,b in zip(rows,rows[1:])):raise ValueError('physical sequence reset/regressed')
        if max(v[0] for v in values)<=.01 or values[-1][1]<=.001:raise ValueError('no actual vehicle motion')
        if max(abs(v[5]) for v in values)>1e-5:raise ValueError('vehicle work/kinetic energy residual')
        c=json.loads((folder/'central-1.json').read_text())
        if c.get('max_validated_wheel_speed',0)<=.01 or c.get('wheel_speed_samples',0)<10:raise ValueError('no validated remote wheel-speed feedback')
        if case in ('normal','restart-live'):
            path=folder/'central-1.json'
            c=json.loads(path.read_text())
            final=[v for r,v in zip(rows,values) if int(r['ns'])>=c['normal_stop_complete']]
            if not final or max(v[0] for v in final)>.15:raise ValueError('normal stop without actual low speed')
        out.update(pass_=True,max_speed_mps=max(v[0] for v in values),distance_m=values[-1][1],final_speed_mps=values[-1][0],max_balance_error_j=max(abs(v[5]) for v in values),samples=len(rows))
        out['pass']=out.pop('pass_')
    except (OSError,ValueError,KeyError,TypeError) as e:out['errors'].append(str(e))
    return out
