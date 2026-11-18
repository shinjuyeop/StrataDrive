"""Measure potential separate-world result freshness at the original native observations."""
import argparse
from bisect import bisect_right
from collections import Counter
import hashlib
import json
from pathlib import Path

LIFETIME = 100_000_000


def indexed(rows, field):
    indexed_rows = {row[field]: row for row in rows}
    if len(indexed_rows) != len(rows):
        raise ValueError(f'duplicate {field}')
    return indexed_rows


def timing(state, result, association):
    now = state['observed_wall_ns']
    if not state['initialized'] or state['state_fault'] or state['disconnected']:
        return 'native_session_unavailable'
    if not 0 < state['wall_enable_ns'] <= state['state_received_wall_ns'] <= now:
        return 'state_wall_clock'
    if now-state['state_received_wall_ns'] >= LIFETIME:
        return 'stale_native_state'
    if not result:
        return 'no_completed_result'
    source = association['physical_source_ns']
    if source < state['source_enable_ns'] or result['original_acquisition_ns'] < state['wall_enable_ns']:
        return 'before_enable'
    if source > state['state_source_ns'] or association['physical_frame'] > state['state_frame']:
        return 'future_physical_state'
    if now-result['original_acquisition_ns'] >= LIFETIME:
        return 'scene_wall_expired'
    if state['state_source_ns']-source >= LIFETIME:
        return 'physical_source_expired'
    if now-result['callback_ns'] >= LIFETIME:
        return 'callback_expired'
    return 'time_eligible'


def analyze(run):
    capture = run/'capture'
    files = [capture/'paired/renderer/result.json', capture/'native-perception.jsonl', capture/'native.json']
    rendered, observations, native = [p.read_bytes() for p in files]
    report = json.loads(rendered)
    rows = report['inference']
    mappings = indexed(report['mapped'],'renderer_frame')
    images = indexed(report['raw'],'frame')
    ticks = indexed(report['ticks'],'renderer_frame')
    ends = []
    for r in rows:
        frame = r['renderer_frame']
        m, image, tick = mappings[frame], images[frame], ticks[frame]
        if not (m['physical_frame'] == tick['physical_frame'] == r['physical_frame']
                and m['scene_sha256'] == tick['scene_sha256'] == r['scene_sha256']
                and m['renderer_source_ns'] == image['source_ns'] == tick['renderer_source_ns']
                and m['original_acquisition_begin_ns'] == r['original_acquisition_ns']
                and m['callback_received_ns'] == image['received_wall_ns'] == r['callback_ns']
                and 0 < r['original_acquisition_ns'] <= m['original_acquisition_end_ns'] <= tick['apply_begin_ns']
                <= tick['tick_begin_ns'] <= r['callback_ns'] <= r['begin_ns'] <= r['end_ns']
                and not r['accepted_for_control'] and 'error' not in r):
            raise ValueError('original scene, renderer/callback, result association or timing')
        ends.append(r['end_ns'])
    if ends != sorted(set(ends)):
        raise ValueError('ordered unique completions')
    start=json.loads(native)['initial']
    stop=start+report['endurance_seconds']*1_000_000_000
    reasons=Counter()
    eligible_frames=set()
    accepted=last_wall=0
    for line in observations.splitlines():
        state=json.loads(line)['perception']
        now=state['observed_wall_ns']
        if now < last_wall:
            raise ValueError('regressing native observation clock')
        last_wall=now
        if not start <= now < stop:
            continue
        index=bisect_right(ends,now)-1
        result=rows[index] if index>=0 else None
        reason=timing(state,result,mappings[result['renderer_frame']] if result else None)
        reasons[reason]+=1
        if reason=='time_eligible':
            eligible_frames.add(result['renderer_frame'])
        accepted=max(accepted,state['accepted_results'])
    count=sum(reasons.values())
    if not count:
        raise ValueError('empty native observation window')
    return dict(schema='m10-native-read-freshness-v1', start_wall_ns=start, stop_wall_ns=stop,
        native_observations=count, eligible_observations=reasons['time_eligible'],
        eligible_sample_fraction=reasons['time_eligible']/count, unique_eligible_results=len(eligible_frames),
        successful_inferences=len(rows), timing_outcomes=dict(reasons), actual_reported_accepted_results=accepted,
        scope='Original native observations with latest completed result. Assumes immediate transport. Timing eligibility only; full scene, delivery and ECU acceptance are separate.',
        inputs={str(p.relative_to(run)):hashlib.sha256(data).hexdigest() for p,data in zip(files,(rendered,observations,native))})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    result=analyze(a.run)
    with a.output.open('x') as f:
        json.dump(result,f,indent=2)
        f.write('\n')
    print(result)
