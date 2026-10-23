#!/usr/bin/env python3
"""Independent CSV checks for the synthetic-Actual standalone SDK experiment.

This does not certify CARLA, native ECU provenance, calibration, or work/energy.
The coarse solver's negative wheel observations must remain a failed criterion.
"""
import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path


def audit(rows):
    errors = set()

    def require(condition, label):
        if not condition:
            errors.add(label)

    require(len(rows) == 850, '850 intervals')
    negative = []
    minimum = math.inf
    for frame, row in enumerate(rows, 1):
        require(all(math.isfinite(float(value)) for value in row.values()), 'finite values')
        begin = 1_000_000_000 + frame * 10_000_000
        require(int(row['frame']) == frame, 'sequence')
        require(int(row['begin_ns']) == begin and int(row['end_ns']) == begin + 10_000_000,
                '10ms interval')
        # Synthetic fixture acquisition, NOT a claim about native runtime source ages.
        require(int(row['source_ns']) == begin and int(row['oldest_ns']) == begin,
                'original fixture source/oldest')
        torque = 0 if frame <= 100 or frame > 650 else (300 if frame <= 500 else -150)
        pressure = 100000 if frame <= 100 or frame > 650 else 0
        require(float(row['torque_nm']) == torque and float(row['pressure_pa']) == pressure,
                'fixture phases')
        require(float(row['motor_rl_nm']) == torque / 2 and float(row['motor_rr_nm']) == torque / 2,
                'signed rear allocation')
        require(all(float(row['friction_'+wheel+'_nm']) == (1000 if pressure else 0)
                    for wheel in ('fl', 'fr', 'rl', 'rr')), 'synthetic brake vector')
        rear = [float(row['omega_'+wheel]) for wheel in ('rl', 'rr')]
        minimum = min(minimum, *rear)
        if min(rear) < 0:
            negative.append(frame)
        if frame <= 100 or frame >= 750:
            require(rear == [0, 0], 'exact rear zero in hold/settled stop')
        require(row['work_valid'] == '0', 'work remains unavailable')
        require(all(row[key] in ('0', '1') for key in
                    ('sleeping', 'air_fl', 'air_fr', 'air_rl', 'air_rr')), 'state flags')
        require(1 <= int(row['low_substeps']) <= 100 and 1 <= int(row['high_substeps']) <= 100,
                'explicit solver subdivision')
    require(not negative, 'no negative rear samples')
    if len(rows) == 850:
        v_accel, v_regen, v_stop = [float(rows[i-1]['forward_m_s']) for i in (500, 650, 850)]
        require(v_accel > 1 and 0 < v_regen < v_accel, 'forward acceleration/negative torque deceleration')
        require(abs(v_stop) < .01, 'body stop')
    else:
        v_accel = v_regen = v_stop = None
    return dict(result='FAIL' if errors else 'PASS', errors=sorted(errors), intervals=len(rows),
                negative_rear_samples=len(negative), first_negative_frame=negative[0] if negative else None,
                minimum_rear_rad_s=minimum, acceleration_end_m_s=v_accel,
                negative_torque_end_m_s=v_regen, stop_m_s=v_stop,
                final_z_m=float(rows[-1]['z_m']) if rows else None,
                subdivisions=sorted({(int(r['low_substeps']), int(r['high_substeps'])) for r in rows}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    results, raw = {}, {}
    names = ['solver-3', 'solver-10', 'solver-20', 'solver-40',
             'physics-normal-verified', 'physics-asan-verified']
    for name in names:
        path = args.evidence/(name+'.csv')
        with path.open() as stream:
            raw[name] = list(csv.DictReader(stream))
        results[name] = audit(raw[name])
        results[name]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = (results['solver-3']['errors'] == ['no negative rear samples'] and
                all(results[name]['result'] == 'PASS' for name in names[1:]))
    # Corrupt evidence copies, never the saved originals; ensure the oracle rejects.
    mutations = {
        'future-source': (101, 'source_ns', '9999999999'),
        'new-oldest': (101, 'oldest_ns', '0'),
        'wrong-tick': (101, 'end_ns', '9999999999'),
        'wrong-wheel-torque': (101, 'motor_rr_nm', '151'),
        'wrong-friction': (1, 'friction_fl_nm', '0'),
        'negative-wheel': (101, 'omega_rl', '-0.000001'),
        'nonfinite-wheel': (101, 'omega_rl', 'nan'),
        'claimed-work': (101, 'work_valid', '1'),
    }
    rejected = {}
    for name, (frame, field, value) in mutations.items():
        rows = copy.deepcopy(raw['physics-normal-verified'])
        rows[frame-1][field] = value
        rejected[name] = audit(rows)['errors']
    ok = expected and all(rejected.values())
    report = dict(scope='standalone public SDK / synthetic Actual fixtures only',
                  traces=results, expected_results_matched=expected, mutations=rejected,
                  mutation_rejections=f'{sum(bool(v) for v in rejected.values())}/{len(rejected)}',
                  coarse_result_remains='FAIL', carla_server='NOT RUN', interval_work='unavailable',
                  probe_consistency='PASS' if ok else 'FAIL')
    print(json.dumps(report, indent=2, allow_nan=False))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
