"""Reproduce frozen endurance audits, including original failures and all raw hashes."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tarfile
from seal_paired_v1 import sha


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def checked_members(path,manifest,target=None):
    assert path.stat().st_size==manifest['bytes'] and sha(path)==manifest['sha256']
    with tarfile.open(path,'r:*') as tar:
        members=tar.getmembers()
        assert len(members)==len(manifest['members']) and {m.name for m in members}==set(manifest['members'])
        for member in members:
            n=Path(member.name);assert member.isfile() and not n.is_absolute() and '..' not in n.parts
            h=hashlib.sha256();count=0
            output=None
            if target:
                p=target/n;p.parent.mkdir(parents=True,exist_ok=True);output=p.open('wb')
            try:
                with tar.extractfile(member) as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):
                        h.update(block);count+=len(block)
                        if output:output.write(block)
            finally:
                if output:output.close()
            expected=manifest['members'][member.name]
            assert count==expected['bytes'] and h.hexdigest()==expected['sha256']


def main(a):
    a.work.mkdir(parents=True,exist_ok=False)
    source,frozen=module('source_check',a.series/'check-evidence.py').extract(a.series,a.work)
    sys.path[:0]=[str(source),str(source/'tests/integration/perception'),str(source/'tests/integration/carla')]
    audit=module('frozen_endurance_audit',source/'tests/integration/perception/audit_paired_v1.py').audit
    case=json.loads((a.bundle/'case.json').read_text())
    assert case['freeze_sha256']==sha(a.series/'sources.json')
    run=a.work/'run';run.mkdir()
    manifest=json.loads((a.bundle/'run-manifest.json').read_text())
    checked_members(a.bundle/manifest['archive'],manifest,run)
    assert json.loads((run/'server.json').read_text())['freeze_sha256']==case['freeze_sha256']
    result=run/'capture/paired/renderer/result.json'
    raw=json.loads(result.read_text())['raw'] if result.exists() else []
    from raw_archive_stream_v1 import inspect as inspect_raw
    archives=json.loads((a.bundle/'raw-manifest.json').read_text())['archives']
    if len({m['archive'] for m in archives})!=len(archives):raise ValueError('duplicate raw archive')
    originals=[Path(m['original']).name for m in archives]
    if len(set(originals))!=len(originals):raise ValueError('duplicate original raw archive')
    if {r['archive'] for r in raw}!=set(originals):raise ValueError('complete raw archives')
    for m in archives:
        rows=[r for r in raw if r['archive']==Path(m['original']).name]
        assert all((r['width'],r['height'])==(2560,1536) for r in rows)
        # Includes complete tar bytes, members, decoded BGRA and RGB identities,
        # even when the original physical verdict is FAIL.
        inspect_raw(a.bundle/m['archive'],m,frames=rows)
        relative=Path(m['original']);assert not relative.is_absolute() and '..' not in relative.parts
        p=run/relative;p.parent.mkdir(parents=True,exist_ok=True);os.symlink((a.bundle/m['archive']).resolve(),p)
    exclusions=json.loads((a.bundle/'future-exclusion.json').read_text());prior=a.bundle/exclusions['prior']
    assert sha(prior)==exclusions['prior_sha256'] and exclusions['holdout_access'] is False
    expected=set(json.loads(prior.read_text())['rgb_sha256']);expected.update(row['rgb_sha256'] for row in raw)
    assert sorted(expected)==exclusions['rgb_sha256'] and len(expected)==exclusions['count'] and len(raw)==exclusions['new_raw_packets']
    try:actual=audit(run)
    except Exception as error:actual=dict(status='FAIL',error=str(error))
    recorded=json.loads((a.bundle/'audit.json').read_text())
    if actual['status']==recorded['status']=='FAIL':
        # File-not-found failures include the extraction location. Compare the
        # same original missing member, retaining all other exception text.
        expected_error=recorded['error'].replace(case['run'],'<run>')
        actual_error=actual['error'].replace(str(run),'<run>')
        assert actual_error==expected_error,'original failure changed'
    else:assert actual==recorded,'original verdict changed'
    summary=dict(status='PASS',case_verdict=actual['status'],source_files=len(frozen['files']),raw_packets=len(raw),future_exclusion=len(expected))
    (a.work/'validation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('series','bundle','work'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
