#!/usr/bin/env python3
"""Fresh-source replay, native CPU input equality, and complete live raw audit."""

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
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def local(root, name):
    p = Path(name)
    require(not p.is_absolute() and ".." not in p.parts and bool(p.parts), "safe path")
    return root / p


def check(e):
    checked = set()
    for line in (e / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        require(
            name not in checked and sha(local(e, name)) == digest,
            "evidence hash: " + name,
        )
        checked.add(name)
    freeze = json.loads((e / "freeze.json").read_text())
    parent = json.loads((e / "parent-freeze.json").read_text())
    require(
        len(parent["files"]) == 514
        and len(freeze["files"]) == 533
        and freeze["parent_sha256"] == sha(e / "parent-freeze.json")
        and all(freeze["files"].get(k) == v for k, v in parent["files"].items()),
        "append-only533 source freeze",
    )
    eq = json.loads((e / "equivalence.json").read_text())
    reference = json.loads((e / "reference/equivalence-v1.json").read_text())
    ref = {r["rgb_sha256"]: r for r in reference["rows"]}
    require(
        eq["status"] == "PASS"
        and len(eq["rows"]) == 84
        and eq["freeze_sha256"] == sha(e / "freeze.json"),
        "all84 consumed input comparisons",
    )
    for row in eq["rows"]:
        require(
            row["tensor_exact"]
            and row["health_exact"]
            and row["tensor_sha256"] == ref[row["rgb_sha256"]]["tensor_sha256"],
            "tensor matches original frozen input",
        )
    names = ("none-01", "slow-01", "blocked-01", "exception-01")
    for name in names:
        r = json.loads((e / name / "result.json").read_text())
        require(
            r["source_freeze_sha256"] == sha(e / "freeze.json")
            and r["profile_sha256"]
            == freeze["files"]["profiles/perception-native-kernel-v1.json"],
            "replay freeze/profile",
        )
    normal = json.loads((e / "none-01/result.json").read_text())
    require(
        normal["media"]["manifest_sha256"] == sha(e / "reference/rgb-manifest.json"),
        "pilot media association",
    )
    numeric = json.loads((e / "reference/numeric-6.json").read_text())
    for i, original in enumerate(normal["media"]["originals"]):
        require(
            numeric["rows"][i]["rgb_sha256"] == original["rgb_sha256"]
            and any(
                r["file"] == f"numeric-6-raw/{i}-cuda.npz"
                and r["sha256"] == sha(e / "reference" / f"{i}-cuda.npz")
                for r in numeric["rows"][i]["raw_files"]
            ),
            "prior CUDA reference identity",
        )
    for name in ("baseline-01", "kernel-01"):
        r = json.loads((e / name / "capture/result.json").read_text())
        server = json.loads((e / name / "server.json").read_text())
        require(
            server["status"] == r["status"] == "PASS"
            and server["server_exit"] == 130
            and server["capture_exit"] == 0
            and not server.get("forced_stop"),
            "bounded live lifecycle",
        )
        require(
            server["freeze_sha256"] == r["freeze_sha256"] == sha(e / "freeze.json")
            and r["kernel_profile_sha256"]
            == freeze["files"]["profiles/perception-native-kernel-v1.json"],
            "live source/profile",
        )
    with tempfile.TemporaryDirectory(prefix="stratadrive-native-kernel-") as directory:
        root = Path(directory)
        extracted = set()
        with tarfile.open(e / "sources.tar.gz", "r:gz") as archive:
            for member in archive:
                require(
                    member.isfile() and member.name not in extracted,
                    "regular unique source",
                )
                target = local(root, member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                require(sha(target) == freeze["files"].get(member.name), "source hash")
                extracted.add(member.name)
        require(extracted == set(freeze["files"]), "complete533 source archive")
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
from audit_async_native_v1 import audit as audit_replay
from audit_native_decisions_v1 import audit_decisions
from audit_carla_native_kernel_v1 import audit as audit_live
from physical_ai.perception.async_native_v1 import BgraPacket
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.camera_resolution_v1 import decode
from physical_ai.perception.native_kernel_v1 import NativeResize
from physical_ai.perception.native_preprocess_v1 import prepare_packet
e=Path(sys.argv[1]);root=Path.cwd();reports=[];numeric_calls=0;refs={}
normal=json.loads((e/'none-01/result.json').read_text())
for i,row in enumerate(normal['media']['originals']):
    with np.load(e/'reference'/f'{i}-cuda.npz') as arrays:ds=decode(dict(arrays),6)
    refs[row['bgra_sha256']]=[(d.class_id,d.score,[v*6 for v in d.box]) for d in ds]
for name in ('none-01','slow-01','blocked-01','exception-01'):
    r=json.loads((e/name/'result.json').read_text());out=audit_replay(r);out['decisions']=audit_decisions(r);reports.append(out)
    offered={x['frame']:x['original_bgra_sha256'] for x in r['traces']['camera']}
    for call in r['model_calls']:
        if 'result' not in call:continue
        expected=refs[offered[call['identity']['frame']]];actual=call['result']['detections'];assert len(actual)==len(expected)
        for a,b in zip(actual,expected):
            assert a['class_id']==b[0]
            np.testing.assert_allclose(a['score'],b[1],atol=1e-4,rtol=0)
            np.testing.assert_allclose(a['box'],b[2],atol=.6,rtol=0)
        numeric_calls+=1
assert numeric_calls==146
live=[];expected={}
for name in ('baseline-01','kernel-01'):
    r=json.loads((e/name/'capture/result.json').read_text());live.append(audit_live(r))
    for row in r['raw']:expected[name+'/'+row['path']]=(r['clock_instance'],row)
assert len(expected)==72
profile=json.loads((root/'profiles/perception-native-kernel-v1.json').read_text())
native=NativeResize(root/'build/m10-native-kernel-v1/libstrata_resize_v1.so',profile['native_library_sha256'])
cv2.setNumThreads(4);seen=set();hashes=set();inputs=[]
with tarfile.open(e/'raw-camera.tar.gz','r|gz') as archive:
    for member in archive:
        assert member.isfile() and member.name in expected and member.name not in seen
        clock,row=expected[member.name];assert member.size==row['stored_bytes']
        data=archive.extractfile(member).read();assert hashlib.sha256(data).hexdigest()==row['stored_sha256']
        decoder=zlib.decompressobj();raw=decoder.decompress(data,3840*2304*4+1)
        assert len(raw)==row['raw_bytes']==3840*2304*4 and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
        assert hashlib.sha256(raw).hexdigest()==row['bgra_sha256']
        rgb=Image.frombytes('RGB',(3840,2304),raw,'raw','BGRX').tobytes();digest=hashlib.sha256(rgb).hexdigest();assert digest==row['rgb_sha256']
        packet=BgraPacket(FrameIdentity(1,clock,row['frame'],row['source_ns']),raw,1)
        before=prepare_packet(packet);after=native.prepare(packet)
        assert before[1:3]==after[1:3]
        for key in before[0]:np.testing.assert_array_equal(before[0][key],after[0][key])
        inputs.append(dict(rgb_sha256=digest,tensor_sha256=hashlib.sha256(after[0]['images'].tobytes()).hexdigest()))
        seen.add(member.name);hashes.add(digest)
assert seen==set(expected)
prior=json.loads((e/'prior-exclusion.json').read_text())['rgb_sha256'];union=json.loads((e/'future-exclusion.json').read_text())['rgb_sha256']
assert len(prior)==5689 and len(union)==5761 and set(union)==set(prior)|hashes
print(json.dumps(dict(status='PASS',replay=reports,live=live,numeric_calls=numeric_calls,raw_frames=len(seen),live_exact_inputs=inputs,future_exclusion=len(union))))
"""
        result = subprocess.run(
            [sys.executable, "-c", code, str(e)],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
        )
        require(result.returncode == 0, result.stdout + result.stderr)
        replay = json.loads(result.stdout)
    return dict(
        status="PASS",
        checked_files=len(checked),
        source_files=len(extracted),
        audit=replay,
    )


if __name__ == "__main__":
    output = Path(sys.argv[2])
    require(not output.exists(), "new audit output required")
    result = check(Path(sys.argv[1]).resolve())
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps({k: result[k] for k in ("status", "checked_files", "source_files")})
    )
