#!/usr/bin/env python3
"""Audit sealed failed trial with its frozen readers and original raw inputs."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tarfile


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args()
    bundle=Path(__file__).resolve().parent;work=a.work.resolve();work.mkdir(parents=True,exist_ok=False)
    seal=json.loads((bundle/'evidence-manifest.json').read_text())
    for name,item in seal['files'].items():
        path=bundle/name;assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],name
    source,frozen=module('source_check',bundle/'check-evidence.py').extract(bundle,work)
    run=work/'server-timing-01';shutil.copytree(bundle/'server-timing-01',run)
    server=json.loads((run/'server.json').read_text())
    assert server['freeze_sha256']==sha(bundle/'sources.json')
    assert server['server_timing_build_sha256']==sha(bundle/'build-02/manifest.json')
    assert server['server_exit']==130 and not server.get('forced_stop')
    assert server['original_ini_sha256']==server['restored_ini_sha256']
    raw=json.loads((bundle/'raw-manifest.json').read_text());path=bundle/raw['archive']
    assert path.stat().st_size==raw['bytes'] and sha(path)==raw['sha256'],'hydrate raw with Git LFS'
    with tarfile.open(path) as tar:
        members=tar.getmembers();assert len(members)==len(raw['members']) and {m.name for m in members}==set(raw['members'])
        for member in members:
            assert member.isfile() and Path(member.name).name==member.name
            data=tar.extractfile(member).read();item=raw['members'][member.name]
            assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
            (run/'capture'/member.name).write_bytes(data)
    sys.path[:0]=[str(source),str(source/'tests/integration/perception')]
    timing=module('frozen_timing',source/'tests/integration/perception/audit_server_timing_v1.py')
    shadow=module('frozen_shadow',source/'tests/integration/perception/audit_control_shadow_v1.py')
    expected_timing=json.loads((bundle/'server-timing-01/timing-audit.json').read_text())
    expected_shadow=json.loads((bundle/'server-timing-01/audit.json').read_text())
    assert timing.audit(run)==expected_timing and shadow.audit(run)==expected_shadow
    assert json.loads((bundle/'live-replay/replay.json').read_text())['startup']==json.loads((run/'capture/native-startup.json').read_text())
    rejected=[]
    def reject(name,path,bad,check):
        original=path.read_bytes();path.write_bytes(bad)
        try:
            try:check(run)
            except (ValueError,KeyError,AssertionError):rejected.append(name)
            else:raise AssertionError('mutation accepted: '+name)
        finally:path.write_bytes(original)
    path=run/'server.log';text=path.read_text();lines=text.splitlines()
    summaries=[i for i,line in enumerate(lines) if line.startswith(timing.END)]
    index=next(i for i,line in enumerate(lines) if line.startswith(timing.PREFIX) and json.loads(line[len(timing.PREFIX):])['cpu_begin']>0)
    reject('missing-journal-end',path,'\n'.join(line for i,line in enumerate(lines) if i!=summaries[0]).encode(),timing.audit)
    for field,value in (('overflow',1),('rows',0)):
        bad=lines.copy();row=json.loads(bad[summaries[0]][len(timing.END):]);row[field]=value;bad[summaries[0]]=timing.END+json.dumps(row)
        reject('journal-'+field,path,'\n'.join(bad).encode(),timing.audit)
    bad=lines.copy();bad.insert(index,bad[index]);reject('duplicate-row',path,'\n'.join(bad).encode(),timing.audit)
    for field,value in (('end',0),('cpu_end',0),('stage','unknown'),('begin',True)):
        bad=lines.copy();row=json.loads(bad[index][len(timing.PREFIX):]);row[field]=value;bad[index]=timing.PREFIX+json.dumps(row)
        reject('timing-'+field,path,'\n'.join(bad).encode(),timing.audit)
    path=run/'capture/sensors.json';sensor=json.loads(path.read_text());bad=copy.deepcopy(sensor);bad['raw']=[]
    reject('omitted-raw',path,json.dumps(bad).encode(),shadow.audit)
    bad=copy.deepcopy(sensor);wire=bytearray.fromhex(bad['ipc'][0]['packet_hex']);wire[28]^=1;bad['ipc'][0]['packet_hex']=wire.hex()
    reject('wire-reserved',path,json.dumps(bad).encode(),shadow.audit)
    path=run/'capture'/next(iter(raw['members']));bad=bytearray(path.read_bytes());bad[-1]^=1
    reject('raw-content',path,bytes(bad),shadow.audit)
    assert timing.audit(run)==expected_timing and shadow.audit(run)==expected_shadow
    result=dict(status='PASS',exact_timing_audit=True,exact_shadow_audit=True,rejected_mutations=rejected,
                scope='retained trial integrity and stage attribution; driving remains failed',driving_acceptance=False)
    (work/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
