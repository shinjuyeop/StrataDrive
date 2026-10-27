from pathlib import Path
import gzip,hashlib,json,shutil,socket,subprocess
root=Path('/d/shin/StrataDrive/docs/test-plan/evidence/m7_carla_integrated')
runtime=Path('/d/shin/stratadrive-tools/m7-source/m7-integrated')
records=[]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def archive(source,dest):
 dest.parent.mkdir(parents=True,exist_ok=True)
 with source.open('rb')as f,dest.open('wb')as out:
  with gzip.GzipFile(filename='',mode='wb',fileobj=out,mtime=0,compresslevel=6)as z:shutil.copyfileobj(f,z)
 h=hashlib.sha256()
 with gzip.open(dest,'rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 digest=sha(source)
 assert h.hexdigest()==digest
 records.append(dict(source=str(source),raw_sha256=digest,archive=str(dest.relative_to(root)),archive_sha256=sha(dest)))
for source in root.rglob('trace.jsonl'):
 archive(source,source.with_suffix('.jsonl.gz'));source.unlink()
for source in runtime.rglob('*'):
 if source.is_file() and source.suffix=='.log':archive(source,root/'runtime-logs'/source.relative_to(runtime).with_suffix('.log.gz'))
for directory in runtime.rglob('probe'):
 if not directory.is_dir():continue
 for source in directory.iterdir():
  if source.suffix not in ('.py','.txt'):continue
  digest=sha(source);dest=root/'executed-sources'/digest/source.name
  dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
for name in ('archive.py',):shutil.copy2(runtime/name,root/name)
(root/'archive-manifest.json').write_text(json.dumps(records,indent=2)+'\n')
reports=[]
for path in sorted(root.rglob('server-*.json')):
 r=json.loads(path.read_text());relative=path.relative_to(root);run=path.parent/path.name.removeprefix('server-').removesuffix('.json')
 p=run/'result.json';result=json.loads(p.read_text())if p.exists()else{}
 reports.append(dict(run=str(run.relative_to(root)),server_report=str(relative),status=r['status'],probe_status=result.get('status','NOT_RUN'),
  receipts=(len(result['receipts']) if isinstance(result.get('receipts'),list) else result.get('receipts',0)),settlements=result.get('settlements',0),normal_intervals=result.get('normal_intervals',0),
  server_exit=r.get('server_exit'),forced_stop=r.get('forced_stop'),
  shutdown_seconds=((r['exit_observed_monotonic_ns']-r['stop_requested_monotonic_ns'])/1e9 if 'stop_requested_monotonic_ns'in r else None)))
ports={}
for port in (2200,2201,2202):
 s=socket.socket()
 try:s.bind(('127.0.0.1',port));ports[str(port)]='FREE'
 except OSError as e:ports[str(port)]=str(e)
 finally:s.close()
processes=[line for line in subprocess.check_output(['ps','-eo','pid,comm'],text=True).splitlines() if any(x in line for x in ('UE4Editor','CrashReportClient'))]
(root/'run-summary.json').write_text(json.dumps(dict(runs=reports,ports=ports,remaining_server_processes=processes),indent=2)+'\n')
print('runs',len(reports),'PASS launchers',sum(r['status']=='COMPLETE_ISOLATED_RUN'for r in reports),'forced',sum(bool(r['forced_stop'])for r in reports),'archives',len(records))
