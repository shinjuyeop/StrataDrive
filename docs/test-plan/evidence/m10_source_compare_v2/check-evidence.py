#!/usr/bin/env python3
"""Replay all original source, timing, raw pixels, model inputs and development scores."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(value, reason):
    if not value:
        raise ValueError(reason)


def local(root, name):
    p = Path(name)
    require(
        bool(p.parts) and not p.is_absolute() and ".." not in p.parts,
        "safe relative path",
    )
    return root / p


def check(e, output, workspace, media):
    require(not output.exists(), "new output required")
    files = {}
    for line in (e / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        require(name not in files and sha(local(e, name)) == digest, "metadata " + name)
        files[name] = digest
    actual = {
        str(p.relative_to(e))
        for p in e.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.name not in ("SHA256SUMS", "validation.json")
        and not (p.name.startswith("raw-") and p.suffix == ".tar")
    }
    require(set(files) == actual, "complete metadata inventory")
    freeze = json.loads((e / "freeze.json").read_text())
    parent = json.loads((e / "parent-freeze.json").read_text())
    require(
        freeze["parent_sha256"] == sha(e / "parent-freeze.json")
        and all(freeze["files"].get(k) == v for k, v in parent["files"].items()),
        "append-only source parent",
    )
    for n, h in freeze["inputs"].items():
        require(sha(local(workspace, n)) == h, "pinned external input " + n)
    # Quality replay needs at most the selected two raw datasets (~2GB); use the project volume.
    temp_parent = workspace / "build/m10-source-compare-audit"
    temp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fresh-", dir=temp_parent) as tmp:
        root = Path(tmp)
        seen = set()
        with tarfile.open(e / "sources.tar.gz", "r:gz") as archive:
            for member in archive:
                require(
                    member.isfile() and member.name not in seen, "unique regular source"
                )
                dest = local(root, member.name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(archive.extractfile(member).read())
                require(
                    sha(dest) == freeze["files"].get(member.name), "frozen source hash"
                )
                seen.add(member.name)
        require(seen == set(freeze["files"]), "complete source archive")
        supplemental = json.loads((e / "supplemental-sources.json").read_text())
        require(
            supplemental["prospectively_frozen"] is False,
            "retain prospective provenance gap",
        )
        supplement_seen = set()
        with tarfile.open(e / "supplemental-sources.tar.gz", "r:gz") as archive:
            for member in archive:
                require(
                    member.isfile()
                    and member.name not in seen
                    and member.name not in supplement_seen,
                    "unique supplementary source",
                )
                dest = local(root, member.name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(archive.extractfile(member).read())
                require(
                    sha(dest) == supplemental["files"].get(member.name),
                    "supplementary source hash",
                )
                supplement_seen.add(member.name)
        require(
            supplement_seen
            == {"tests/integration/perception/source_compare_v1_common.py"}
            == set(supplemental["files"]),
            "explicit supplementary helper",
        )
        for name in freeze["inputs"]:
            dest = local(root, name)
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(local(workspace, name))
        copy = root / "evidence"
        copy.mkdir()
        for name in files:
            if name == "sources.tar.gz":
                continue
            dest = local(copy, name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local(e, name), dest)
        code = r"""
import hashlib,json,runpy,sys,tarfile,zlib
from pathlib import Path
import numpy as np,cv2
from PIL import Image
from audit_carla_source_compare_v1 import audit_readback
from evidence_payload_v1 import payload
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.camera_resolution_v1 import NativeFrame, prepare
from source_compare_v1_common import derive
from score_source_compare_v1 import score
base,origin,media = map(Path,sys.argv[1:4])
runs=json.loads((base/'runs.json').read_text());freeze=json.loads((base/'freeze.json').read_text())
outcome=runpy.run_path(str(base/'audit-outcome.py'))['outcome'];e2e=runpy.run_path(str(base/'end-to-end.py'))['end_to_end']
expected={};live={};quality={};all_rgb=set();source_inputs={};failed={}
def live_binding(r, server, name):
 assert server['source_head']=='294096eb1c38eabf246e4f3a9cdab704e33a7f4c'
 source_profile = 'profiles/perception-source-compare-server-v2.json' if server['schema'].endswith('server-v2') else 'profiles/perception-readback-server-v1.json'
 sp=json.loads(Path(source_profile).read_text())
 assert server['profile_sha256']==freeze['files'][source_profile] and server['external_files']==sp['external_files']
 assert r['kernel_profile_sha256']==freeze['files']['profiles/perception-source-compare-v1.json']
 assert r['condition']==server['condition']==name
 assert r['freeze_sha256']==server['freeze_sha256']==hashlib.sha256((base/'freeze.json').read_bytes()).hexdigest()
 assert server['probe_sha256']==freeze['files']['tests/integration/perception/carla_source_compare_v1.py']
 assert r['plan_sha256']==server['plan_sha256']==freeze['plan_sha256']
 assert r['sdk_library_sha256']==json.loads(Path('profiles/perception-source-compare-v1.json').read_text())['sdk_library_sha256']
 assert (server['startup_budget_seconds'],server['capture_budget_seconds'],server['shutdown_budget_seconds'])==(180,900,30)

for name in runs['live_runs']:
 r=json.loads((base/name/'capture/result.json').read_text());server=json.loads((base/name/'server.json').read_text());pv=json.loads((base/name/'packet-validation.json').read_text())
 live_binding(r,server,name)
 assert r['condition']==name and r['freeze_sha256']==server['freeze_sha256']==hashlib.sha256((base/'freeze.json').read_bytes()).hexdigest()
 assert r['status']==server['status']==pv['original_status'] and server['server_exit']==130 and not server.get('forced_stop')
 assert (server['startup_budget_seconds'],server['capture_budget_seconds'],server['shutdown_budget_seconds'])==(180,900,30)
 assert server['capture_exit']==(0 if r['status']=='PASS' else 1)
 audit=outcome(r,pv['expected_failure']);assert audit==pv['audit']
 log=(base/name/'server.log').read_text();assert audit_readback(r,log)==server['readback_audit']
 assert e2e(r,log)==json.loads((base/'end-to-end.json').read_text())[name]
 live[name]=audit;source_inputs[name]=[]
 for row in r['raw']:expected[name+'/capture/'+row['path']]=(name,r['source_scale'],r['clock_instance'],row,'rgb',False)
for scale,name in runs['quality_runs'].items():
 r=json.loads((base/name/'dataset/capture.json').read_text());s=json.loads((base/name/'server.json').read_text());pv=json.loads((base/name/'packet-validation.json').read_text())
 assert int(scale)==r['scale'] and r['status']==s['status']=='PASS' and s['server_exit']==130 and s['capture_exit']==0 and not s.get('forced_stop')
 assert s['module_sha256']=='099f15274e768049c774166b17eb55838e672f9098f7d9e9f89aeddab6f81134'
 assert s['source_head']=='294096eb1c38eabf246e4f3a9cdab704e33a7f4c'
 assert s['freeze_sha256']==hashlib.sha256((base/'freeze.json').read_bytes()).hexdigest()
 assert s['protocol_sha256']==freeze['protocol_sha256'] and s['plan_sha256']==freeze['plan_sha256']
 assert s['phase']=='comparison' and s['scale']==int(scale) and s['selection_sha256'] is None
 for field,filename in [('probe_sha256','carla_camera_resolution_v1.py'),('helper_sha256','quality_geometry_v4.py'),('staging_sha256','quality_staging_v5.py')]:
  assert s[field]==freeze['files']['tests/integration/perception/'+filename]
 assert (s['startup_budget_seconds'],s['capture_budget_seconds'],s['shutdown_budget_seconds'])==(180,900,30)
 source_inputs[name]=[]
 for row in r['frames']:
  for kind in ('rgb','instance'):
   part=dict(row[kind],frame=row['frame'],source_ns=row['source_ns'])
   expected[name+'/dataset/'+part['path']]=(name,r['scale'],r['clock_instance'],part,kind,True)
for name in runs['failed_no_camera']:
 r=json.loads((base/name/'capture/result.json').read_text());s=json.loads((base/name/'server.json').read_text())
 live_binding(r,s,name)
 assert r['status']==s['status']=='FAIL' and s['server_exit']==130 and s['capture_exit']==1 and not s.get('forced_stop')
 assert not r['raw'] and not r['traces']['camera'] and not r['model_calls'] and not r['worker']['counters']['offered']
 assert 'owner made insufficient progress: camera' in r['error']
 traces=[json.loads(x.split(' ',1)[1]) for x in (base/name/'server.log').read_text().splitlines() if x.startswith('STRATA_READBACK_V1 ')]
 assert len(traces)>0 and all(x['error']=='unexpected_dimensions' and x['render']==x['send']==0 for x in traces)
 failed[name]=dict(status='REJECTED',raw=0,unsupported_requests=len(traces))
profile=json.loads(Path('profiles/perception-source-compare-v1.json').read_text());adapters={};cv2.setNumThreads(4)
for scale in (4,6):
 if scale==4:
  from physical_ai.perception.native_kernel_2k_v1 import NativeResize
  from physical_ai.perception.staged_kernel_2k_v1 import prepare_staged
  from physical_ai.perception.async_native_2k_v1 import BgraPacket
 else:
  from physical_ai.perception.native_kernel_v1 import NativeResize
  from physical_ai.perception.staged_kernel_v1 import prepare_staged
  from physical_ai.perception.async_native_v1 import BgraPacket
 binding=profile['native_libraries'][str(scale)]
 adapters[scale]=(NativeResize(Path(binding['path']).resolve(),binding['sha256']),prepare_staged,BgraPacket)
seen=set()
for item in json.loads((base/'raw-archives.json').read_text()):
 path=payload(origin/item['file'],item['sha256'],item['bytes'],media);members=[]
 with tarfile.open(path,'r|') as archive:
  for member in archive:
   assert member.isfile() and member.name in expected and member.name not in seen
   name,scale,clock,row,kind,keep=expected[member.name];w,h=640*scale,384*scale
   assert member.size==row['stored_bytes'];data=archive.extractfile(member).read();assert hashlib.sha256(data).hexdigest()==row['stored_sha256']
   dec=zlib.decompressobj();raw=dec.decompress(data,w*h*4+1);assert len(raw)==w*h*4 and dec.eof and not dec.unused_data and not dec.unconsumed_tail
   assert hashlib.sha256(raw).hexdigest()==row.get('bgra_sha256',row.get('sha256'))
   if keep:
    dest=base/member.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
   if kind=='rgb':
    rgb=Image.frombytes('RGB',(w,h),raw,'raw','BGRX').tobytes();digest=hashlib.sha256(rgb).hexdigest();all_rgb.add(digest)
    if not keep:assert digest==row['rgb_sha256']
    native,staged,Packet=adapters[scale];ident=FrameIdentity(1,clock,row['frame'],row['source_ns']);got=staged(native,Packet(ident,raw,1),{})[0];want=prepare(NativeFrame(ident,w,h,rgb))
    for k in want:np.testing.assert_array_equal(got[k],want[k])
    source_inputs[name].append(dict(frame=row['frame'],rgb_sha256=digest,tensor_sha256=hashlib.sha256(got['images'].tobytes()).hexdigest()))
   seen.add(member.name);members.append(member.name)
 assert members==item['members']
assert seen==set(expected)
for name,rows in source_inputs.items():
 pv=json.loads((base/name/'packet-validation.json').read_text());assert rows==pv['exact_inputs'] and [r['rgb_sha256'] for r in rows]==pv['rgb_sha256'] and len(rows)==pv['rgb_frames']
for scale,name in runs['quality_runs'].items():
 derived=derive(base/name/'dataset/capture.json',base/'freeze.json')
 for key,file in [('rgb','rgb.json'),('truth','evaluation-only-gt.json'),('metadata','benchmark.json'),('acceptance','acceptance.json')]:assert derived[key]==json.loads((base/name/'dataset'/file).read_text())
 assert derived['acceptance']['status']=='PASS'
 scored=score(base,base/name);assert scored==json.loads((base/f'comparison-{scale}-score.json').read_text());quality[scale]=scored
 # Verify that saved full-model predictions are tied to the exact native feed.
 report=json.loads((base/f'comparison-{scale}-model/run.json').read_text())
 assert [x['tensor_sha256'] for x in report['rows']]==[x['tensor_sha256'] for x in source_inputs[name]]
assert runpy.run_path(str(base/'compare-quality.py'))['compare'](base)==json.loads((base/'quality-comparison.json').read_text())
prior=json.loads((base/'prior-exclusion.json').read_text())['rgb_sha256'];future=json.loads((base/'future-exclusion.json').read_text())['rgb_sha256']
assert set(future)==set(prior)|all_rgb and len(future)==len(set(future))
print(json.dumps(dict(status='PASS',live=live,failed_no_camera=failed,quality=quality,raw_packets=len(seen),rgb_frames=sum(map(len,source_inputs.values())),future_exclusion=len(future),exact_inputs=source_inputs)))
"""
        env = dict(
            os.environ,
            OMP_WAIT_POLICY="PASSIVE",
            PYTHONPATH=str(root)
            + os.pathsep
            + str(root / "tests/integration/perception"),
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(copy), str(e), str(media)],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=900,
        )
        require(result.returncode == 0, result.stdout + result.stderr)
        audit = json.loads(result.stdout)
    value = dict(
        status="PASS",
        checked_files=len(files),
        source_files=len(seen),
        supplemental_source_files=len(supplement_seen),
        prospective_source_closure=False,
        audit=audit,
    )
    output.write_text(json.dumps(value, indent=2) + "\n")
    print(
        json.dumps({k: value[k] for k in ("status", "checked_files", "source_files")})
    )


if __name__ == "__main__":
    e, output = map(lambda p: Path(p).resolve(), sys.argv[1:3])
    workspace = Path.cwd()
    media = Path(
        next(
            x.split("=", 1)[1]
            for x in subprocess.check_output(
                ["git", "lfs", "env"], text=True
            ).splitlines()
            if x.startswith("LocalMediaDir=")
        )
    )
    check(e, output, workspace, media)
