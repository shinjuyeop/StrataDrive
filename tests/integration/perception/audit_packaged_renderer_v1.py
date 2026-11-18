"""Original physical gates plus explicit stock-renderer/pre-START boundaries."""
import argparse
import json
from pathlib import Path
from audit_visual_tags_v1 import audit as visual_audit
from packaged_renderer_v1 import MAP, XODR, VERSION
from owner_code_prefetch_v1 import MAX_BYTES, MAX_SECONDS


def validate(server,capture,renderer):
    info=server['packaged_renderer'];prepared=info['preparation'];argv=server['argv']['renderer']
    if (argv[0]!=info['executable'] or Path(argv[0]).name!='CarlaUE4-Linux-Shipping'
            or info['editor_idle_wait'] is not False or info['viewport_fps_cap'] is not None
            or any(s.startswith(('-Strata','-ExecCmds=','-ini:')) for s in argv)
            or info['original_ini_sha256']!=info['restored_ini_sha256']):
        raise ValueError('explicit stock renderer and restored configuration')
    if (prepared['version']!=VERSION or prepared['map']!=MAP or prepared['xodr_sha256']!=XODR
            or prepared['parked'] is not True or any(prepared['empty'].values())
            or set(prepared['empty'])!={'vehicle.*','walker.*','sensor.*'}
            or not 0<=prepared['completed_ns']-server['process_started_ns']['renderer']<180_000_000_000):
        raise ValueError('original readiness bound and exact target map before capture')
    stop=server['shutdown']['renderer'];unpark=stop.get('unpark',{})
    if (stop['server_exit']!=130 or stop.get('forced_stop') or stop.get('unpark_error')
            or not renderer['quiescent_cleanup']['end_wall_ns']<=server['client_completed_ns']<=stop['begin_wall_ns']
            or not stop['begin_wall_ns']<=unpark.get('completed_ns',0)<=stop['end_wall_ns']
            or unpark.get('synchronous_after') is not False
            or not 0<=stop['end_wall_ns']-stop['begin_wall_ns']<=30_000_000_000):
        raise ValueError('release renderer wait only after recorded capture; normal bounded exit')
    pre=capture['owner_code_prefetch'];start=capture['native_initial']['initial']
    if (server.get('prefetch_owner_code') is not True or pre['status']!='PREPARED_BEFORE_NATIVE_START'
            or pre['control_writes']!=0 or pre['limit_bytes']!=MAX_BYTES or pre['limit_seconds']!=MAX_SECONDS
            or not 0<=pre['begin_ns']<=pre['end_ns']<start
            or pre['end_ns']-pre['begin_ns']>=MAX_SECONDS*1_000_000_000
            or pre['read_bytes']!=sum(f['read_bytes'] for f in pre['files'])
            or not 0<pre['read_bytes']<=MAX_BYTES):
        raise ValueError('bounded read-only physical code preparation before native START')
    if pre['owner']['pid']!=server['pids']['owner']:
        raise ValueError('preparation targets this physical owner')
    return dict(renderer=info,owner_code_read_bytes=pre['read_bytes'])


def audit(run):
    result=visual_audit(run)
    read=lambda name:json.loads((run/name).read_text())
    checks=validate(read('server.json'),read('capture/result.json'),read('capture/paired/renderer/result.json'))
    result.update(status='PASS_PACKAGED_RENDERER_INTEGRITY',checks=checks,
        scope='original physical gates and explicit renderer/preparation boundary; not native perception acceptance')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as error:result=dict(status='FAIL',error=str(error).replace(str(a.run),'<run>'))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if result['status']=='PASS_PACKAGED_RENDERER_INTEGRITY' else 1)
