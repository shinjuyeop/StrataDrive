"""Analyze the preserved pre-native failure without assigning missing control data."""
from collections import Counter,defaultdict
import gzip,hashlib,json,os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];S=Path(__file__).resolve().parent;B=S/'normal-30s-01';R=ROOT/'build/m10-gc-recovery-v1/normal-30s-01/archive-check/run'
read=lambda p:json.loads(p.read_text())
server=read(R/'server.json');capture=read(R/'capture/result.json');perception=read(R/'capture/perception.json')
prep=perception['preparation'];begin=prep['started_wall_ns'];end=prep['finished_wall_ns']
assert capture['receipts']==0 and 'preparation deadline' in capture['error']
assert prep['state']=='FAILED' and prep['calls']==[] and perception['preparation_calls']==[]
assert not (R/'capture/native.json').exists() and not read(B/'raw-manifest.json')['archives']
client={p['pid'] for sample in server['resources'] for p in sample['processes'] if p['role']=='client'};assert len(client)==1;client=client.pop()
with gzip.open(R/'host-profile.jsonl.gz','rt') as stream:rows=[json.loads(x) for x in stream]
threads=defaultdict(list);gpu=[]
for row in rows:
 if not begin<=row['wall_ns']<=end:continue
 gpu.append(row['gpu']['gpu_percent'])
 for process in row['processes']:
  if process['pid']!=client:continue
  for thread in process['threads']:threads[thread['tid']].append(dict(wall_ns=row['wall_ns'],**thread))
summaries=[]
for tid,samples in threads.items():
 a,b=samples[0],samples[-1]
 summaries.append(dict(tid=tid,samples=len(samples),states=dict(Counter(x['state'] for x in samples)),first_wall_ns=a['wall_ns'],last_wall_ns=b['wall_ns'],major_fault_delta=b['major_faults']-a['major_faults'],cpu_ns=b['schedstat'][0]-a['schedstat'][0],scheduler_wait_ns=b['schedstat'][1]-a['schedstat'][1],affinities=[list(x) for x in sorted({tuple(x['affinity']) for x in samples})]))
summaries.sort(key=lambda x:x['major_fault_delta'],reverse=True)
result=dict(status='RECORDED_PRE_NATIVE_STARTUP_FAILURE',client_pid=client,client_exit=server['client_exit'],preparation=prep,worker=perception['worker'],cleanup_errors=perception['cleanup_errors'],receipts=0,raw_packets=0,native_started=False,gc_recovery_measured=False,preparation_elapsed_ns=end-begin,gpu_samples=len(gpu),gpu_percent_range=[min(gpu),max(gpu)],threads=summaries,shutdown=server['shutdown'],interpretation='An active preparation thread repeatedly waited in D with increasing major faults and little CPU/GPU work. This supports file-backed page I/O as a startup contributor. The original sample has no function stack or file mapping, so it does not identify the exact library. Client exited SIGSEGV after reporting a still-busy worker at cleanup; the crash stack was not captured. No GC, native or physical comparison was reached.')
(B/'startup-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
archive=read(B/'run-manifest.json');payload=B/archive['archive'];assert hashlib.sha256(payload.read_bytes()).hexdigest()==archive['sha256']
review=B/'bounded-review.tar.gz';assert not review.exists();shutil.copy2(payload,review)
(B/'bounded-review.json').write_text(json.dumps(dict(status='PASS_FULL_STARTUP_REVIEW',archive=review.name,bytes=review.stat().st_size,sha256=archive['sha256'],members=len(archive['members']),basis='byte-identical full startup run archive, no camera payloads',original_case_verdict='FAIL'),indent=2)+'\n')
print(json.dumps(dict(preparation_ms=(end-begin)/1e6,gpu_percent_range=result['gpu_percent_range'],highest_fault_thread=summaries[0],review_bytes=review.stat().st_size)))
