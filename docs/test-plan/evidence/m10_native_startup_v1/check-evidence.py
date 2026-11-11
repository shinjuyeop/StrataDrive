#!/usr/bin/env python3
"""Fresh frozen-source audit of preparation, rate comparisons and all live raw."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def local(root, name):
    path = Path(name)
    require(
        not path.is_absolute() and ".." not in path.parts and bool(path.parts),
        "safe path",
    )
    return root / path


def check(e):
    checked = set()
    for line in (e / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        require(
            name not in checked and sha(local(e, name)) == digest,
            "evidence hash: " + name,
        )
        checked.add(name)
    parent = json.loads((e / "parent-freeze.json").read_text())
    freeze = json.loads((e / "freeze.json").read_text())
    require(
        len(parent["files"]) == 533
        and len(freeze["files"]) == 547
        and freeze["parent_sha256"] == sha(e / "parent-freeze.json")
        and all(freeze["files"].get(k) == v for k, v in parent["files"].items()),
        "append-only547 freeze",
    )
    profile_hash = freeze["files"]["profiles/perception-native-startup-v1.json"]
    for rate in (10, 13, 20):
        r = json.loads((e / f"rate-{rate}/result.json").read_text())
        require(
            r["source_freeze_sha256"] == sha(e / "freeze.json")
            and r["profile_sha256"] == profile_hash,
            "replay source/profile",
        )
    memory = json.loads((e / "memory-freeze.json").read_text())
    require(
        len(memory["files"]) == 554
        and memory["parent_sha256"] == sha(e / "freeze.json")
        and all(memory["files"].get(k) == v for k, v in freeze["files"].items()),
        "append-only554 memory revision",
    )
    for name in ("prepared-02", "memory-01", "memory-02"):
        r = json.loads((e / name / "capture/result.json").read_text())
        server = json.loads((e / name / "server.json").read_text())
        is_memory = name.startswith("memory-")
        source = memory if is_memory else freeze
        source_path = "memory-freeze.json" if is_memory else "freeze.json"
        profile_path = (
            "profiles/perception-native-memory-v1.json"
            if is_memory
            else "profiles/perception-native-startup-v1.json"
        )
        require(
            server["status"] == r["status"] == "PASS"
            and server["capture_exit"] == 0
            and server["server_exit"] == 130
            and not server.get("forced_stop"),
            "live lifecycle",
        )
        require(
            server["freeze_sha256"] == r["freeze_sha256"] == sha(e / source_path)
            and r["kernel_profile_sha256"] == source["files"][profile_path],
            "live source/profile",
        )
        require(
            (
                server["startup_budget_seconds"],
                server["capture_budget_seconds"],
                server["shutdown_budget_seconds"],
            )
            == (180, 900, 30),
            "unchanged lifecycle budgets",
        )
    declaration = json.loads((e / "recovery-declaration.json").read_text())
    failed = json.loads((e / "prepared-01/server.json").read_text())
    recovered = json.loads((e / "prepared-01-recovery/server.json").read_text())
    require(
        failed["status"] == "FAIL"
        and failed["server_exit"] == -9
        and failed["forced_stop"]
        and "capture_exit" not in failed
        and not (e / "prepared-01/capture").exists(),
        "original startup failure retained",
    )
    require(
        declaration["original_server_sha256"] == sha(e / "prepared-01/server.json")
        and declaration["protocol_sha256"] == sha(e / "recovery-protocol.md")
        and declaration["freeze_sha256"] == sha(e / "freeze.json")
        and declaration["attempts_allowed"] == 1
        and declaration["declared_utc"] < recovered["started_utc"]
        and not declaration["source_changes"]
        and not declaration["lifecycle_changes"],
        "prospective single unchanged recovery",
    )
    failed_capture = json.loads(
        (e / "prepared-01-recovery/capture/result.json").read_text()
    )
    require(
        recovered["status"] == failed_capture["status"] == "FAIL"
        and recovered["capture_exit"] == 1
        and recovered["server_exit"] == 130
        and not recovered.get("forced_stop")
        and failed_capture["recorder_overflow"] == [1300]
        and recovered["freeze_sha256"]
        == failed_capture["freeze_sha256"]
        == sha(e / "freeze.json"),
        "original232-image recording overflow retained",
    )
    with tempfile.TemporaryDirectory(prefix="stratadrive-native-startup-audit-") as tmp:
        root = Path(tmp)
        seen = set()
        with tarfile.open(e / "sources.tar.gz", "r:gz") as archive:
            for member in archive:
                require(
                    member.isfile() and member.name not in seen, "regular unique source"
                )
                target = local(root, member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                require(sha(target) == freeze["files"].get(member.name), "source hash")
                seen.add(member.name)
        require(seen == set(freeze["files"]), "complete547 source archive")
        memory_seen = set()
        with tarfile.open(e / "memory-sources.tar.gz", "r:gz") as archive:
            for member in archive:
                require(
                    member.isfile() and member.name not in memory_seen,
                    "regular unique memory source",
                )
                target = local(root, member.name)
                data = archive.extractfile(member).read()
                require(
                    hashlib.sha256(data).hexdigest()
                    == memory["files"].get(member.name),
                    "memory source hash",
                )
                if target.exists():
                    require(
                        sha(target) == memory["files"][member.name],
                        "unchanged parent bytes",
                    )
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                memory_seen.add(member.name)
        require(
            memory_seen == set(memory["files"]), "complete554 memory source archive"
        )

        env = dict(
            os.environ,
            OMP_WAIT_POLICY="PASSIVE",
            PYTHONPATH=str(root)
            + os.pathsep
            + str(root / "tests/integration/perception"),
        )
        code = r"""
import hashlib,json,sys,tarfile,zlib
from pathlib import Path
import cv2,numpy as np
from PIL import Image
from audit_native_startup_v1 import audit as audit_replay
from audit_carla_native_startup_v1 import audit as audit_live
from audit_carla_native_memory_v1 import audit as audit_memory
from audit_native_startup_v1 import audit_preparation
from audit_async_native_v1 import validate_result
from physical_ai.perception.async_native_v1 import BgraPacket
from physical_ai.perception.contract import FrameIdentity,sha256_file
from physical_ai.perception.camera_resolution_v1 import decode
from physical_ai.perception.native_kernel_v1 import NativeResize
from physical_ai.perception.native_preprocess_v1 import prepare_packet
e=Path(sys.argv[1]);root=Path.cwd();replays=[];numeric_calls=0;refs={}
normal=json.loads((e/'rate-10/result.json').read_text())
manifest=json.loads((e/'reference/rgb-manifest.json').read_text())
numeric=json.loads((e/'reference/numeric-6.json').read_text())
assert normal['media']['manifest_sha256']==sha256_file(e/'reference/rgb-manifest.json')
for i,row in enumerate(normal['media']['originals']):
    assert numeric['rows'][i]['rgb_sha256']==row['rgb_sha256']==manifest['frames'][i]['rgb_sha256']
    assert any(x['file']==f'numeric-6-raw/{i}-cuda.npz' and x['sha256']==sha256_file(e/'reference'/f'{i}-cuda.npz') for x in numeric['rows'][i]['raw_files'])
    with np.load(e/'reference'/f'{i}-cuda.npz') as arrays:ds=decode(dict(arrays),6)
    refs[row['bgra_sha256']]=[(d.class_id,d.score,[v*6 for v in d.box]) for d in ds]
for rate in (10,13,20):
    r=json.loads((e/f'rate-{rate}/result.json').read_text());replays.append(audit_replay(r))
    assert r['media']==normal['media']
    offered={x['frame']:x['original_bgra_sha256'] for x in r['traces']['camera']}
    for call in r['model_calls']:
        expected=refs[offered[call['identity']['frame']]];actual=call['result']['detections']
        assert len(actual)==len(expected)
        for a,b in zip(actual,expected):
            assert a['class_id']==b[0]
            np.testing.assert_allclose(a['score'],b[1],atol=1e-4,rtol=0)
            np.testing.assert_allclose(a['box'],b[2],atol=.6,rtol=0)
        numeric_calls+=1
live=[];expected={}
for name in ('prepared-02','memory-01','memory-02'):
    r=json.loads((e/name/'capture/result.json').read_text())
    live.append((audit_memory if name.startswith('memory-') else audit_live)(r))
    for row in r['raw']:expected[name+'/'+row['path']]=(r['clock_instance'],row)
r=json.loads((e/'prepared-01-recovery/capture/result.json').read_text())
assert r['status']=='FAIL' and r['closed'] and not r['cleanup_errors'] and not r['errors']
assert r['recorder_overflow']==r['recorder']['overflow']==[1300]
assert not r['recorder']['errors'] and r['recorder']['stopped'] and r['recorder']['capacity']==8
assert len(r['traces']['state'])==1161 and len(r['raw'])==len(r['traces']['camera'])==r['recorder']['offered']==232
assert len(r['model_calls'])==231 and 'decisions' not in r
failed_preparation=audit_preparation(r)
c=r['final_worker']['counters']
assert c['offered']==c['accepted']==232 and c['started']==c['completed']==231
assert c['published']==226 and c['late']==4 and c['obsolete']==c['cancelled']==1
assert c['errors']==c['rejected']==c['overwritten']==c['expired_pending']==0
prior_frame,prior_source=r['initial_frame'],r['initial_source_ns'];ticks={}
for tick in r['traces']['state']:
    assert tick['frame']==prior_frame+1 and abs(tick['source_ns']-prior_source-10_000_000)<=1000
    ticks[tick['frame']]=tick;prior_frame,prior_source=tick['frame'],tick['source_ns']
assert prior_frame<r['last_planned_frame']
assert [x['frame'] for x in r['traces']['camera']]==[f for f in ticks if f%5==0]==[x['frame'] for x in r['raw']]==[x['frame'] for x in r['recorder']['records']]
offered={x['frame']:x for x in r['traces']['camera']};calls={}
for call in r['model_calls']:
    result=validate_result(call['result']);identity=call['identity'];frame=identity['frame'];image=offered[frame]
    assert frame not in calls and identity==call['result']['identity']
    assert identity['clock_instance']==r['clock_instance'] and identity['epoch']==1
    assert identity['source_ns']==image['source_ns'] and abs(identity['source_ns']-ticks[frame]['source_ns'])<=1000
    assert image['offer_entry_wall_ns']<=call['received_wall_ns']<=image['end_wall_ns']
    assert call['received_wall_ns']<=call['begin_wall_ns']<=call['end_wall_ns']
    calls[frame]=call
for row in r['traces']['consumer']:
    if row['perception'] is None:continue
    result=validate_result(row['perception']);call=calls[result.identity.frame]
    assert row['perception']==call['result'] and call['end_wall_ns']<=row['end_wall_ns']
    assert 0<=row['snapshot_read_source_ns']-result.identity.source_ns<100_000_000
    assert 0<=row['snapshot_read_wall_ns']-call['received_wall_ns']<100_000_000
for row in r['raw']:expected['prepared-01-recovery/'+row['path']]=(r['clock_instance'],row)
assert len(expected)==952
failed=dict(status='ORIGINAL_FAIL_PRESERVED',raw=232,actual_ticks=1161,preparation=failed_preparation,decision_cause_replay=False,reason='streaming recorder overflow; original per-decision trace absent')
profile=json.loads((root/'profiles/perception-native-startup-v1.json').read_text())
native=NativeResize(root/'build/m10-native-kernel-v1/libstrata_resize_v1.so',profile['native_library_sha256'])
cv2.setNumThreads(4);seen=set();hashes=set();inputs=[]
archives=sorted(e.glob('raw-camera-*.tar'));assert len(archives)==16
for path in archives:
    assert path.stat().st_size<1_500_000_000
    with tarfile.open(path,'r|') as archive:
        for member in archive:
            assert member.isfile() and member.name in expected and member.name not in seen
            clock,row=expected[member.name];assert member.size==row['stored_bytes']
            data=archive.extractfile(member).read();assert hashlib.sha256(data).hexdigest()==row['stored_sha256']
            decoder=zlib.decompressobj();raw=decoder.decompress(data,3840*2304*4+1)
            assert len(raw)==row['raw_bytes']==3840*2304*4 and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
            assert hashlib.sha256(raw).hexdigest()==row['bgra_sha256']
            rgb=Image.frombytes('RGB',(3840,2304),raw,'raw','BGRX').tobytes()
            digest=hashlib.sha256(rgb).hexdigest();assert digest==row['rgb_sha256']
            packet=BgraPacket(FrameIdentity(1,clock,row['frame'],row['source_ns']),raw,1)
            before=prepare_packet(packet);after=native.prepare(packet)
            assert before[1:3]==after[1:3]
            for key in before[0]:np.testing.assert_array_equal(before[0][key],after[0][key])
            inputs.append(dict(rgb_sha256=digest,tensor_sha256=hashlib.sha256(after[0]['images'].tobytes()).hexdigest()))
            seen.add(member.name);hashes.add(digest)
assert seen==set(expected)
prior=json.loads((e/'prior-exclusion.json').read_text())['rgb_sha256']
union=json.loads((e/'future-exclusion.json').read_text())['rgb_sha256']
assert len(prior)==5761 and set(union)==set(prior)|hashes and len(union)==len(set(union))
print(json.dumps(dict(status='PASS',replay=replays,live=live,failed_recording=failed,numeric_calls=numeric_calls,raw_frames=len(seen),live_exact_inputs=inputs,future_exclusion=len(union))))
"""
        run = subprocess.run(
            [sys.executable, "-c", code, str(e)],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=900,
        )
        require(run.returncode == 0, run.stdout + run.stderr)
        result = json.loads(run.stdout)
    return dict(
        status="PASS",
        checked_files=len(checked),
        source_files=len(memory_seen),
        audit=result,
    )


if __name__ == "__main__":
    output = Path(sys.argv[2])
    require(not output.exists(), "new audit output required")
    result = check(Path(sys.argv[1]).resolve())
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps({k: result[k] for k in ("status", "checked_files", "source_files")})
    )
