"""Verify the opt-in conversion change independently of physical acceptance."""
import argparse
import gzip
import json
from pathlib import Path


def validate_self_check(check):
    if check.get('ok') is not True or check.get('finite_double_patterns')!=4096:
        raise ValueError('complete before-START numeric check')
    if any(check.get(key) is not True for key in ('exact_number_bits','actual_physics_equal','mutation_checks')):
        raise ValueError('original bitwise state/type equivalence')
    if check.get('nonfinite_cases')!=3 or any(check.get(key) is not True for key in (
            'nonfinite_legacy_fallback','finite_direct_identity')):
        raise ValueError('original nonfinite parser behavior and finite direct identity')
    if check.get('internal_envelope_cases')!=9 or any(check.get(key) is not True for key in (
            'internal_envelope_bound','internal_envelope_equal','oversize_noncanonical_fallback')):
        raise ValueError('bounded original internal envelope')
    if check.get('scope')!='pre_native_START; no control service; bitwise JSON roundtrip and actual physics snapshot':
        raise ValueError('numeric check scope')


def audit(run):
    read=lambda p:json.loads((run/p).read_text())
    server=read('server.json');result=read('capture/result.json')
    if not server.get('structured_state') or not result.get('structured_state'):
        raise ValueError('undeclared structured state')
    validate_self_check(result['structured_json_check'])
    if not result['binding']['structured_state'] or not result['final_server']['structured_state']:
        raise ValueError('actual structured state binding')
    final=result['final_server']
    if int(final['structured_direct_requests'])<result['receipts']:
        raise ValueError('complete internal direct request coverage')
    if int(final['structured_text_fallback_requests']):
        raise ValueError('comparison requires canonical bounded direct requests')
    with gzip.open(run/'capture/trace.jsonl.gz','rt') as stream:
        records=[json.loads(line) for line in stream]
    receipts={int(r['receipt']['frame']):r['receipt'] for r in records}
    if len(receipts)!=len(records) or len(records)!=result['requested_intervals']:
        raise ValueError('complete original receipts')
    if any('state_path' not in r or 'state_path' in r['receipt'] for r in records):
        raise ValueError('original receipt diagnostic separation')
    queries=read('capture/paired/source.json')['queries']
    if not queries or any(receipts.get(int(r['frame']))!=r for r in queries):
        raise ValueError('cached original receipt unchanged')
    events=read('capture/events.json')
    check=next(e for e in events if e['op']=='structured_json_check')
    start=next(e for e in events if e['op']=='wall_start')
    if check['response']!=result['structured_json_check'] or check['wall_ns']>=start['wall_ns']:
        raise ValueError('numeric check precedes physical start')
    return dict(status='PASS_STRUCTURED_STATE_INTEGRITY',scope='conversion/receipt integrity only; original physical and shadow audits remain required',
        finite_double_patterns=4096,receipts=len(receipts),cached_queries=len(queries),
        direct_requests=int(final['structured_direct_requests']),text_fallback_requests=0,
        original_acquisition_preserved='also checked by audit_state_path_v1',native_perception_accepted=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as error:result=dict(status='FAIL',error=str(error).replace(str(a.run),'<run>'))
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    raise SystemExit(0 if result['status']=='PASS_STRUCTURED_STATE_INTEGRITY' else 1)
