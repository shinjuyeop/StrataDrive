#!/usr/bin/env python3
"""Post-run physical-response audit; not a prospective timing/WCET verdict.

Usage: python3 docs/test-plan/evidence/m4_faults/summarize_response.py RAW_DIR
Reads original full-rate traces. Keeps existing model/normal/protection criteria,
reports short-run bus discharge separately from actual HV OFF confirmation.
"""
import csv
import hashlib
import json
from pathlib import Path
import sys


def main():
    raw = Path(sys.argv[1])
    output = Path(__file__).resolve().parent
    results = []; timeline = []
    metadata = json.loads((raw/'metadata.json').read_text())
    for profile in ('normal','sanitized'):
        for path in sorted((raw/profile/'faults').glob('*/*-fault.json')):
            summary = json.loads(path.read_text())
            events = list(csv.DictReader(path.with_name(path.stem+'-events.csv').open()))
            injected = summary['effective_injection_ns']
            origin = int(events[0]['time_ns'])-round(float(events[0]['elapsed_ms'])*1e6)
            for owner in range(10):
                own = [e for e in events if int(e['owner'])==owner]
                after = [e for e in own if int(e['time_ns'])>=origin+injected]
                detected = next((e for e in after if e['kind'] in ('fault-observed','session-failed')),None)
                cutoff = int(detected['time_ns']) if detected else origin+injected
                valid = [e for e in own if e['kind'] in ('valid-input','valid-feedback') and int(e['time_ns'])<=cutoff]
                last_valid = valid[-1] if valid else None
                def first(name):
                    return next((int(e['time_ns']) for e in after if e['kind']==name),0)
                timeline.append({'profile':profile,'case':path.parent.name,'owner':owner,
                                 'effective_injection_ns':origin+injected,'last_valid_observation_ns':last_valid['time_ns'] if last_valid else 0,
                                 'last_valid_rx_ns':(last_valid['reference_ns'] if last_valid['kind']=='valid-input' else last_valid['time_ns']) if last_valid else 0,
                                 'original_source_ns':last_valid['source_ns'] if last_valid else 0,'original_deadline_ns':last_valid['deadline_ns'] if last_valid else 0,
                                 'controller_fault_ns':detected['time_ns'] if detected else 0,'gate_observed_ns':first('gate-closed-observed'),
                                 'leaf_selection_ns':first('leaf-protection-selected'),'zone_ack_ns':first('zone-protection-ack'),
                                 'physical_watchdog_ns':first('output-watchdog'),'physical_override_ns':first('override-applied')})
            trace = list(csv.DictReader(path.with_suffix('.csv').open()))
            limit = summary['recovery_ns']/1e6 if summary['recovery_ns'] else float('inf')
            before_recovery = [r for r in trace if float(r['elapsed_ms']) < limit]
            last = before_recovery[-1]
            tail = [r for r in before_recovery if float(r['elapsed_ms']) >= float(last['elapsed_ms'])-50]
            angles = [float(r['angle_rad']) for r in tail]
            pressure = float(last['pressure_pa']); torque = float(last['torque_nm'])
            contacts = int(last['contacts']); bus = float(last['bus_v'])
            # Original fixture: active fault eventually selects hold/floor/zero,
            # actual coils open; no new response-time acceptance threshold here.
            active = summary['first_active_ns'] > 0
            safe = not active or (max(angles)-min(angles) < 1e-9 and pressure >= 1_000_000-1e-6 and abs(torque) < .1 and contacts == 0)
            assert safe, (profile,path.parent.name,'physical response contract')
            assert summary['model_preserved'] and summary['stopped_ack_violations']==0
            results.append({'profile':profile,'case':path.parent.name,'active_before_fault':active,
                            'observed_ms':last['elapsed_ms'],'angle_rad':last['angle_rad'],'last_50ms_angle_span_rad':max(angles)-min(angles),
                            'pressure_pa':pressure,'torque_nm':torque,'contacts':contacts,'bus_v':bus,
                            'actual_hv_off':contacts==0 and bus<30,'soc':last['soc'],'energy_j':last['energy_j'],
                            'model_epoch':last['model_epoch'],'model_sequence':last['model_sequence'],
                            'live_selection_mask_100ms':summary['live_selection_mask'],'missing_selection_mask_100ms':summary['missing_selection_mask'],
                            'posthoc_response_verdict':'PASS' if active else 'NOT APPLICABLE (never active)'})
    with (output/'physical-results.csv').open('w') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(results[0]),lineterminator='\n');writer.writeheader();writer.writerows(results)
    with (output/'timeline.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(timeline[0]),lineterminator='\n');writer.writeheader();writer.writerows(timeline)
    # New-source normal representative; historical m4_async evidence is retained.
    normal = list(csv.DictReader((raw/'normal/logical-normal.csv').open()))
    with (output/'normal.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(normal[0]),lineterminator='\n');writer.writeheader();writer.writerows(normal[::3]+[normal[-1]])
    manifest={'kind':'post-run physical audit; no new timing acceptance','source_commit':metadata['source_commit'],
              'source_digest':metadata['source_digest'],'analysis_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'active_response_pass':sum(r['active_before_fault'] for r in results),
              'never_active_not_applicable':sum(not r['active_before_fault'] for r in results),'rows':len(results)}
    (output/'physical-audit.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest))


if __name__=='__main__': main()
