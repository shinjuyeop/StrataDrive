#!/usr/bin/env python3
"""Audit the wall owner probe. Synthetic plant only; never a CARLA/M7 exit PASS."""
import argparse
import csv
import json
from pathlib import Path


def audit(prefix):
    meta = json.loads(prefix.with_suffix('.json').read_text())
    with prefix.with_suffix('.csv').open() as stream:
        rows = [{k: float(v) if k in ('pressure_pa', 'torque_nm') else int(v)
                 for k, v in row.items()} for row in csv.DictReader(stream)]
    with Path(str(prefix)+'-wall.csv').open() as stream:
        jobs = [{k: int(v) for k, v in row.items()} for row in csv.DictReader(stream)]
    result = dict(scope=meta['scope'], mode=meta['mode'], checks=[], full_m7_closed=False)

    def check(name, condition):
        result['checks'].append(dict(name=name, passed=bool(condition)))

    check('synthetic_scope_explicit', meta['scope'] == 'wall owner with stationary synthetic work; NOT CARLA')
    check('no_owner_exception', not meta['exception'])
    check('separate_owner_and_io_threads', meta['owner']['tid'] != meta['io']['tid'])
    check('bounded_nonempty_trace', 1000 <= len(rows) <= 2000)
    if not rows:
        result['status'] = 'FAIL'; return result
    initial, end = meta['initial_ns'], rows[-1]['now_ns']
    check('actual_monotonic_service', all(a['now_ns'] < b['now_ns'] for a, b in zip(rows, rows[1:])))
    check('all_eight_roles_serviced', all(r['service_mask'] == 255 for r in rows))
    check('no_backfilled_controller_jobs', all(b['controller_releases']-a['controller_releases'] in (0, 1)
                                             for a, b in zip(rows, rows[1:])))
    check('original_sensor_and_energy_times', all(r['wheel_source_ns'] <= r['now_ns'] and
          r['energy_end_ns'] <= r['now_ns'] for r in rows))
    complete = [r for r in jobs if r['deadline_ns'] <= end]
    check('original_2ms_4ms_grid', bool(complete) and all(
        r['release_ns'] == initial+1_000_000+r['slot']*2_000_000 and
        r['deadline_ns'] == r['release_ns']+4_000_000 for r in complete))
    check('all_ten_owners_measured', {r['owner'] for r in complete} == set(range(10)))
    check('no_fabricated_completion', all(not r['end_ns'] or
        r['release_ns'] <= r['start_ns'] <= r['end_ns'] for r in complete))
    missing = [r for r in complete if not r['end_ns']]
    late = [r for r in complete if r['end_ns'] > r['deadline_ns']]
    result.update(rows=len(rows), complete_slots=len(complete), missing_slots=len(missing),
                  late_slots=len(late), first_fault=meta['first_fault'])
    faults = [r for r in rows if r['failed']]
    check('established_normal_before_injection', any(r['armed'] and r['credit_mask'] == 255
                                                  and r['now_ns'] < initial+1_100_000_000 for r in rows))
    expected_energy = initial+(1_100_000_000 if meta['mode'] == 'gap' else 1_490_000_000)
    check('all_produced_work_settled', rows[-1]['energy_end_ns'] == expected_energy and
          len(meta['deliveries_ns']) == (110 if meta['mode'] == 'gap' else 149))
    if meta['mode'] == 'normal':
        check('normal_never_faulted', not faults and not meta['first_fault'])
        check('normal_original_deadlines', not missing and not late)
        check('normal_stays_armed', rows[-1]['armed'] and rows[-1]['credit_mask'] == 255)
    else:
        check('injected_fault_observed', bool(faults))
        if faults:
            first = faults[0]
            injection = initial+1_100_000_000
            check('no_preinjection_failure', first['now_ns'] >= injection)
            check('original_100ms_loss_bound', first['now_ns']-injection <= 100_000_000)
            check('protection_terminal', all(not r['armed'] and r['credit_mask'] == 0 and
                  r['protection_ns'] == first['protection_ns'] for r in faults))
            # Zone acknowledgement follows the original leaf selection on the
            # next real service. A local fault flag is not already all 8 ACKs.
            selected = [r for r in faults if r['selected_mask'] == 255]
            check('all_roles_selected_inside_original_100ms_bound', bool(selected) and
                  selected[0]['now_ns']-injection <= 100_000_000 and
                  all(r['selected_mask'] == 255 for r in faults if r['now_ns'] >= selected[0]['now_ns']))
            if selected:
                result['selection_after_fault_ns'] = selected[0]['now_ns']-first['now_ns']
            protected = [r for r in faults if r['pressure_pa'] >= 1_000_000 and r['torque_nm'] == 0 and
                         r['brake_source_ns'] >= first['protection_ns'] and r['drive_source_ns'] >= first['protection_ns']]
            check('original_230ms_response_bound', bool(protected) and
                  protected[0]['now_ns']-first['protection_ns'] <= 230_000_000)
            if protected:
                result['response_ns'] = protected[0]['now_ns']-first['protection_ns']
            result['fault_after_injection_ns'] = first['now_ns']-injection
            if meta['mode'] == 'gap':
                check('owner_keeps_original_deadlines_during_io_gap', not missing and not late)
                check('held_wheel_and_energy_never_restamped', all(r['wheel_source_ns'] == expected_energy and
                      r['energy_end_ns'] == expected_energy for r in faults))
            else:
                check('injected_owner_stall_is_not_backfilled', bool(missing) and
                      meta['first_fault'] == 'wall execution deadline')
    result['status'] = 'PASS_CASE_ONLY' if all(c['passed'] for c in result['checks']) else 'FAIL'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prefix', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.prefix)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    return int(result['status'] == 'FAIL')


if __name__ == '__main__':
    raise SystemExit(main())
