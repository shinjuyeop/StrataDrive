#!/usr/bin/env python3
"""One separately owned renderer process, bounded lifetime and exact restoration."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import time
import traceback

from run_carla_control_shadow_v1 import sha, verify


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('engine','source','python','freeze','output','original'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='m10-render-replay-server-v1', status='FAIL', attempts=1,
                  scope='renderer-only retained replay; no concurrent physics or live inference',
                  started_utc=datetime.now(timezone.utc).isoformat())
    ini = a.source/'Unreal/CarlaUE4/Saved/Config/Linux/GameUserSettings.ini'
    original = ini.read_bytes(); report['original_ini_sha256'] = hashlib.sha256(original).hexdigest()
    proc = None
    try:
        report['freeze_sha256'] = verify(a.freeze)
        manifest = json.loads(a.freeze.read_text())
        for base in ('/d','/tmp'):
            usage = os.statvfs(base)
            free = usage.f_bavail * usage.f_frsize
            report.setdefault('preflight_free_bytes', {})[base] = free
            if free < 256 * 1024 * 1024:
                raise ValueError('insufficient bounded diagnostic storage: '+base)
        guards = []
        try:
            for port in (2300,2301,2302):
                sock = socket.socket(); guards.append(sock); sock.bind(('127.0.0.1',port))
        finally:
            for sock in guards: sock.close()
        root = Path(__file__).resolve().parents[3]
        baseline = json.loads((root/'docs/test-plan/evidence/m10_fence_compare_v1/build-02/manifest.json').read_text())
        for name, item in baseline['installed'].items():
            if manifest['external'].get(item['path']) != item['original_sha256'] or sha(item['path']) != item['original_sha256']:
                raise ValueError('original runtime identity: '+name)
        if baseline['installed']['executable']['path'] != str((a.engine/'Engine/Binaries/Linux/UE4Editor').resolve()):
            raise ValueError('renderer executable path')
        if baseline['installed']['module']['path'] != str((a.source/'Unreal/CarlaUE4/Plugins/Carla/Binaries/Linux/libUE4Editor-Carla.so').resolve()):
            raise ValueError('renderer module path')
        command = [str(a.engine/'Engine/Binaries/Linux/UE4Editor'), str(a.source/'Unreal/CarlaUE4/CarlaUE4.uproject'),
            '/Game/Carla/Maps/Town03_Opt', '-game', '-FixedSeed', '-RenderOffScreen', '-nosound', '-unattended',
            '-nosplash', '-carla-server', '-carla-rpc-port=2300', '-quality-level=Epic',
            '-ExecCmds=r.SceneRenderTargetResizeMethod 2,r.SceneRenderTargetResizeMethodForceOverride 1',
            '-ini:EditorSettings:[/Script/UnrealEd.CrashReportsPrivacySettings]:bSendUnattendedBugReports=False',
            '-ini:Engine:[CrashReportClient]:bAgreeToCrashUpload=False,[CrashReportClient]:bImplicitSend=False',
            '-log', '-stdout', '-FullStdOutLogOutput']
        client = [str(a.python), str(Path(__file__).with_name('carla_render_replay_v1.py')), '--port','2300',
                  '--original',str(a.original),'--output',str(a.output/'capture')]
        report.update(argv=command, client_argv=client)
        env = dict(os.environ, OMP_WAIT_POLICY='PASSIVE')
        env.pop('STRATADRIVE_M7_OWNER_KEY', None)
        if env.get('LD_PRELOAD'): raise ValueError('unexpected preload')
        def no_core(): resource.setrlimit(resource.RLIMIT_CORE, (0,0))
        with (a.output/'server.log').open('w') as log:
            proc = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True, preexec_fn=no_core)
        report['pid'] = proc.pid
        end = time.monotonic()+180
        while time.monotonic() < end:
            if proc.poll() is not None: raise ValueError('renderer exited before readiness')
            try:
                with socket.create_connection(('127.0.0.1',2300), timeout=.5): break
            except OSError: time.sleep(.2)
        else: raise TimeoutError('renderer RPC readiness')
        code = '''import carla,time,sys
c=carla.Client('127.0.0.1',2300);c.set_timeout(2);end=time.monotonic()+float(sys.argv[1])
while time.monotonic()<end:
 try:
  w=c.get_world()
  if w.get_snapshot().frame>0: print(w.id,flush=True);sys.exit(0)
 except RuntimeError: pass
 time.sleep(.2)
sys.exit(1)
'''
        with (a.output/'readiness.log').open('w') as log:
            subprocess.run([str(a.python),'-c',code,str(max(1,end-time.monotonic()))], env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=185)
        with (a.output/'client.log').open('w') as log:
            completed = subprocess.run(client, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        report['client_exit'] = completed.returncode
        if completed.returncode: raise ValueError('renderer diagnostic failed; original failure retained')
        if verify(a.freeze) != report['freeze_sha256']: raise ValueError('frozen sources/runtime changed')
        report['status'] = 'EXECUTED_REQUIRES_AUDIT'
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        if proc:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGINT)
                try: proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    report['forced_stop'] = True; os.killpg(proc.pid,signal.SIGKILL); proc.wait(timeout=10)
            report['server_exit'] = proc.returncode
            if proc.returncode != 130 or report.get('forced_stop'): report['status'] = 'FAIL'
        ini.write_bytes(original); report['restored_ini_sha256'] = sha(ini)
        (a.output/'server.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','error') if k in report}))
    return 0 if report['status'] == 'EXECUTED_REQUIRES_AUDIT' else 1


if __name__ == '__main__': raise SystemExit(main())
