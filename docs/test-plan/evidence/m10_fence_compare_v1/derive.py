"""Post-run summaries derived only from retained original timestamps/receipts."""
import csv
import json


def derive(bundle, timing):
    conditions = []
    for name in ('camera-absent-01', 'camera-2k-01'):
        run = bundle / name
        audit = timing.audit(run)
        rows = timing.reader.parse((run / 'server.log').read_text())
        capture = run / 'capture'
        result = json.loads((capture / 'result.json').read_text())
        startup = json.loads((capture / 'native-startup.json').read_text())
        jobs = list(csv.DictReader((capture / 'native.csv').open()))
        failed = next(row for row in jobs if int(row['protection']))
        events = json.loads((capture / 'events.json').read_text())
        last = [row['response'] for row in events if row['op'] == 'describe'][-1]
        a, b = audit['largest_gap']['begin'], audit['largest_gap']['end']
        # CPU durations are reported for whole brackets, never clipped using
        # wall timestamps or subtracted from a different clock domain.
        spans = [dict(stage=r['stage'], wall_ns=r['end']-r['begin'],
                      thread_cpu_ns=r['cpu_end']-r['cpu_begin']) for r in rows
                 if r['stage'] in ('frame_sync', 'fence_wait', 'task_wait_render')
                 and r['begin'] < b and r['end'] > a]
        receipts = [json.loads(line) for line in (capture / 'trace.jsonl').read_text().splitlines()]
        conditions.append(dict(
            name=name, binding_frame=audit['binding_frame'],
            receipt_frames=[int(r['receipt']['frame']) for r in receipts],
            first_protection_ns=int(failed['protection']),
            protection_after_enable_ns=int(failed['protection'])-startup[0]['enable_ns'],
            wheel_age_at_first_protection_ns=int(failed['now'])-int(failed['wheel_source']),
            hv_dependency_age_at_first_protection_ns=int(failed['now'])-int(failed['hv_dependency']),
            startup=[dict(leaf=r['leaf'], first_body_after_enable_ns=r['first_body_ns']-r['enable_ns'],
                          first_body_fault=r['first_body_fault']) for r in startup],
            normal_intervals=int(last['wall_normal_intervals']),
            server_lifetime_max_pump_gap_ns=int(last['max_pump_gap_ns']),
            native_service_window_largest_journal_gap_ns=b-a,
            overlapping_full_brackets=spans,
            journal_components={c:sum(r['component']==c for r in rows)
                                for c in sorted(timing.reader.STAGES)},
            native_exit=result['native_exit'],
            cleanup_error=result.get('cleanup_error'),
            camera_cleanup_error=result.get('camera_cleanup_error')))
    return dict(scope='post-run descriptive derivation; two failed trials, no steady capture sample',
                conditions=conditions, driving_acceptance=False)
