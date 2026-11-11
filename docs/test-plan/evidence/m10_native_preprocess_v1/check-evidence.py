#!/usr/bin/env python3
"""Verify source/raw archives and replay traces; preserve failed live admission."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import zlib

from PIL import Image


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
    require(
        not p.is_absolute() and ".." not in p.parts and bool(p.parts),
        "safe relative path",
    )
    return root / p


def check(e):
    seen = set()
    for line in (e / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        require(
            name not in seen and sha(local(e, name)) == digest, "evidence hash: " + name
        )
        seen.add(name)
    frozen = json.loads((e / "live-freeze.json").read_text())
    first = json.loads((e / "freeze.json").read_text())
    parent = json.loads((e / "parent-freeze.json").read_text())
    require(
        [len(x["files"]) for x in (parent, first, frozen)] == [503, 509, 514],
        "source denominators",
    )
    require(
        all(first["files"].get(k) == v for k, v in parent["files"].items())
        and all(frozen["files"].get(k) == v for k, v in first["files"].items()),
        "append-only source freezes",
    )
    require(
        first["parent_sha256"] == sha(e / "parent-freeze.json")
        and frozen["parent_sha256"] == sha(e / "freeze.json"),
        "source parent identities",
    )
    equivalence = json.loads((e / "equivalence.json").read_text())
    require(
        equivalence["status"] == "PASS"
        and len(equivalence["rows"]) == 84
        and equivalence["freeze_sha256"] == sha(e / "freeze.json")
        and all(r["rgb_exact"] and r["tensor_exact"] for r in equivalence["rows"]),
        "all84 tensor checks",
    )
    names = ("none-01", "slow-01", "blocked-01", "exception-01")
    for n in names:
        r = json.loads((e / n / "result.json").read_text())
        require(
            r["source_freeze_sha256"] == sha(e / "freeze.json")
            and r["profile_sha256"]
            == first["files"]["profiles/perception-native-preprocess-v1.json"],
            "replay source/profile",
        )
    normal = json.loads((e / "none-01/result.json").read_text())
    reference = json.loads((e / "reference/numeric-6.json").read_text())
    require(
        sha(e / "reference/rgb-manifest.json") == normal["media"]["manifest_sha256"],
        "original media manifest identity",
    )
    for i, original in enumerate(normal["media"]["originals"]):
        row = reference["rows"][i]
        require(
            row["rgb_sha256"] == original["rgb_sha256"]
            and any(
                f["file"] == f"numeric-6-raw/{i}-cuda.npz"
                and f["sha256"] == sha(e / "reference" / f"{i}-cuda.npz")
                for f in row["raw_files"]
            ),
            "prior CUDA output/image association",
        )
    live = json.loads((e / "live-01/capture/result.json").read_text())
    server = json.loads((e / "live-01/server.json").read_text())
    require(
        server["status"] == live["status"] == "FAIL"
        and server["server_exit"] == 130
        and server["capture_exit"] == 1
        and not server.get("forced_stop")
        and not live.get("error")
        and not live["cleanup_errors"],
        "original live deadline failure and clean shutdown retained",
    )
    require(
        server["freeze_sha256"] == live["freeze_sha256"] == sha(e / "live-freeze.json")
        and server["profile_sha256"]
        == frozen["files"]["profiles/perception-carla-native-async-v1.json"],
        "live source/profile identity",
    )
    with tempfile.TemporaryDirectory(
        prefix="stratadrive-native-preprocess-"
    ) as directory:
        root = Path(directory)
        extracted = set()
        with tarfile.open(e / "sources.tar.gz", "r:gz") as archive:
            for member in archive:
                require(
                    member.isfile() and member.name not in extracted,
                    "source member type/duplicate",
                )
                target = local(root, member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                require(
                    sha(target) == frozen["files"].get(member.name),
                    "source member hash",
                )
                extracted.add(member.name)
        require(extracted == set(frozen["files"]), "complete514 source archive")
        env = dict(
            os.environ,
            PYTHONPATH=str(root)
            + os.pathsep
            + str(root / "tests/integration/perception"),
        )
        code = r"""
import json,sys
from copy import deepcopy
from pathlib import Path
import numpy as np
from audit_async_native_v1 import audit as audit_replay
from audit_carla_native_async_v1 import audit as audit_live
from physical_ai.perception.camera_resolution_v1 import decode
e=Path(sys.argv[1]); rows=[]; numeric=0
normal=json.loads((e/'none-01/result.json').read_text());refs={}
for i,row in enumerate(normal['media']['originals']):
    with np.load(e/'reference'/f'{i}-cuda.npz') as arrays: ds=decode(dict(arrays),6)
    refs[row['bgra_sha256']]=[(d.class_id,d.score,[v*6 for v in d.box]) for d in ds]
for name in ('none-01','slow-01','blocked-01','exception-01'):
    r=json.loads((e/name/'result.json').read_text()); rows.append(audit_replay(r))
    offered={x['frame']:x['original_bgra_sha256'] for x in r['traces']['camera']}
    for call in r['model_calls']:
        if 'result' not in call: continue
        expected=refs[offered[call['identity']['frame']]];actual=call['result']['detections']
        assert len(expected)==len(actual)
        for a,b in zip(actual,expected):
            assert a['class_id']==b[0]
            np.testing.assert_allclose(a['score'],b[1],atol=1e-4,rtol=0)
            np.testing.assert_allclose(a['box'],b[2],atol=.6,rtol=0)
        numeric+=1
assert numeric==111
live=json.loads((e/'live-01/capture/result.json').read_text())
assert live['status']=='FAIL' and live['unique_consumed_frames']==0
assert live['worker']['counters']['late']==len(live['model_calls'])==37
assert live['worker']['counters']['published']==live['worker']['counters']['errors']==0
assert live['audit_error'].endswith('ValueError: live fresh output consumption\n')
# Diagnostic only: bypass the status guard on a COPY to replay all checks up to
# the prospective fresh-consumption gate. The original report remains FAIL.
diagnostic=deepcopy(live);diagnostic['status']='PASS'
try: audit_live(diagnostic)
except ValueError as error: assert str(error)=='live fresh output consumption'
else: raise AssertionError('original live failure disappeared')
silence=[x for x in live['traces']['consumer'] if x['snapshot_read_wall_ns']>=live['sensor_stopped_wall_ns']+100000000]
assert len(silence)>=5 and all(x['perception'] is None and x['snapshot_read_source_ns']==live['traces']['state'][-1]['source_ns'] for x in silence)
print(json.dumps(dict(status='PASS',replay=rows,numeric_calls=numeric,live_acceptance='FAIL',live_expected_rejection='live fresh output consumption',silence_reads=len(silence))))
"""
        result = subprocess.run(
            [sys.executable, "-c", code, str(e)],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        require(result.returncode == 0, result.stdout + result.stderr)
        replay = json.loads(result.stdout)
    expected = {r["path"]: r for r in live["raw"]}
    require(
        len(expected) == len(live["traces"]["camera"]) == 60, "all live raw callbacks"
    )
    raw_seen, rgb_hashes = set(), set()
    with tarfile.open(e / "raw-camera.tar.gz", "r|gz") as archive:
        for member in archive:
            require(
                member.isfile()
                and member.name in expected
                and member.name not in raw_seen,
                "raw member",
            )
            row = expected[member.name]
            require(member.size == row["stored_bytes"], "raw stored size")
            compressed = archive.extractfile(member).read()
            require(
                hashlib.sha256(compressed).hexdigest() == row["stored_sha256"],
                "stored camera hash",
            )
            decoder = zlib.decompressobj()
            raw = decoder.decompress(compressed, 3840 * 2304 * 4 + 1)
            require(
                len(raw) == row["raw_bytes"] == 3840 * 2304 * 4
                and decoder.eof
                and not decoder.unused_data
                and not decoder.unconsumed_tail,
                "bounded original camera bytes",
            )
            require(
                hashlib.sha256(raw).hexdigest() == row["bgra_sha256"],
                "original BGRA hash",
            )
            rgb = Image.frombytes("RGB", (3840, 2304), raw, "raw", "BGRX").tobytes()
            digest = hashlib.sha256(rgb).hexdigest()
            require(digest == row["rgb_sha256"], "original RGB exclusion hash")
            rgb_hashes.add(digest)
            raw_seen.add(member.name)
    require(raw_seen == set(expected), "complete raw archive")
    prior = json.loads((e / "prior-exclusion.json").read_text())["rgb_sha256"]
    union = json.loads((e / "future-exclusion.json").read_text())["rgb_sha256"]
    require(
        len(prior) == 5629
        and len(union) == 5689
        and set(union) == set(prior) | rgb_hashes,
        "all-attempt future exclusion",
    )
    return dict(
        status="PASS",
        checked_files=len(seen),
        source_files=len(extracted),
        original_raw_frames=len(raw_seen),
        future_exclusion=len(union),
        replay=replay,
    )


if __name__ == "__main__":
    evidence = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2])
    require(not output.exists(), "new audit output required")
    result = check(evidence)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
