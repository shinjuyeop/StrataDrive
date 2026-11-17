"""Exercise actual owner and renderer model setup at100%, without CARLA/control."""
from pathlib import Path
import argparse,json,os,sys,time,traceback
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[4];S=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests/integration/perception')]
from control_shadow_capture_v1 import Capture
from carla_paired_renderer_v1 import DiagnosticInference
from endurance_host_v1 import pipeline_setup,pin
from audit_library_prefetch_v1 import validate
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(exist_ok=False,parents=True)
assert Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct').read_text().strip()=='100'
assert os.environ.get('STRATADRIVE_M10_PREFETCH_LIBRARIES')=='1'
pin('observer')
args=SimpleNamespace(output=a.output,wall_clock=1,detector=ROOT/'build/m10-resolution-v2/models/dfine-960.onnx',models=ROOT/'build/m10-resolution-v2/models.json',library=ROOT/'build/m10-source-compare-v1/native/libstrata_resize_2k_v1.so',step_ms=5,endurance_seconds=30)
profile=(ROOT/'profiles/perception-inference-libraries-host-v1.json').read_bytes();record=dict(status='FAIL',scope='actual two setup paths at100%; no CARLA, camera or control; no70% physical acceptance',begin_wall_ns=time.monotonic_ns());cap=Capture(args);inference=None
try:
 with pipeline_setup() as cpus:
  assert cpus==[6,7,14,15]
  cap.report['model_setup_cpus']=cpus;cap.prepare_model(SimpleNamespace(id=1))
 owner=cap.worker.preparation_status();assert owner['state']=='READY' and len(owner['calls'])==3
 record['owner_worker_cpus']=sorted(os.sched_getaffinity(cap.worker._thread.native_id))
 assert record['owner_worker_cpus']==[6,7,14,15]
 record['owner_preparation']=owner;record['owner_library_read']=validate(cap.report['library_prefetch'],profile,owner['started_wall_ns'])
 cap.report['observer_cpus_after_setup']=sorted(os.sched_getaffinity(0));assert cap.report['observer_cpus_after_setup']==[0,8]
 cap.stop();assert cap.report['closed'] and not cap.report['cleanup_errors']
 renderer=dict(preparation=[],errors=[])
 with pipeline_setup():
  inference=DiagnosticInference(args,1,renderer)
  assert inference.ready.wait(30),'unchanged renderer readiness deadline'
 assert not renderer['errors'],renderer['errors']
 assert len(renderer['preparation'])==3
 record['renderer_worker_cpus']=sorted(os.sched_getaffinity(inference.thread.native_id))
 assert record['renderer_worker_cpus']==[6,7,14,15]
 record['renderer_library_read']=validate(renderer['library_prefetch'],profile,renderer['preparation'][0]['begin_ns'])
 inference.stop();inference=None
 (a.output/'renderer.json').write_text(json.dumps(renderer,indent=2)+'\n')
 record.update(status='PASS_ACTUAL_MODEL_SETUP_ONLY',renderer_preparation=renderer['preparation'],control_writes=0,camera_frames=0)
except Exception:record['error']=traceback.format_exc()
finally:
 if cap.worker and not cap.report.get('closed'):cap.stop()
 if inference is not None:
  try:inference.stop()
  except Exception:record['cleanup_error']=traceback.format_exc()
 cap.tx.close();cap.rx.close();record['end_wall_ns']=time.monotonic_ns()
 (a.output/'validation.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps({k:record[k] for k in ('status','error','owner_library_read','renderer_library_read') if k in record}),flush=True)
raise SystemExit(0 if record['status']=='PASS_ACTUAL_MODEL_SETUP_ONLY' else 1)
