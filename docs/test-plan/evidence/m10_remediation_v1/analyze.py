"""Retained observations only: original frozen audits determine each verdict."""
import csv,gzip,json,statistics,sys
from pathlib import Path
root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root/'tests/integration/carla'))
from evidence_io import json_rows
cases=[]
for version in range(4,9):
 name='normal-30s-01';bundle=root/f'docs/test-plan/evidence/m10_endurance_v{version}'/name
 run=root/f'build/m10-endurance-v{version}/{name}-archive-check/run';p=run/'capture'
 read=lambda f:json.loads(f.read_text())
 s=read(run/'server.json');m=read(p/'native.json');r=read(p/'paired/renderer/result.json')
 n=list(csv.DictReader((p/'native.csv').open()));rs=[x['receipt'] for x in json_rows(p/'trace.jsonl')]
 begin=min(int(x['physics_acquisition_begin_ns']) for x in rs);end=max(int(x['physics_acquisition_end_ns']) for x in rs)
 fault=next((x for x in n if int(x['protection'])),None)
 normal=sum(bool(x['original_actual']['native']['normal']) for x in rs)
 protection=sum(bool(int(x['original_actual']['native']['protection_since_ns'])) for x in rs)
 quant=lambda values:dict(median=statistics.median(values),maximum=max(values)) if values else None
 live=[x for x in s['resources'] if begin<=x['wall_ns']<=end]
 thermal=[]
 for x in live:
  if 'host_telemetry' not in x:continue
  h=x['host_telemetry'];temps=[v/1000 for k,v in h.items() if 'hwmon' in k]
  freqs={k.split('/')[5]:v for k,v in h.items() if 'scaling_cur_freq' in k}
  thermal.append(dict(after_initial_seconds=(x['wall_ns']-m['initial'])/1e9,max_cpu_c=max(temps) if temps else None,
      frequency_khz=freqs,throttle_counts={k.split('/')[-1]:v for k,v in h.items() if 'throttle' in k}))
 row=dict(series=version,original_verdict=read(bundle/'audit.json'),intervals=len(rs),model_seconds=len(rs)*.005,
  wall_span_seconds=(end-begin)/1e9,normal=normal,protection=protection,init=len(rs)-normal-protection,
  first_fault=m['first_fault'],fault_after_initial_ms=(int(fault['now'])-m['initial'])/1e6 if fault else None,
  raw_frames=len(r['raw']),inferences=len(r['inference']),
  overlapping_inferences=sum(begin<=x['begin_ns']<=end for x in r['inference']),
  recorder_peak=r['recorder']['peak_queue_frames'],recorder_overflow=r['recorder']['overflow'],recorder_errors=r['recorder']['errors'],
  write_ms=quant([(x['write_end_ns']-x['write_begin_ns'])/1e6 for x in r['raw']]),
  scene_to_result_ms=quant([(x['end_ns']-x['original_acquisition_ns'])/1e6 for x in r['inference']]),
  physics_ms=quant([(int(x['physics_acquisition_end_ns'])-int(x['wall_applied_ns']))/1e6 for x in rs]),
  thermal=thermal,shutdown={k:dict(exit=v['server_exit'],forced=v.get('forced_stop',False)) for k,v in s['shutdown'].items()},
  replay=read(bundle/'replay.json'),archive=read(bundle/'archive-validation.json'),future_exclusion=read(bundle/'future-exclusion.json')['count'])
 cases.append(row)
result=dict(scope='five prospective failed experiments; observations, not replacement acceptance',cases=cases,
 accepted_perception_results=0,holdout_access=False,conditional_300s='NOT_RUN',
 fresh_raw_frames=sum(x['raw_frames'] for x in cases),latest_future_exclusion=cases[-1]['future_exclusion'])
(Path(__file__).parent/'observations.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps([{k:v for k,v in c.items() if k in ['series','intervals','normal','protection','init','fault_after_initial_ms','raw_frames','inferences','overlapping_inferences','recorder_overflow','future_exclusion']} for c in cases],indent=2))
