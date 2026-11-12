"""Lossless retained receipt/service-time conversion, not clock extrapolation."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct
import subprocess


def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--scenario',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--require-exact',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    run=json.loads((a.capture/'result.json').read_text());meta=json.loads((a.capture/'native.json').read_text())
    receipts=[json.loads(line) for line in (a.capture/'trace.jsonl').read_text().splitlines()]
    jobs=list(csv.DictReader((a.capture/'native.csv').open()))
    f32=lambda v:struct.unpack('<f',struct.pack('<f',v))[0]
    dt=f32(f32(.01)*f32(1/320))
    by_end={int(row['receipt']['work_end_ns']):row for row in receipts};used=set()
    lines=[f"{meta['initial']} {run['binding']['logical_begin_ns']} {run['binding']['actor']}"]
    for job in jobs:
        end=int(job['energy_end']);row=by_end.get(end) if end not in used else None
        tokens=[job['now'],str(int(row is not None))]
        if row:
            used.add(end);r=row['receipt'];admitted=r['original_actual']['admitted_actual'];work=r['solver_work']
            assert int(job['wheel_source'])==int(r['physics_acquisition_begin_ns'])
            assert work['valid'] and not r['wall_authority_expired_during_physics']
            wheels=row['physics']['wheels'];begin=(wheels[2]['solver_omega_rad_s']+wheels[3]['solver_omega_rad_s'])/2
            tokens += [r['frame'],r['logical_begin_ns'],r['work_end_ns'],r['wall_applied_ns'],r['physics_acquisition_begin_ns'],r['physics_acquisition_end_ns'],
                       admitted['oldest_actuator_ns'] if int(admitted['oldest_actuator_ns']) else r['wall_applied_ns'],r['coil_source_ns'],r['coil_bits'],
                       str(work['sleeping']),repr(admitted['torque_nm']),repr(dt),repr(begin)]
            tokens += [repr(w['solver_omega_rad_s']) for w in r['physics']['wheels']]
            tokens += [repr(v) for v in work['rear_mean_rad_s']] if not work['sleeping'] else ['0']*320
        lines.append(' '.join(tokens))
    assert used==set(by_end)
    source=a.output/'input.txt';source.write_text('\n'.join(lines)+'\n')
    subprocess.run([str(a.binary.resolve()),str(source.resolve()),str(a.scenario.resolve()),str((a.output/'replay').resolve())],check=True)
    output=list(csv.DictReader((a.output/'replay.csv').open()));assert len(output)==len(jobs)
    differences=[dict(index=i,original=x,replay=y) for i,(x,y) in enumerate(zip(jobs,output)) if x!=y]
    source_fields=('now','energy_end','wheel_source','hv_source','hv_dependency')
    original_sources=all(all(x[k]==y[k] for k in source_fields) for x,y in zip(jobs,output))
    assert original_sources, 'replay must retain original service/energy/sensor times'
    report=dict(scope='original wall timestamp/solver replay; not new live execution',calls=len(jobs),receipts=len(receipts),exact=not differences,
                original_source_fields_equal=original_sources,
                input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),first_difference=differences[:1],different_rows=len(differences))
    (a.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if a.require_exact:assert not differences


if __name__=='__main__':main()
