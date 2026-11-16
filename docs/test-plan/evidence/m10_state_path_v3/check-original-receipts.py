"""Check the diagnostic correction separately from physical acceptance."""
import argparse
import gzip
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--run', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
with gzip.open(a.run/'capture/trace.jsonl.gz', 'rt') as stream:
    records = [json.loads(line) for line in stream]
receipts = {int(r['receipt']['frame']): r['receipt'] for r in records}
assert len(receipts) == len(records)
assert all('state_path' in r and 'state_path' not in r['receipt'] for r in records)
source = json.loads((a.run/'capture/paired/source.json').read_text())
assert source['queries']
assert all(receipts[int(r['frame'])] == r for r in source['queries'])
result = dict(status='PASS', scope='exact cached receipt equality and sibling diagnostics only; not physical acceptance',
              complete_receipts=len(records), cached_queries=len(source['queries']),
              diagnostic_fields_inside_original_receipt=0)
a.output.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
