#!/usr/bin/env python3
"""Read-only installed-binding audit and reanalysis of immutable 1g/1h traces.

No Client, server, tick, ego, or actuation is created. Historical observations
are not new CARLA runtime results or a calibrated numerical-error bound.
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys

import carla


def public_names(cls):
    return sorted(x for x in dir(cls) if not x.startswith('_'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if not rows:
        raise ValueError('empty trace')
    prior = None
    rear, negative, exact_zero, tiny_body_motion = [], [], 0, 0
    for row in rows:
        omega = [w['omega'] for w in row['wheel']]
        if len(omega) != 4 or not all(math.isfinite(x) for x in omega):
            raise ValueError('invalid wheel observation')
        if row['frame'] != row['bracket_after_frame'] or not row['repeated_omega_equal']:
            raise ValueError('unbracketed observation')
        if prior and (row['frame'] != prior['frame']+1 or row['sim_s'] <= prior['sim_s']):
            raise ValueError('nonconsecutive trace')
        mean = (omega[2]+omega[3])/2
        rear.append(mean)
        if omega[2] == 0 and omega[3] == 0:
            exact_zero += 1
        if omega[2] < 0 or omega[3] < 0:
            negative.append(dict(index=row['index'], frame=row['frame'],
                                 sim_s=row['sim_s'], rear_omega=omega[2:],
                                 forward_m_s=row['forward_m_s'], velocity=row['velocity']))
            if any(v != 0 for v in row['velocity']):
                tiny_body_motion += 1
        prior = row
    return dict(path=str(path), sha256=digest(path), historical_samples=len(rows),
                negative_rear_samples=len(negative), exact_rear_zero_samples=exact_zero,
                minimum_rear_mean_rad_s=min(rear), maximum_abs_rear_mean_rad_s=max(map(abs, rear)),
                first_negative=negative[0] if negative else None,
                negative_samples_with_nonzero_body_velocity=tiny_body_motion,
                # A finite observed maximum is not a valid noise tolerance.
                calibrated_error_bound=None, negative_to_zero_authorized=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.repo.resolve()
    evidence = root/'docs/test-plan/evidence'
    vehicle = public_names(carla.Vehicle)
    telemetry = public_names(carla.VehicleTelemetryData)
    wheel = public_names(carla.WheelTelemetryData)
    result = dict(
        kind='READ_ONLY_BINDING_AND_HISTORICAL_TRACE_AUDIT',
        python=sys.version, carla_distribution=importlib.metadata.version('carla'),
        carla_module=str(Path(carla.__file__).resolve()),
        new_server_runs=0, apply_calls=0, live_driving_acceptance='NOT_RUN',
        vehicle_methods=vehicle, vehicle_telemetry_fields=telemetry, wheel_telemetry_fields=wheel,
        candidate_native_methods={name: name in vehicle for name in
                                  ['set_drive_torque', 'set_brake_torque', 'set_steer_angle', 'is_sleeping']},
        existing_visual_setter_present='set_wheel_steer_direction' in vehicle,
        missing_capabilities=[
            'published physics-on per-wheel signed motor torque setter',
            'published physics-on per-wheel friction torque setter',
            'atomic frame-stamped wheel effort/work receipt',
            'physics sleeping and wheel constraint validity observation',
            'pressure-to-friction calibration for mkz_2020'],
        traces=[analyze(evidence/rel) for rel in [
            'm7_carla_1g/attempt06-flat-observation/capture/frames.jsonl',
            'm7_carla_1h/attempt02-external-flat/capture/frames.jsonl',
            'm7_carla_1h/attempt03-final-slope/capture/frames.jsonl']],
        limits=['Method-name absence is combined with official API/source review; it is not proof about every external backend.',
                'Public upstream PhysX source is a design reference, not verified binary/source identity of bundled UE.',
                'Actor is_active/is_dormant reports actor streaming state, not PhysX sleep.',
                'Previous free-rolling flat trace has no applied protective Brake Actual; it cannot classify signed jitter as sensor noise.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(carla=result['carla_distribution'], new_server_runs=0,
                         samples=[x['historical_samples'] for x in result['traces']],
                         negative_samples=[x['negative_rear_samples'] for x in result['traces']]), indent=2))


if __name__ == '__main__':
    main()
