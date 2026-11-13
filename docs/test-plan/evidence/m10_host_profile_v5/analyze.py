import argparse,csv,gzip,json,statistics,sys
from collections import defaultdict
from pathlib import Path
root=Path(__file__).resolve().parents[4];sys.path.insert(0,str(root/'tests/integration/carla'))
from evidence_io import json_rows
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--case',required=True);p.add_argument('--output',type=Path,required=True)
options=p.parse_args();name=options.case;run=options.run
read=lambda p:json.loads(p.read_text())
s=read(run/'server.json');m=read(run/'capture/native.json');r=read(run/'capture/paired/renderer/result.json')
receipts=[x['receipt'] for x in json_rows(run/'capture/trace.jsonl')]
start=m['initial'];end=max(int(x['physics_acquisition_end_ns']) for x in receipts)
normal=[x for x in receipts if x['original_actual']['native']['normal']]
protected=[x for x in receipts if int(x['original_actual']['native']['protection_since_ns'])]
n=list(csv.DictReader((run/'capture/native.csv').open()));fault=next((int(x['now']) for x in n if int(x['protection'])),end);has_fault=any(int(x['protection']) for x in n)
samples=[json.loads(x) for x in gzip.open(run/'host-profile.jsonl.gz','rt').read().splitlines()]
phases={'preparation':(samples[0]['wall_ns'],start),'before_fault':(start,fault),'physical_all':(start,end),'protected':(fault,end)}
if normal:phases['normal']=(min(int(x['physics_acquisition_begin_ns']) for x in normal),max(int(x['physics_acquisition_end_ns']) for x in normal))
monitor=read(run/'host-profile-summary.json');ticks_per_second=monitor['ticks_per_second']
rolemap={v:k for k,v in s['pids'].items()};result={}
def role(p):
 if p['pid'] in rolemap:return rolemap[p['pid']]
 if any(t['comm'].startswith('m10-') for t in p['threads']):return 'image_pipeline'
 if p['comm'].startswith('m7_'):return 'native'
 return 'observer_setup'
def quant(values):return dict(median=statistics.median(values),p95=(statistics.quantiles(values,n=100,method='inclusive')[94] if len(values)>1 else values[0]),max=max(values)) if values else None
for phase,(lo,hi) in phases.items():
 points=[x for x in samples if lo<=x['wall_ns']<=hi];seconds=max(0,(hi-lo)/1e9);cpu=defaultdict(float);thread=defaultdict(float)
 for a,b in zip(points,points[1:]):
  old={(p['pid'],p['start_ticks']):p for p in a['processes']}
  for p in b['processes']:
   prev=old.get((p['pid'],p['start_ticks']))
   if not prev:continue
   group=role(p);cpu[group]+=max(0,p['user_ticks']+p['system_ticks']-prev['user_ticks']-prev['system_ticks'])/ticks_per_second
   tids={(t['tid'],t['start_ticks']):t for t in prev['threads']}
   for t in p['threads']:
    last=tids.get((t['tid'],t['start_ticks']))
    if last:thread[group+' / '+t['comm']]+=max(0,t['schedstat'][0]-last['schedstat'][0])/1e9
 temperatures=[max(v/1000 for k,v in x['host'].items() if '/temp' in k) for x in points]
 gpu=[x['gpu'].get('gpu_percent') for x in points if 'gpu_percent' in x['gpu']]
 delta={}
 if len(points)>1:
  delta={k.rsplit('/',1)[-1]:v-points[0]['host'].get(k,v) for k,v in points[-1]['host'].items() if 'throttle' in k}
 result[phase]=dict(seconds=seconds,samples=len(points),cpu_seconds=dict(cpu),average_cores={k:v/seconds for k,v in cpu.items()} if seconds else {},hottest_c=max(temperatures,default=None),gpu_percent=quant(gpu),thermal_delta=delta,top_threads=sorted(thread.items(),key=lambda x:x[1],reverse=True)[:15])
summary=dict(case=name,normal_intervals=len(normal),protection_intervals=len(protected),init_intervals=len(receipts)-len(normal)-len(protected),normal_model_seconds=.005*len(normal),physical_intervals=len(receipts),fault_after_initial_ms=(fault-start)/1e6 if has_fault else None,first_fault=m['first_fault'],raw=len(r['raw']),inferences=len(r['inference']),overflow=r['recorder']['overflow'],phases=result,scene_result_ms=quant([(x['end_ns']-x['original_acquisition_ns'])/1e6 for x in r['inference']]),stages={key:quant([x[key]/1e6 for x in r['inference']]) for key in ['preprocess_ns','inference_ns','postprocess_ns','thread_cpu_ns']},recorder_stages={key:quant([x['profile'][key]/1e6 for x in r['raw'] if 'profile' in x]) for key in ['compression_ns','compression_cpu_ns','hash_conversion_ns','hash_conversion_cpu_ns']},host_pipeline=r.get('host_pipeline'),monitor=monitor,shutdown=s['shutdown'])
inferences=r['inference'];physical_seconds=(end-start)/1e9
summary['latency_components_ms']={
 'source_to_callback':quant([(x['callback_ns']-x['original_acquisition_ns'])/1e6 for x in inferences]),
 'callback_to_start':quant([(x['begin_ns']-x['callback_ns'])/1e6 for x in inferences]),
 'compute':quant([(x['end_ns']-x['begin_ns'])/1e6 for x in inferences])}
summary['over_100ms']=sum(x['end_ns']-x['original_acquisition_ns']>100000000 for x in inferences)
summary['camera_callbacks_during_physical']=sum(start<=x['received_wall_ns']<=end for x in r['raw'])
summary['camera_hz_during_physical']=summary['camera_callbacks_during_physical']/physical_seconds
summary['renderer_ticks_during_physical']=sum(start<=x['tick_end_ns']<=end for x in r['ticks'])
summary['renderer_hz_during_physical']=summary['renderer_ticks_during_physical']/physical_seconds
summary['live_stored_bytes']=r['recorder']['stored_bytes']
options.output.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('phases','shutdown')},indent=2))
for phase,row in result.items():print(phase,json.dumps(row))
