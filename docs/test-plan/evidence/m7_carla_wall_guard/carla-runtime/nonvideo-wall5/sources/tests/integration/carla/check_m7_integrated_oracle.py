#!/usr/bin/env python3
"""Corrupt saved camera/scenario metadata and require independent rejection."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
from audit_m7_integrated import audit


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();audit(a.directory)
    original=json.loads((a.directory/'result.json').read_text());sensors=json.loads((a.directory/'sensors.json').read_text())
    mutations={
        'changed_request_profile':lambda r,s:r['scenario'].update(text=r['scenario']['text'].replace('3500 1.0','3500 0.9')),
        'GT_control_use':lambda r,s:s.update(gt_control_use=True),
        'RGB_restamp':lambda r,s:s['streams']['rgb'][3].update(timestamp=s['streams']['rgb'][4]['timestamp']),
        'RGB_missing_frame':lambda r,s:s['streams']['rgb'].pop(3),
        'wrong_actor':lambda r,s:s['streams']['rgb'][3].update(ego_id=0),
        'GT_purpose':lambda r,s:s['streams']['gt'][3].update(use='DRIVING_INPUT'),
        'invalid_image':lambda r,s:s['streams']['rgb'][3].update(validity='INVALID'),
    }
    rejections={}
    with tempfile.TemporaryDirectory() as temp:
        directory=Path(temp)
        trace=a.directory/'trace.jsonl'
        if not trace.exists():trace=trace.with_suffix('.jsonl.gz')
        (directory/trace.name).symlink_to(trace.resolve())
        for name,mutate in mutations.items():
            result=copy.deepcopy(original);sensor=copy.deepcopy(sensors);mutate(result,sensor)
            (directory/'result.json').write_text(json.dumps(result));(directory/'sensors.json').write_text(json.dumps(sensor))
            try:audit(directory)
            except (ValueError,KeyError) as exc:rejections[name]=str(exc)
            else:raise AssertionError('corruption accepted: '+name)
    a.output.write_text(json.dumps(dict(status='PASS_MUTATION_REJECTION',rejected=rejections),indent=2)+'\n')


if __name__=='__main__':main()
