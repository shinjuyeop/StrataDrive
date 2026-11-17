"""Probe the observed next-pump timestamp; preserve the original trajectory."""
import csv,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];S=Path(__file__).resolve().parent;B=S/'normal-300s-01'
W=ROOT/'build/m10-gc-recovery-v3/normal-300s-01';R=W/'archive-check/run';prior=W/'admission-replay'
read=lambda p:json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report=read(B/'admission-replay.json');recovery=read(B/'recovery-window-analysis.json')
assert sha(prior/'replay-admission')==report['binary_sha256']
assert sha(prior/'events.txt')==report['event_input_sha256']
at=int(recovery['gc']['end']['wall_ns'])+recovery['next_pump_after_gc_ns'];observed=None
with (R/'capture/native-state-path.csv').open() as stream:
 for row in csv.DictReader(stream):
  if int(row['proof_publish_ns'])>at:break
  observed=int(row['service_begin_ns'])
assert observed is not None
out=W/'exact-next-pump';out.mkdir(exist_ok=False);pending=[(at,k) for k in ('C','Z')]
with (prior/'events.txt').open() as source,(out/'events.txt').open('w') as target:
 for line in source:
  columns=line.split(' ',3);key=(int(columns[1]),columns[0])
  assert key not in pending,'original grid already includes the exact point'
  while pending and pending[0]<key:
   t,k=pending.pop(0);target.write(f'{k} {t} {observed} 0 -\n')
  target.write(line)
 assert not pending
prefix=out/'replay'
subprocess.run([str(prior/'replay-admission'),str(W/'replay/input.txt'),str(ROOT/'tests/integration/carla/scenarios/m10_endurance_hold_v1.txt'),str(prefix),'5','300',str(out/'events.txt')],check=True)
assert (out/'replay.csv').read_bytes()==(W/'replay/replay.csv').read_bytes()
with (out/'replay-admission.csv').open() as stream:
 rows=[row for row in csv.DictReader(stream) if int(row['at'])==at and row['kind'] in ('C','Z')]
assert len(rows)==2
result=dict(status='EXACT_ORIGINAL_REPLAY_WITH_READ_ONLY_PUMP_QUERIES',query_wall_ns=at,
 query_after_gc_ns=recovery['next_pump_after_gc_ns'],latest_published_native_observed_ns=observed,
 queries=rows,original_native_replay_exact=True,original_proof_bytes_equal=True,
 binary_sha256=report['binary_sha256'],derived_event_sha256=sha(out/'events.txt'),
 scope='300us and0 extra-reserve eligibility on the original proof at the recorded next-pump stamp; no new physics, modified timestamp or acceptance claim')
(B/'exact-next-pump.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
