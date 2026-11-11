#!/usr/bin/env python3
"""Verify complete raw payloads and replay evidence from only archived source bytes."""

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


def check(e, media):
    checked = set()
    for line in (e / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        require(
            name not in checked and sha(local(e, name)) == digest,
            "evidence bytes: " + name,
        )
        checked.add(name)
    parent = json.loads((e / "parent-freeze.json").read_text())
    freeze = json.loads((e / "freeze.json").read_text())
    require(
        len(parent["files"]) == 565
        and freeze["parent_sha256"] == sha(e / "parent-freeze.json")
        and all(freeze["files"].get(k) == v for k, v in parent["files"].items()),
        "append-only parent",
    )
    runs = json.loads((e / "runs.json").read_text())
    require(
        set(runs["conditions"])
        == {"baseline-01", "deferred-01", "deferred-02", "baseline-02"},
        "all declared conditions",
    )
    for condition, name in runs["conditions"].items():
        r = json.loads(local(e, name + "/capture/result.json").read_text())
        s = json.loads(local(e, name + "/server.json").read_text())
        require(
            r["status"]
            == s["status"]
            == ("FAIL" if condition in runs["failed_conditions"] else "PASS")
            and s["capture_exit"]
            == (1 if condition in runs["failed_conditions"] else 0)
            and s["server_exit"] == 130
            and not s.get("forced_stop"),
            "successful lifecycle",
        )
        require(
            r["condition"] == s["condition"] == condition
            and r["freeze_sha256"] == s["freeze_sha256"] == sha(e / "freeze.json")
            and r["kernel_profile_sha256"]
            == freeze["files"]["profiles/perception-readback-v1.json"]
            and s["probe_sha256"]
            == freeze["files"]["tests/integration/perception/carla_readback_v1.py"],
            "original source and condition",
        )
        require(
            (
                s["startup_budget_seconds"],
                s["capture_budget_seconds"],
                s["shutdown_budget_seconds"],
            )
            == (180, 900, 30),
            "lifecycle budgets",
        )
    for name in runs["startup_failures"]:
        s = json.loads(local(e, name + "/server.json").read_text())
        d = json.loads(local(e, name + "-recovery-declaration.json").read_text())
        recovered = json.loads(
            local(e, runs["conditions"][s["condition"]] + "/server.json").read_text()
        )
        require(
            s["status"] == "FAIL"
            and "capture_exit" not in s
            and not local(e, name + "/capture").exists(),
            "original startup failure retained",
        )
        require(
            d["original_server_sha256"] == sha(local(e, name + "/server.json"))
            and d["attempts_allowed"] == 1
            and d["declared_utc"] < recovered["started_utc"]
            and d["freeze_sha256"] == sha(e / "freeze.json"),
            "prospective recovery",
        )
    with tempfile.TemporaryDirectory(prefix="stratadrive-readback-audit-") as tmp:
        root = Path(tmp)
        seen = set()
        with tarfile.open(e / "sources.tar.gz", "r:gz") as archive:
            for member in archive:
                require(
                    member.isfile() and member.name not in seen, "unique regular source"
                )
                target = local(root, member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                require(
                    sha(target) == freeze["files"].get(member.name),
                    "frozen source hash",
                )
                seen.add(member.name)
        require(seen == set(freeze["files"]), "complete source archive")
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
from audit_carla_readback_v1 import audit_readback
import runpy
from evidence_payload_v1 import payload
from physical_ai.perception.async_native_v1 import BgraPacket
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.native_kernel_v1 import NativeResize
from physical_ai.perception.native_preprocess_v1 import prepare_packet
e=Path(sys.argv[1]);media=Path(sys.argv[2]) if sys.argv[2] else None
runs=json.loads((e/'runs.json').read_text());audits={};expected={}
outcome=runpy.run_path(str(e/'audit-outcome.py'))['outcome']
for condition,name in runs['conditions'].items():
 r=json.loads((e/name/'capture/result.json').read_text());audits[condition]=outcome(r,runs['failed_conditions'].get(condition))
 s=json.loads((e/name/'server.json').read_text())
 assert audit_readback(r,(e/name/'server.log').read_text())==s['readback_audit']

 for row in r['raw']:expected[name+'/'+row['path']]=(r['clock_instance'],row)
profile=json.loads(Path('profiles/perception-readback-v1.json').read_text())
native=NativeResize(Path('build/m10-native-kernel-v1/libstrata_resize_v1.so').resolve(),profile['native_library_sha256'])
cv2.setNumThreads(4);seen=set();hashes=set();inputs=[]
archives=json.loads((e/'raw-archives.json').read_text());seen_archives=set()
for item in archives:
 assert item['file'] not in seen_archives and '/' not in item['file'] and item['file'].startswith('raw-camera-')
 seen_archives.add(item['file'])
 path=payload(e/item['file'],item['sha256'],item['bytes'],media)
 members=[]
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
   seen.add(member.name);members.append(member.name);hashes.add(digest)
 assert members==item['members']
assert seen==set(expected)
prior=json.loads((e/'prior-exclusion.json').read_text())['rgb_sha256']
union=json.loads((e/'future-exclusion.json').read_text())['rgb_sha256']
assert len(prior)==7013 and set(union)==set(prior)|hashes and len(union)==len(set(union))
print(json.dumps(dict(status='PASS',live=audits,raw_frames=len(seen),exact_inputs=inputs,future_exclusion=len(union))))
"""
        result = subprocess.run(
            [sys.executable, "-c", code, str(e), str(media) if media else ""],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=900,
        )
        require(result.returncode == 0, result.stdout + result.stderr)
        audit = json.loads(result.stdout)
    return dict(
        status="PASS", checked_files=len(checked), source_files=len(seen), audit=audit
    )


if __name__ == "__main__":
    e, output = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    require(not output.exists(), "new output required")
    media = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    if media is None:
        settings = subprocess.check_output(["git", "lfs", "env"], cwd=e, text=True)
        media = Path(
            next(
                x.split("=", 1)[1]
                for x in settings.splitlines()
                if x.startswith("LocalMediaDir=")
            )
        )
    result = check(e, media)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps({k: result[k] for k in ("status", "checked_files", "source_files")})
    )
