#!/usr/bin/env python3
"""Finite pre-proposal failure cohort using the actual native adapter binary."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'diagnostics'))
from audit_bootstrap_incidents import audit
from front_run import config
from run import sanitizer_errors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path);parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--fixed-layout',action='store_true',help='process-local TSan ASLR workaround')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);binary=args.binary.resolve()
    rows=[]
    def call(case,env,role,*extra):
        command=[str(binary),role,str(case),*extra]
        if role in ('central','front','rear'):
            command=['unshare','-Urnm',sys.executable,str(HERE/'run.py'),'--node',*command]
        if args.fixed_layout:command=['setarch','x86_64','-R',*command]
        with (case/(role+'.log')).open('w') as log:
            try:code=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=15).returncode
            except subprocess.TimeoutExpired:code=124
        rows.append({'case':case.name,'role':role,'command':command,'exit':code})
        (out/'runs.json').write_text(json.dumps(rows,indent=2)+'\n')
        assert not sanitizer_errors((case/(role+'.log')).read_text(errors='replace')),(case.name,role,'sanitizer diagnostic')
        return code
    manifest={'binary':str(binary),'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'watchdog_s':15,'fixed_layout':args.fixed_layout,'scope':'pre-proposal failure; no live timing acceptance'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    cases=('normal','epoch-conflict','journal-conflict','missing-spool','journal-open','journal-open-front','journal-open-rear')
    for name in cases:
        case=out/name;case.mkdir();(case/'sil-io').mkdir()
        persistent=Path(tempfile.mkdtemp(prefix='stratadrive-boot-native-',dir='/var/tmp'))
        env=dict(os.environ,LD_LIBRARY_PATH=str(binary.parents[4]/'install/lib'),
                 ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',TSAN_OPTIONS='halt_on_error=1:exitcode=66',
                 STRATADRIVE_BOOTSTRAP_STORE_ROOT=str(persistent/'incidents'),STRATADRIVE_NATIVE_DIAGNOSTICS='1',
                 STRATADRIVE_THREE_ECU='1',STRATADRIVE_DIAGNOSTIC_STORE_ROOT=str(persistent/'diagnostics'))
        (case/'storage.json').write_text(json.dumps({'path':str(persistent),'retained':True})+'\n')
        if name!='missing-spool':assert call(case,env,'bootstrap-log-init')==0
        if name=='epoch-conflict':(case/'epochs').mkdir()
        if name=='journal-conflict':(persistent/'diagnostics').write_text('blocked path\n')
        code=call(case,env,'bootstrap')
        assert code==(0 if name=='normal' or name.startswith('journal-open') else 1),(name,code)
        if name=='missing-spool':
            assert not (case/'epochs').exists()
            continue
        if name.startswith('journal-open'):
            role='front' if name.endswith('front') else 'rear' if name.endswith('rear') else 'central'
            store=persistent/'diagnostics'/role/('merged' if role=='central' else 'context')
            store.rename(store.with_name(store.name+'-original'));store.write_text('blocked open\n')
            cfg=config(role,1,True);cfg.update(unicast='127.0.0.1',netmask='255.0.0.0')
            config_path=case/(role+'.config.json');config_path.write_text(json.dumps(cfg))
            env.update(VSOMEIP_CONFIGURATION=str(config_path),VSOMEIP_APPLICATION_NAME=role)
            assert call(case,env,role,'normal','1')==1
            summary=json.loads((case/(role+'-1.json')).read_text())
            assert summary['epoch']==0 and summary['release_ack_mask']==0 and summary['armed_ns']==0
            assert not (case/(role+'-1.started')).exists()
        result=audit(persistent/'incidents')
        expected=(2,1) if name.startswith('journal-open') else {'normal':(2,0),'epoch-conflict':(0,1),'journal-conflict':(1,1)}[name]
        assert (result['succeeded'],result['failed'])==expected and result['interrupted']==0,(name,result)
        if name=='epoch-conflict':
            # Explicit fresh workspace, same spool: no automatic deletion/reset
            # of the failed EpochStore or of its original incident.
            before={str(p.relative_to(persistent/'incidents')):p.read_bytes() for p in (persistent/'incidents').rglob('*') if p.is_file()}
            retry=out/'epoch-explicit-retry';retry.mkdir();(retry/'sil-io').mkdir()
            assert call(retry,env,'bootstrap')==0
            for path,data in before.items():assert (persistent/'incidents'/path).read_bytes()==data
            result=audit(persistent/'incidents');assert result['succeeded']==2 and result['failed']==1
        shutil.copytree(persistent/'incidents',case/'incidents')
        (case/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'pass':True,'cases':len(cases),'explicit_retry':1,'processes':len(rows)}))
    return 0


if __name__=='__main__':sys.exit(main())
