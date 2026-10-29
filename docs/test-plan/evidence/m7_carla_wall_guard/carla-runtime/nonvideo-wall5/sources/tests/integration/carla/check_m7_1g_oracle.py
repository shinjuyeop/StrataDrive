#!/usr/bin/env python3
"""Mutation checks against a completed native live trace, never modify evidence."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
from analyze_m7_1g import analyze


def main():
    p=argparse.ArgumentParser()
    p.add_argument('attempt',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    baseline=analyze(args.attempt)
    rows=[json.loads(l) for l in (args.attempt/'capture/frames.jsonl').read_text().splitlines()]
    cases={
        'source-restamp':lambda r:r[200]['native']['returned_wheel'].update(source_ns=round(r[200]['sim_s']*1e9)+1),
        'wrong-wheel-value':lambda r:r[200]['native']['returned_wheel'].update(rad_s=99),
        'wrong-actor':lambda r:r[200].update(actor=0),
        'duplicate-frame':lambda r:r[200].update(frame=r[199]['frame']),
        'future-tick-permit':lambda r:r[200]['native'].update(next_frame=r[200]['frame']+2),
        'fake-normal-driving':lambda r:r[200]['native'].update(driving=True),
        'missing-credit':lambda r:r[200]['native'].update(credit_mask=127),
    }
    result=dict(baseline=baseline,mutations=[])
    with tempfile.TemporaryDirectory(prefix='m7-wheel-oracle-') as d:
        dest=Path(d)
        (dest/'capture').mkdir()
        for name in ['process.json','runner.py','capture/summary.json']:
            shutil.copyfile(args.attempt/name,dest/name)
        for name,mutate in cases.items():
            data=copy.deepcopy(rows)
            mutate(data)
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
