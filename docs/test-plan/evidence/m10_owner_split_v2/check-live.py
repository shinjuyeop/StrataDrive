#!/usr/bin/env python3
"""Audit the original run with frozen readers and rebuildable native replay."""
import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    p.add_argument('--replay-binary',type=Path,required=True);a=p.parse_args()
    bundle=Path(__file__).resolve().parent;work=a.work.resolve();work.mkdir(parents=True,exist_ok=False)
    seal=json.loads((bundle/'evidence-manifest.json').read_text())
    for name,item in seal['files'].items():
        path=bundle/name;assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],name
    source,frozen=module('source_check',bundle/'check-evidence.py').extract(bundle,work)
    case=json.loads((bundle/'case.json').read_text());run=work/case['run'];run.mkdir()
    manifest=json.loads((bundle/'run-manifest.json').read_text());archive=bundle/manifest['archive']
    assert sha(archive)==manifest['sha256'] and archive.stat().st_size==manifest['bytes']
    with tarfile.open(archive,'r:gz') as tar:
        members=tar.getmembers();assert len(members)==len(manifest['members']) and {m.name for m in members}==set(manifest['members'])
        for member in members:
            path=Path(member.name);assert member.isfile() and not path.is_absolute() and '..' not in path.parts
            data=tar.extractfile(member).read();item=manifest['members'][member.name]
            assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
            target=run/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    sys.path[:0]=[str(source),str(source/'tests/integration/perception'),str(source/'tests/integration/carla')]
    shadow=module('frozen_shadow',source/'tests/integration/perception/audit_control_shadow_v1.py')
    physical=module('frozen_physical',source/'tests/integration/carla/audit_m7_wall_carla.py')
    capture=run/'capture';sensors=json.loads((capture/'sensors.json').read_text())
    assert not sensors['camera'] and not sensors['raw'] and not sensors['model_calls']
    assert shadow.audit(run)==json.loads((bundle/'shadow-audit.json').read_text())

    def lifecycle():
        server=json.loads((run/'server.json').read_text())
        assert server['freeze_sha256']==sha(bundle/'sources.json')==case['freeze_sha256']
        assert server['server_exit']==130 and not server.get('forced_stop') and server['attempts']==1
        assert server['original_ini_sha256']==server['restored_ini_sha256']
        assert server['execution_profile']=='owner5ms' and server['camera_condition']=='absent'
        assert all(x in server['argv'] for x in ('-StrataM7Wall5ms','-nullrhi','-norenderthread'))
        assert '-StrataM7SensorFrame5' not in server['argv'] and '--cameras' not in server['client_argv']
    lifecycle()
    original=json.loads((capture/'result.json').read_text())
    if case['overall_attempt_index']==1:
        assert original['status']=='FAIL' and original['completed_physics']==1
        assert 'shadow observer/recording error' in original['error']
        assert sensors['world_observation']['clock']['failed'] and sensors['errors']
        assert not json.loads((capture/'native.json').read_text())['first_fault']
    else:
        assert physical.audit(capture)==json.loads((bundle/'physical-audit.json').read_text())
        assert original['status']=='EXECUTED_REQUIRES_AUDIT' and original['completed_physics']==400
    prior=json.loads((bundle/'future-exclusion.json').read_text())
    exclusion=bundle/prior['prior'];assert sha(exclusion)==prior['prior_sha256']
    assert prior['count']==json.loads(exclusion.read_text())['count']==8978
    assert prior['new_raw_packets']==0 and prior['holdout_access'] is False
    baseline=json.loads((source/'docs/test-plan/evidence/m10_fence_compare_v1/build-02/manifest.json').read_text())
    restored=json.loads((bundle/'restoration.json').read_text())
    for name,item in baseline['installed'].items():
        assert restored[name]['sha256']==item['original_sha256']==frozen['external'][item['path']]
        assert restored[name]['unchanged']
    env=dict(os.environ,PYTHONPATH=str(source)+':'+str(source/'tests/integration/perception'),PYTHONDONTWRITEBYTECODE='1')
    def run_command(name,command):
        with (work/(name+'.log')).open('w') as log:
            subprocess.run(list(map(str,command)),cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    run_command('fresh-replay',[sys.executable,source/'tests/integration/perception/replay_wall_startup_v1.py',
        '--capture',capture,'--binary',a.replay_binary.resolve(),'--scenario',source/'tests/integration/carla/scenarios/m7_integrated_v1.txt',
        '--output',work/'fresh-replay','--require-exact'])
    for name in ('input.txt','replay.csv','replay.json'):
        assert (work/'fresh-replay'/name).read_bytes()==(bundle/'replay'/name).read_bytes(),name
    assert json.loads((work/'fresh-replay/replay.json').read_text())['startup']==json.loads((capture/'native-startup.json').read_text())
    rejected=[]
    if case['overall_attempt_index']==2:
        def accepted():assert physical.audit(capture)['status']=='PASS_CASE_ONLY'
        def reject(name,path,bad,check=accepted):
            original_bytes=path.read_bytes();path.write_bytes(bad)
            try:
                try:check()
                except (ValueError,KeyError,AssertionError):rejected.append(name)
                else:raise AssertionError('mutation accepted: '+name)
            finally:path.write_bytes(original_bytes)
        path=capture/'result.json'
        for name,field,value in (('model-step','model_step_ns',10_000_000),('hv-budget','hv_dependency_ns',50_000_000),
                                 ('execution-profile','execution_profile','shadow10ms'),('failed-run','status','FAIL')):
            bad=copy.deepcopy(original);bad[field]=value;reject(name,path,json.dumps(bad).encode())
        bad=copy.deepcopy(original);bad['writer_checks']['tick_denied']=False
        reject('writer-denial',path,json.dumps(bad).encode())
        path=capture/'sensors.json'
        bad=copy.deepcopy(sensors);bad['state'][0]['source_ns']+=5_000_000
        reject('state-source',path,json.dumps(bad).encode())
        bad=copy.deepcopy(sensors);bad['preparation_calls'].pop();reject('preparation-count',path,json.dumps(bad).encode())
        bad=copy.deepcopy(sensors);bad['camera']=[{}];reject('hidden-camera',path,json.dumps(bad).encode())
        path=capture/'native.json';bad=json.loads(path.read_text());bad['first_fault']='injected fault'
        reject('native-fault',path,json.dumps(bad).encode())
        path=capture/'native.csv';lines=path.read_text().splitlines();index=next(i for i,line in enumerate(lines[1:],1) if line.split(',')[4]=='1')
        values=lines[index].split(',');values[2]=str(int(values[2])+1);lines[index]=','.join(values)
        def native_identity():assert list(csv.DictReader((capture/'native.csv').open()))==list(csv.DictReader((bundle/'replay/replay.csv').open()))
        reject('renewed-native-wheel-source',path,('\n'.join(lines)+'\n').encode(),native_identity)
        path=capture/'trace.jsonl';lines=path.read_text().splitlines()
        reject('missing-receipt',path,('\n'.join(lines[1:])+'\n').encode())
        bad=json.loads(lines[0]);bad['receipt']['physics_acquisition_begin_ns']=str(int(bad['receipt']['physics_acquisition_begin_ns'])+1)
        altered=[json.dumps(bad),*lines[1:]];reject('renewed-physics-source',path,('\n'.join(altered)+'\n').encode())
        path=run/'server.json';bad=json.loads(path.read_text());bad['server_exit']=-11
        reject('server-lifecycle',path,json.dumps(bad).encode(),lifecycle)
        component=json.loads((bundle/'scene-source.json').read_text())
        assert component['parent_archive_sha256']==sha(bundle/'sources.tar.gz')
        for name,item in component['files'].items():
            path=bundle/'scene-source'/name
            assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes']
            assert not (source/name).exists(),'component source must be separate from prelive freeze'
            (source/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,source/name)
        run_command('scene-tests',[sys.executable,'-m','unittest','test_scene_mailbox_v1','-v'])
        run_command('scene-replay',[sys.executable,source/'tests/integration/perception/replay_scene_mailbox_v1.py',capture,'--output',work/'scene-replay.json'])
        assert json.loads((work/'scene-replay.json').read_text())==json.loads((bundle/'scene-replay.json').read_text())
        assert physical.audit(capture)==json.loads((bundle/'physical-audit.json').read_text())
    validation=dict(status='PASS',run_verdict=case['verdict'],exact_native_replay=True,
                    replay_binary_sha256=sha(a.replay_binary),exact_shadow_audit=True,
                    exact_physical_audit=case['overall_attempt_index']==2,
                    scene_component_tests=10 if case['overall_attempt_index']==2 else 0,
                    rejected_mutations=rejected,continuous_driving_acceptance=False,live_renderer_test=False)
    (work/'validation.json').write_text(json.dumps(validation,indent=2)+'\n');print(json.dumps(validation,indent=2))


if __name__=='__main__':main()
