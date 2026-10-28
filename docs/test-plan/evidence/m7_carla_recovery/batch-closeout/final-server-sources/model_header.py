"""Generate server-owned constants from the explicitly accepted virtual model."""
import hashlib
import json
from pathlib import Path


def generate():
    data = Path(__file__).with_name("virtual_ev_v1.json").read_bytes()
    m = json.loads(data)
    assert m["approval"] == "ACCEPTED_VIRTUAL_MODEL_ONLY"
    assert m["real_vehicle_calibration"] is False
    def values(xs):
        return ", ".join(format(x, ".17g") for x in xs)
    lines = ["// Generated from virtual_ev_v1.json. Do not edit.", "#pragma once",
             "namespace M7V1 {",
             f'constexpr const char* Id = "{m["id"]}";',
             f'constexpr const char* Sha = "{hashlib.sha256(data).hexdigest()}";',
             f'constexpr double Mass = {m["mass_kg"]};',
             f'constexpr double BrakeGain = {m["aggregate_friction_nm_per_pa"]:.17g};']
    for name, key in (("BrakeFractions", "brake_fractions"), ("MotorFractions", "motor_fractions"),
                      ("PressureRange", "pressure_range_pa"), ("DriveRange", "drive_range_nm"),
                      ("SteeringRange", "steering_range_left_rad")):
        lines.append(f"constexpr double {name}[] = {{{values(m[key])}}};")
    for name, key in (("X", "offset_x_m"), ("Y", "offset_y_right_m"), ("Radius", "radius_m"),
                      ("MaxBrake", "max_brake_nm"), ("MaxSteer", "max_steer_rad")):
        lines.append(f'constexpr double {name}[4] = {{{values(w[key] for w in m["wheels"])}}};')
    lines.append('constexpr const char* Bones[4] = {' + ', '.join(json.dumps(w['bone']) for w in m['wheels']) + '};')
    return "\n".join(lines + ["}", ""]).encode()
