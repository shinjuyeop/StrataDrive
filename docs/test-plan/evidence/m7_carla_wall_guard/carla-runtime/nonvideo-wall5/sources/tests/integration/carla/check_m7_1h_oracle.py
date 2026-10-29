#!/usr/bin/env python3
"""Mutation checks for external ZOH evidence; leave originals untouched."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
from analyze_m7_1h import analyze


def main():
    p=argparse.ArgumentParser()
    p.add_argument('attempt',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    baseline=analyze(args.attempt)
    rows=[json.loads(l) for l in (args.attempt/'capture/frames.jsonl').read_text().splitlines()]
    def step(r):
        return r[200]['native']['electrical_steps'][0]
    cases={
        'future-wheel-source':lambda r:step(r).update(wheel_source_ns=step(r)['end_ns'],wheel_oldest_ns=step(r)['end_ns']),
        'fabricated-zero-wheel':lambda r:step(r).update(wheel_rad_s=0),
        'changed-interval-work':lambda r:step(r).update(mechanical_j=step(r)['mechanical_j']+1),
        'changed-cumulative-work':lambda r:step(r).update(total_mechanical_j=step(r)['total_mechanical_j']+1),
        'overlapping-interval':lambda r:step(r).update(begin_ns=step(r)['begin_ns']-1000000),
        'restamped-oldest':lambda r:step(r).update(wheel_oldest_ns=step(r)['wheel_source_ns']+1),
        'false-carla-work-claim':lambda r:r[200]['native'].update(carla_work_valid=True),
    }
    result=dict(baseline=baseline,mutations=[])
    with tempfile.TemporaryDirectory(prefix='m7-external-oracle-') as d:
        dest=Path(d);(dest/'capture').mkdir()
        for name in ['process.json','runner.py','capture/summary.json']:
            shutil.copyfile(args.attempt/name,dest/name)
        for name,mutate in cases.items():
            data=copy.deepcopy(rows);mutate(data)
            (dest/'capture/frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in data))
            try:
                analyze(dest)
                raise AssertionError('oracle accepted '+name)
            except ValueError as error:
                result['mutations'].append(dict(case=name,status='REJECTED',reason=str(error)))
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(str(len(cases))+'/'+str(len(cases))+' corrupt traces rejected')


if __name__=='__main__':
    main()
