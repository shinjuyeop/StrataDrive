#!/usr/bin/env python3
"""Audit preserved failed live trial using frozen auditor and original LFS raw."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tarfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);a=parser.parse_args()
    bundle=Path(__file__).resolve().parent;work=a.work.resolve();work.mkdir(parents=True,exist_ok=False)
    source=work/'source';source.mkdir()
    frozen=json.loads((bundle/'sources.json').read_text())
    assert sha(bundle/'sources.tar.gz')==frozen['archive_sha256']
    with tarfile.open(bundle/'sources.tar.gz','r:gz') as tar:
        members=tar.getmembers();assert len(members)==len(frozen['files'])
        assert {m.name for m in members}==set(frozen['files'])
        for m in members:
            path=Path(m.name);assert m.isfile() and not path.is_absolute() and '..' not in path.parts
            data=tar.extractfile(m).read();expected=frozen['files'][m.name]
            assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256']
            dest=source/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    run=work/'run-01';shutil.copytree(bundle/'run-01',run)
    server=json.loads((run/'server.json').read_text());assert server['freeze_sha256']==sha(bundle/'sources.json')
    raw=json.loads((bundle/'raw-manifest.json').read_text());archive=bundle/raw['archive']
    assert archive.stat().st_size==raw['bytes'] and sha(archive)==raw['sha256'], 'hydrate original raw with Git LFS'
    with tarfile.open(archive) as tar:
        members=tar.getmembers();assert {m.name for m in members}==set(raw['members']) and len(members)==len(raw['members'])
        for m in members:
            assert m.isfile() and Path(m.name).name==m.name
            data=tar.extractfile(m).read();item=raw['members'][m.name]
            assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
            (run/'capture'/m.name).write_bytes(data)
    sys.path.insert(0,str(source));sys.path.insert(0,str(source/'tests/integration/perception'))
    spec=importlib.util.spec_from_file_location('frozen_shadow_audit',source/'tests/integration/perception/audit_control_shadow_v1.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=module.audit(run);expected=json.loads((bundle/'run-01/audit.json').read_text());assert result==expected
    capture=run/'capture';native_path=capture/'native-perception.jsonl';native_bytes=native_path.read_bytes()
    rows=[json.loads(line) for line in native_bytes.splitlines()];fresh=next(i for i,r in enumerate(rows) if r['perception']['available'])
    rejected=[]
    def reject(name, path, bad):
        original=path.read_bytes();path.write_bytes(bad)
        try:
            try:module.audit(run)
            except (ValueError,KeyError,AssertionError):rejected.append(name)
            else:raise AssertionError('mutation accepted: '+name)
        finally:path.write_bytes(original)
    for field in ('frame','source_ns','received_wall_ns','expires_ns','wall_expires_ns'):
        bad=copy.deepcopy(rows);bad[fresh]['perception'][field]+=1
        reject('native-'+field,native_path,(''.join(json.dumps(r)+'\n' for r in bad)).encode())
    for field in ('initialized','state_received_wall_ns'):
        bad=copy.deepcopy(rows);bad[fresh]['perception'][field]=0
        reject('native-'+field,native_path,(''.join(json.dumps(r)+'\n' for r in bad)).encode())
    bad=copy.deepcopy(rows);bad[fresh]['root_error']=1
    reject('native-root-error',native_path,(''.join(json.dumps(r)+'\n' for r in bad)).encode())
    bad=copy.deepcopy(rows);packet=bytearray.fromhex(bad[fresh]['actual'][2]);packet[-1]^=1;bad[fresh]['actual'][2]=packet.hex()
    reject('original-actual-crc',native_path,(''.join(json.dumps(r)+'\n' for r in bad)).encode())
    sensor_path=capture/'sensors.json';sensor=json.loads(sensor_path.read_text())
    for name,offset in [('reserved',28),('clock',32),('version',8)]:
        bad=copy.deepcopy(sensor);data=bytearray.fromhex(bad['ipc'][0]['packet_hex']);data[offset]^=1;bad['ipc'][0]['packet_hex']=data.hex()
        reject('wire-'+name,sensor_path,json.dumps(bad).encode())
    bad=copy.deepcopy(sensor);bad['raw']=[]
    reject('omitted-raw',sensor_path,json.dumps(bad).encode())
    name=next(iter(raw['members']));path=capture/name;bad=bytearray(path.read_bytes());bad[-1]^=1
    reject('raw-content-hash',path,bytes(bad))
    assert module.audit(run)==expected
    out=dict(status='PASS',scope='original failed trial integrity, not driving acceptance',exact_audit=True,rejected_mutations=rejected,
             camera_packets=result['camera_packets'],fresh_reads=result['fresh_reads'],driving_acceptance=False)
    (work/'validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))


if __name__=='__main__':main()
