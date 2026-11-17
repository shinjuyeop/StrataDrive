"""Audit the declared structured preview margin, separate from physical acceptance."""
import argparse
import gzip
import json
from pathlib import Path


def validate_receipt(r):
    if (r.get('structured_state') is not True or r.get('wall_preview_reserve_ns') != '2000000'
            or r.get('model_step_ns') != '5000000' or r.get('admission_profile') != 'whole-interval-v1'):
        raise ValueError('declared structured 2ms preview and original 5ms interval')
    out = r['original_actual']['admitted_actual']
    if out['empty_init']:
        return
    through = int(out['command_checked_through_ns'])+2_000_000
    if (through >= int(out['exclusive_expiry_ns'])
            or through-int(out['oldest_actuator_ns']) > 30_000_000):
        raise ValueError('original authority must cover physics plus declared staging reserve')


def audit(run):
    result = json.loads((run/'capture/result.json').read_text())
    for value in (result['binding'], result['final_server']):
        if value.get('wall_preview_reserve_ns') != '2000000' or not value.get('structured_state'):
            raise ValueError('actual candidate binding/readback')
    count = normal = 0
    with gzip.open(run/'capture/trace.jsonl.gz', 'rt') as stream:
        for line in stream:
            r = json.loads(line)['receipt']; validate_receipt(r)
            count += 1; normal += bool(r['original_actual']['admitted_actual']['normal'])
    if count != result['requested_intervals']:
        raise ValueError('complete original receipts')
    return dict(status='PASS_ADMISSION_WINDOW_INTEGRITY', receipts=count, normal=normal,
                preview_reserve_ns=2_000_000, physics_interval_ns=5_000_000, original_age_ns=30_000_000,
                scope='preview configuration and original whole-interval coverage; not physical acceptance')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    try: result = audit(a.run)
    except Exception as error: result = dict(status='FAIL', error=str(error).replace(str(a.run), '<run>'))
    a.output.write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result))
    raise SystemExit(0 if result['status']=='PASS_ADMISSION_WINDOW_INTEGRITY' else 1)
