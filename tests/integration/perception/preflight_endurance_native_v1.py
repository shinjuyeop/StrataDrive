"""Start/stop the actual executable with no CARLA, proving complete horizon allocation."""
import argparse
import json
from pathlib import Path
import select
import socket
import subprocess
import time


def main(a):
    a.output.mkdir(parents=True,exist_ok=False);results=[]
    for seconds in (30,300):
        root=a.output/str(seconds);root.mkdir();tx,rx=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        tx.setblocking(False);rx.setblocking(False)
        command=[str(a.binary.resolve()),str((root/'bridge').resolve()),str((root/'native').resolve()),
            str(a.scenario.resolve()),'5','30','--perception-shadow',f'{rx.fileno()}:1:2','--endurance-seconds',str(seconds)]
        with (root/'stderr.log').open('w') as log:
            process=subprocess.Popen(command,pass_fds=(rx.fileno(),),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True)
            rx.close()
            try:
                process.stdin.write('START 99 1000000000 1 1 00000000-0000-4000-8000-000000000001\n');process.stdin.flush()
                assert select.select([process.stdout],[],[],10)[0],'bounded native initialization'
                line=process.stdout.readline();assert line,'native initialization failed; see retained stderr.log'
                initial=json.loads(line)
                assert initial['model_step_ns']==5_000_000 and initial['hv_dependency_ns']==30_000_000
                process.stdin.write('STOP\n');process.stdin.flush();process.stdin.close()
                assert process.wait(timeout=10)==0
                meta=json.loads((root/'native.json').read_text())
                assert meta['diagnostic_horizon_ns']==(seconds+5)*1_000_000_000
                results.append(dict(seconds=seconds,initialized=True,scope='allocation/start/stop only; zero CARLA observations'))
            finally:
                if process.poll() is None:process.kill();process.wait()
                tx.close()
    result=dict(status='PASS',live_server=False,cases=results)
    (a.output/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('binary','scenario','output'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
