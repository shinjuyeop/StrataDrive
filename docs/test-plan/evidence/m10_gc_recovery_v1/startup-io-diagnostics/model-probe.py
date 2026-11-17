"""Standalone original model startup: retain failures, wait only for cleanup."""
import faulthandler,json,os,resource,sys,time,traceback
from pathlib import Path
from types import SimpleNamespace
root=Path('/d/shin/StrataDrive');sys.path[:0]=[str(root),str(root/'tests/integration/perception')]
from control_shadow_capture_v1 import Capture
from endurance_host_v1 import pipeline_setup
out=Path(sys.argv[1]);out.mkdir(exist_ok=True)
args=SimpleNamespace(output=out,wall_clock=1,detector=root/'build/m10-resolution-v2/models/dfine-960.onnx',models=root/'build/m10-resolution-v2/models.json',library=root/'build/m10-source-compare-v1/native/libstrata_resize_2k_v1.so',step_ms=5,endurance_seconds=30)
stack=(out/'python-stacks.log').open('w');faulthandler.enable(stack);faulthandler.dump_traceback_later(5,repeat=True,file=stack)
if os.environ.get('DIAGNOSTIC_LIBRARY_DIRECTORY'):
 import onnxruntime as ort
 original_preload=ort.preload_dlls
 ort.preload_dlls=lambda **kw:original_preload(directory=os.environ['DIAGNOSTIC_LIBRARY_DIRECTORY'])
if os.environ.get('DIAGNOSTIC_PREFETCH_MANIFEST'):
 from physical_ai.perception.library_prefetch_v1 import prefetch
 import control_shadow_capture_v1
 control_shadow_capture_v1.prefetch_pipeline_libraries=lambda report:prefetch(os.environ['DIAGNOSTIC_PREFETCH_MANIFEST'],root,report)
cap=Capture(args);begin=time.monotonic_ns();record=dict(begin_wall_ns=begin,host_max_perf_pct=Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct').read_text().strip(),pid=os.getpid(),scope='isolated diagnostic at restored host100%; no CARLA, no control, unchanged original preparation')
(out/'identity.json').write_text(json.dumps(record,indent=2)+'\n')
try:
 with pipeline_setup() as cpus:
  cap.report['model_setup_cpus']=cpus;cap.prepare_model(SimpleNamespace(id=1))
 record['preparation_pass']=True
except Exception:
 record.update(preparation_pass=False,error=traceback.format_exc())
finally:
 record['readiness_observed_wall_ns']=time.monotonic_ns();record['readiness']=cap.worker.preparation_status() if cap.worker else None
 if cap.worker:record['closed_after_cleanup_wait']=cap.worker.close(60)
 record['final_preparation']=cap.worker.preparation_status() if cap.worker else None
 record['end_wall_ns']=time.monotonic_ns();record['max_rss_kb']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
 record['major_faults']=resource.getrusage(resource.RUSAGE_SELF).ru_majflt
 (out/'maps.txt').write_text(Path('/proc/self/maps').read_text());(out/'result.json').write_text(json.dumps(record,indent=2)+'\n')
 (out/'perception.json').write_text(json.dumps(cap.report,indent=2)+'\n')
 (out/'backend-stages.json').write_text(json.dumps(getattr(getattr(cap,'detector',None),'stages',[]),indent=2)+'\n')
 cap.tx.close();cap.rx.close();faulthandler.cancel_dump_traceback_later()
 print(json.dumps({k:record.get(k) for k in ('preparation_pass','closed_after_cleanup_wait','major_faults','max_rss_kb')}),flush=True)
 if not record.get('closed_after_cleanup_wait',True):os._exit(2)
