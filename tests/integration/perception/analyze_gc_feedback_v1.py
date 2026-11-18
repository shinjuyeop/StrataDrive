"""Decode retained original CAN/P05 proofs around GC; never synthesize authority."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'carla'))
from audit_m7_1q_native import wire, frame

DOMAIN = 0x4D374D4F4E4F3031


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def analyze(path, gc_end):
    transitions = []
    previous = None
    for line in Path(path).read_text().splitlines():
        fields = line.split()
        if len(fields) != 30:
            raise ValueError('original proof layout')
        observed = int(fields[0])
        if abs(observed - gc_end) > 25_000_000:
            continue
        roles = []
        for role in range(3):
            zone = 0 if role < 2 else 1
            actual = frame(wire(fields[8 + role], zone, 7, 9, DOMAIN), role, True, False)
            packet = wire(fields[11 + role], zone, role + 2, 5, DOMAIN)
            packet.get('IQQQI')
            command = frame(packet, role, False)
            if packet.get('B') != 1:
                raise ValueError('missing original allocation context')
            epoch, sequence, source, expiry, acceleration, curvature, brake, hold = packet.get('IIQQdddB')
            oldest, allocated_expiry = packet.get('QQ')
            roles.append(dict(actual=actual, command=command,
                parent=dict(epoch=epoch, sequence=sequence, source_ns=source, expiry_ns=expiry),
                oldest_input_ns=oldest, allocated_expiry_ns=allocated_expiry))
        identity = (fields[2], tuple((r['actual']['seq'], r['command']['seq']) for r in roles))
        if identity == previous:
            continue
        previous = identity
        transitions.append(dict(observed_ns=observed, after_gc_ms=(observed-gc_end)/1e6,
            native_normal=fields[2] == '1', roles=roles))
    if not transitions:
        raise ValueError('no original proofs in GC window')
    fresh = next(r for r in transitions if r['roles'][2]['actual']['wheel_source'] > gc_end)
    stale = [r for r in transitions if r['observed_ns'] < fresh['observed_ns']][-1]
    old_wheel = stale['roles'][2]['actual']['wheel_source']
    fresh_command = fresh['roles'][2]
    return dict(schema='m10-gc-feedback-analysis-v1', scope='Read-only original replay proof diagnosis; no live or alternate-trajectory acceptance',
        source=dict(path=str(path), sha256=sha(path)), gc_end_ns=gc_end, transitions=transitions,
        finding=dict(old_wheel_source_ns=old_wheel,
            first_fresh_actual_observed_ns=fresh['observed_ns'],
            first_fresh_actual_after_gc_ms=fresh['after_gc_ms'],
            inherited_command_expiry_ns=fresh_command['allocated_expiry_ns'],
            matches_old_wheel_30ms_bound=fresh_command['allocated_expiry_ns'] == old_wheel + 30_000_001,
            remaining_command_lifetime_ms=(fresh_command['allocated_expiry_ns']-fresh['observed_ns'])/1e6,
            original_physics_interval_ms=5,
            has_whole_physics_interval=fresh_command['allocated_expiry_ns'] > fresh['observed_ns']+5_000_000),
        runtime_changed=False, milestone_closed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proofs', type=Path, required=True)
    parser.add_argument('--gc-end', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with args.output.open('x') as out:
        json.dump(analyze(args.proofs, args.gc_end), out, indent=2)
        out.write('\n')
