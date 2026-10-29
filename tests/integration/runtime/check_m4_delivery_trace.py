#!/usr/bin/env python3
"""Fixed 20+20 M4 native diagnostic, opt-in full transport trace, no retries."""
import argparse
import csv
import datetime
import json
import os
from pathlib import Path
import platform
import runpy
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
BASE = runpy.run_path(str(ROOT/'tests/integration/runtime/check_m4_async.py'))
TEST = 'M4AsyncWall.IndependentOwnersRunActualNormalPath'
BUILDS = {'normal': 'build/m4-readiness', 'tsan': 'build/m4-tsan'}
REQUIRED = ('unit.xml', 'wall-normal.json', 'wall-normal.csv', 'wall-normal-events.csv',
            'wall-normal-execution.csv', 'wall-normal-transport.csv')


def read_csv(path):
    if not path.exists():
        return []
    with path.open() as stream:
        return list(csv.DictReader(stream))


def analyze(folder):
    events = read_csv(folder/'wall-normal-transport.csv')
    transactions = {}
    for event in events:
        if int(event['token']) == 0:
            continue
        key = (event['epoch'], event['token'])
        transactions.setdefault(key, []).append(event)
    rows = []
    for (epoch, token), group in transactions.items():
        start = next((e for e in group if e['stage'] == 'central-enqueued' and e['operation'] == '3'), None)
        if start is None:
            continue
        def first(stage):
            return next((int(e['time_ns']) for e in group if e['stage'] == stage), 0)
        row = {'epoch': epoch, 'token': token, 'zone': start['peer'],
               'source_ns': start['original_source_ns'], 'payload_source_ns': start['payload_source_ns'],
               'inner_expiry_ns': start['inner_deadline_ns'], 'sent_ns': start['sent_ns'],
               'envelope_deadline_ns': start['envelope_deadline_ns']}
        for stage in ('central-enqueued', 'zone-received', 'zone-command-dispatch', 'zone-leaf-enqueued',
                      'leaf-received', 'leaf-completed', 'leaf-output-published', 'zone-result-enqueued', 'central-result-received',
                      'central-result-accepted', 'central-result-rejected', 'central-result-timeout', 'command-still-pending'):
            row[stage] = first(stage)
        rows.append(row)
    if rows:
        with (folder/'transactions.csv').open('w') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    pending = [e for e in events if e['stage'] == 'command-still-pending']
    rejected = [e for e in events if e['stage'] in ('command-submit-rejected', 'central-post-rejected', 'central-post-full', 'central-result-rejected', 'central-result-timeout')]
    details = {'trace_rows': len(events), 'command_transactions': len(rows), 'rejections': rejected,
               'pending_at_submit': pending,
               'pending_chains': [e for e in events if any(e['epoch'] == p['epoch'] and e['token'] == p['token'] for p in pending)]}
    (folder/'analysis.json').write_text(json.dumps(details, indent=2)+'\n')
    return details


def trial_evidence(folder, metadata):
    """Missing/malformed/skipped evidence is a failed trial, never an empty PASS."""
    errors = [f'missing/empty {name}' for name in REQUIRED
              if not (folder/name).is_file() or (folder/name).stat().st_size == 0]
    result, detail, settings = {}, {'trace_rows': 0, 'command_transactions': 0, 'rejections': []}, False
    try:
        result = json.loads((folder/'wall-normal.json').read_text())
        if not isinstance(result, dict):
            raise ValueError('runtime result must be an object')
        threads = result.get('threads', [])
        settings = (len(threads) == 9 and {t['owner'] for t in threads} == set(range(9)) and
                    all(t['policy'] == 0 and t['priority'] == 0 and t['affinity'] == metadata['affinity']
                        and not t['setup_error'] for t in threads))
        if not settings:
            errors.append('owner/settings coverage')
        if (any(result.get(k) is not True for k in ('passed', 'ownership_ok', 'physical_ok', 'transport_trace_enabled'))
                or result.get('event_overflow') is not False or result.get('guards_enabled') is not False
                or result.get('duration_ns') != metadata['duration_ns']):
            errors.append('runtime verdict/trace/config')
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {}
        errors.append(f'runtime result: {error}')
    try:
        cases = ET.parse(folder/'unit.xml').getroot().findall('.//testcase')
        if (len(cases) != 1 or cases[0].get('classname', '')+'.'+cases[0].get('name', '') != TEST
                or any(cases[0].find(tag) is not None for tag in ('failure', 'error', 'skipped'))
                or cases[0].get('status') == 'notrun'):
            errors.append('missing/failed/skipped requested GTest')
    except (OSError, ET.ParseError) as error:
        errors.append(f'JUnit: {error}')
    try:
        detail = analyze(folder)
        if not detail['trace_rows'] or not detail['command_transactions']:
            errors.append('missing command transport trace')
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append(f'transport trace: {error}')
    (folder/'evidence-check.json').write_text(json.dumps({'errors': errors}, indent=2)+'\n')
    return result, detail, settings, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    digest = BASE['fingerprint']()
    metadata = {'source_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
                'source_digest': digest, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'kernel': platform.release(), 'compiler': subprocess.check_output(['c++','--version'], text=True).splitlines()[0],
                'affinity': sorted(os.sched_getaffinity(0)), 'policy': os.sched_getscheduler(0),
                'planned': 40, 'repetitions_per_profile': 20, 'test': TEST, 'duration_ns': 1800000000,
                'load': 'none', 'guards': False, 'transport_trace': True, 'process_aslr': 'setarch -R',
                'protocol': 'docs/archive/m4-test-protocols.md#m4_settlement_protocol'}
    (out/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    rows = []
    for repetition in range(1,21):
        for profile in (('normal','tsan') if repetition % 2 else ('tsan','normal')):
            folder = out/f'{repetition:02}-{profile}'; folder.mkdir()
            command = ['setarch','x86_64','-R',str(ROOT/BUILDS[profile]/'m4_async_runtime_test'),
                       '--gtest_filter='+TEST,'--gtest_output=xml:'+str(folder/'unit.xml')]
            changes = {'STRATADRIVE_M4_RESULTS': str(folder), 'STRATADRIVE_M4_TRANSPORT_TRACE': '1'}
            (folder/'command.json').write_text(json.dumps({'argv': command, 'env': changes},indent=2)+'\n')
            executed = True
            with (folder/'run.log').open('w') as f:
                try:
                    code = subprocess.run(command,cwd=ROOT,env={**os.environ,**changes},stdout=f,stderr=subprocess.STDOUT,timeout=30,check=False).returncode
                except subprocess.TimeoutExpired as error:
                    code = 124
                    f.write(f'\n{error}\n')
                except OSError as error:
                    code, executed = 127, False
                    f.write(f'\nlaunch failed: {error}\n')
            log = (folder/'run.log').read_text(errors='replace')
            result, detail, settings, errors = trial_evidence(folder, metadata)
            passed = executed and code == 0 and not errors and 'WARNING: ThreadSanitizer' not in log
            row = {'profile': profile,'repetition': repetition,'verdict': 'PASS' if passed else 'FAIL',
                   'exit_code': code,'settings_ok': settings,'trace_rows':detail['trace_rows'],
                   'warnings':log.count('WARNING: ThreadSanitizer'),'reason':result.get('reason', 'no runtime result'),
                   'submit_rejections':sum(e['stage']=='command-submit-rejected' for e in detail['rejections']),
                   'first_fault_ns':result.get('first_fault_ns',0),'raw':folder.name,
                   'executed': executed, 'evidence_errors': '; '.join(errors)}
            rows.append(row); (out/'cohort.json').write_text(json.dumps(rows,indent=2)+'\n'); print(json.dumps(row),flush=True)
    integrity = []
    try:
        if BASE['fingerprint']()!=digest:
            integrity.append('source changed during fixed cohort')
    except OSError as error:
        integrity.append(f'cannot verify source fingerprint: {error}')
    if len(rows) != metadata['planned'] or sum(r['executed'] for r in rows) != metadata['planned']:
        integrity.append('planned execution missing')
    with (out/'summary.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    results = {p:{v:sum(r['profile']==p and r['verdict']==v for r in rows) for v in ('PASS','FAIL')} for p in BUILDS}
    passed = not integrity and all(r['verdict'] == 'PASS' for r in rows)
    results['overall'] = {'verdict': 'PASS' if passed else 'FAIL', 'planned': metadata['planned'],
                          'recorded': len(rows), 'executed': sum(r['executed'] for r in rows), 'errors': integrity}
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    return 0 if passed else 1


if __name__=='__main__':
    raise SystemExit(main())
