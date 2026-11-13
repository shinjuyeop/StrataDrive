import json,os,signal,time,select
from pathlib import Path
pid=3823961;out=Path('/d/shin/StrataDrive/build/m10-paired-v2/ddc-preparation-01/memory-guard.json')
r=dict(schema='m10-ddc-memory-guard-v1',pid=pid,begin_ns=time.monotonic_ns(),minimum_available_bytes=2*1024**3,events=[])
fd=os.pidfd_open(pid);p=Path('/proc')/str(pid)
try:
 args=(p/'cmdline').read_bytes().split(b'\0')
 if b'-run=DerivedDataCache' not in args or os.getpgid(pid)!=pid:raise ValueError('expected owned cache process')
 score=p/'oom_score_adj';r['original_oom_score_adj']=int(score.read_text());score.write_text('1000');r['cache_oom_score_adj']=1000
 first=None;minimum=2**63
 while not select.select([fd],[],[],0)[0]:
  info={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.split(':')[0] in ('MemAvailable',)}
  available=info['MemAvailable'];minimum=min(minimum,available);now=time.monotonic_ns()
  if available<r['minimum_available_bytes'] and first is None:
   signal.pidfd_send_signal(fd,signal.SIGINT);first=now;r['events'].append(dict(action='SIGINT',wall_ns=now,available_bytes=available))
  if first and now-first>=30_000_000_000:
   os.killpg(pid,signal.SIGKILL);r['events'].append(dict(action='SIGKILL',wall_ns=now,available_bytes=available));break
  r['minimum_observed_available_bytes']=minimum;r['last_ns']=now
  out.write_text(json.dumps(r,indent=2)+'\n');time.sleep(1)
finally:
 os.close(fd);r['end_ns']=time.monotonic_ns();out.write_text(json.dumps(r,indent=2)+'\n')
