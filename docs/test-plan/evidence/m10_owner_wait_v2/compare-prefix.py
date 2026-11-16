"""Post-run matched moving-prefix comparison; no new acceptance verdict."""
import argparse
import csv
import gzip
import io
import json
from pathlib import Path
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from audit_state_path_v1 import join,quant

p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);a=p.parse_args()
baseline=ROOT/'docs/test-plan/evidence/m10_state_path_v3/normal-30s-01'


def prefix(open_binary):
    with open_binary('capture/native-state-path.csv') as stream:
        native={int(r['frame']):{k:int(v) for k,v in r.items()}
                for r in csv.DictReader(io.TextIOWrapper(stream)) if int(r['frame'])}
    rows=[]
    with open_binary('capture/trace.jsonl.gz') as compressed:
        with gzip.open(compressed,'rt') as stream:
            for line in stream:
                record=json.loads(line);receipt=record['receipt'];ticket=int(receipt['ticket'])
                if ticket>900:break
                if ticket<200:continue
                row=join(receipt,native[int(receipt['frame'])],record['state_path'])
                if not row['normal']:raise ValueError('prefix contains non-normal receipt')
                rows.append(row)
    if [r['ticket'] for r in rows]!=list(range(200,901)):
        raise ValueError('complete declared tickets200..900 required')
    result={key:quant(r[key] for r in rows) for key in ('acquisition_to_publication_ns',
        'publication_to_native_upper_ns','acquisition_to_native_ns','native_service_ns','max_pump_gap_ns','max_rpc_ns')}
    result['stages']={phase:{metric:quant(r['owner_spans'][phase][metric] for r in rows)
        for metric in ('wall_ns','cpu_ns','wall_minus_cpu_ns')} for phase in rows[0]['owner_spans']}
    result['owner_cpu_sum_ns']=quant(sum(s['cpu_ns'] for s in r['owner_spans'].values()) for r in rows)
    return result


try:
    manifest=json.loads((baseline/'run-manifest.json').read_text())
    with tarfile.open(baseline/manifest['archive'],'r:gz') as tar:
        before=prefix(tar.extractfile)
    after=prefix(lambda name:(a.run/name).open('rb'))
    metrics={key:dict(baseline_median_ns=before[key]['median_ns'],candidate_median_ns=after[key]['median_ns'],
        median_change_percent=100*(after[key]['median_ns']/before[key]['median_ns']-1))
        for key in ('acquisition_to_publication_ns','acquisition_to_native_ns','owner_cpu_sum_ns')}
    result=dict(status='PASS_MATCHED_PREFIX',scope='descriptive between-run comparison of701 normal moving tickets200..900; host clocks and thermal history are not controlled; no physical acceptance',
        baseline_run_sha256=manifest['sha256'],baseline=before,candidate=after,metrics=metrics)
except Exception as error:
    result=dict(status='NOT_COMPARABLE',error=str(error))
a.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('baseline','candidate')},indent=2))
