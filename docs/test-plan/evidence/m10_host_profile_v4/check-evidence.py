#!/usr/bin/env python3
"""Extract sealed sources and reproduce renderer boundary tests without CARLA."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile


def extract(bundle, work):
    frozen = json.loads((bundle/'sources.json').read_text())
    assert hashlib.sha256((bundle/'sources.tar.gz').read_bytes()).hexdigest() == frozen['archive_sha256']
    source = work/'source'; source.mkdir(parents=True, exist_ok=False)
    with tarfile.open(bundle/'sources.tar.gz', 'r:gz') as tar:
        members = tar.getmembers()
        assert len(members) == len(frozen['files']) and {m.name for m in members} == set(frozen['files'])
        for member in members:
            name = Path(member.name)
            assert member.isfile() and not name.is_absolute() and '..' not in name.parts
            data = tar.extractfile(member).read(); item = frozen['files'][member.name]
            assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256']
            target = source/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
    return source, frozen


def main():
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True); a = p.parse_args()
    work = a.work.resolve(); work.mkdir(parents=True, exist_ok=False)
    source, frozen = extract(Path(__file__).resolve().parent, work)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(source)+':'+str(source/'tests/integration/perception'))
    with (work/'tests.log').open('w') as log:
        subprocess.run([sys.executable,'-m','unittest','test_paired_fault_v1','test_carla_readiness_v1','test_scene_capture_v1','test_renderer_shutdown_v1','test_renderer_lifecycle_v1','test_render_provenance_v1','test_scene_mailbox_v1','test_endurance_v1','test_endurance_host_v1','test_profile_host_v1','-v'],
                       cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    result = dict(status='PASS', focused_tests=61, source_files=len(frozen['files']), live_server=False)
    (work/'validation.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result))


if __name__ == '__main__': main()
