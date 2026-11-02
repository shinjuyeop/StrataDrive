#!/usr/bin/env python3
"""Plot original body speed and decoded actuator acquisitions around terminal events."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from evidence_io import json_rows
from audit_m7_1q_native import frame, wire

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory', type=Path)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--case', action='append', help='Case basename; repeat for multiple columns')
a = p.parse_args()
cases = a.case or ('stop-01', 'input-loss-01')
fig, axes = plt.subplots(3, len(cases), figsize=(5.5 * len(cases), 8), sharex=True,
                         squeeze=False, constrained_layout=True)
for column, name in enumerate(cases):
    report = json.loads((a.directory / (name + '-audit.json')).read_text())
    data = []
    for row in json_rows(a.directory / name / 'trace.jsonl'):
        t = row['simulation_seconds'] - report['trigger_ns'] * 1e-9
        if not -1 <= t <= (12 if report['mode']=='normal-stop30' else 6):
            continue
        proof = row['native']['native_export']
        brake = frame(wire(proof['actual'][1], 0, 7, 9), 1, True, require_wheel=False)
        drive = frame(wire(proof['actual'][2], 1, 7, 9), 2, True, require_wheel=False)
        data.append((t, row['physics']['body_forward_velocity_m_s'] * 3.6,
                     drive['value'], brake['value'] / 1e6))
    t, speed, torque, pressure = zip(*data)
    for axis, values, label in zip(axes[:, column], (speed, torque, pressure),
                                  ('Body speed (km/h)', 'Actual torque (Nm)', 'Actual brake (MPa)')):
        axis.plot(t, values)
        axis.axvline(0, color='black', linestyle='--', alpha=.5)
        axis.axvline(report['stop_delay_s'], color='green', linestyle=':', label='Physical stop')
        if 'injection_ns' in report:
            axis.axvline((report['injection_ns'] - report['trigger_ns']) * 1e-9,
                         color='red', linestyle='-.', label='Protection injection')
        axis.set_ylabel(label)
        axis.grid(alpha=.25)
    town='Town06' if report['mode']=='normal-stop30' else 'Town03'
    axes[0, column].set_title(report['mode'] + ' | ' + town + ', simulation time')
    axes[0, column].legend(loc='upper right')
    if report['complete_delay_s'] is not None:
        axes[2, column].axvline(report['complete_delay_s'], color='purple', linestyle='-.', label='HV-off complete')
        axes[2, column].legend(loc='lower right')
    axes[2, column].set_xlabel('Seconds since terminal event')
fig.savefig(a.output, dpi=150)
