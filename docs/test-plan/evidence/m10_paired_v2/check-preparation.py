#!/usr/bin/env python3
"""Verify retained failed preparation phases; this never accepts a paired run."""
import hashlib,json,tarfile
from pathlib import Path

bundle=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
assert not (bundle/'case.json').exists(),'no paired case was declared'
frozen=json.loads((bundle/'sources.json').read_text())
assert sha((bundle/'sources.tar.gz').read_bytes())==frozen['archive_sha256']
phases=[]
for name in ('cache-manifest-01.json','cache-manifest-02.json','ddc-manifest-01.json','sync-cache-manifest-01.json','original-profile-cache-manifest-01.json'):
 manifest=json.loads((bundle/name).read_text());archive=bundle/manifest['archive']
 assert archive.stat().st_size==manifest['bytes'] and sha(archive.read_bytes())==manifest['sha256']
 with tarfile.open(archive,'r:*') as tar:
  members=tar.getmembers();assert len(members)==len(manifest['members']) and {m.name for m in members}==set(manifest['members'])
  for member in members:
   assert member.isfile();data=tar.extractfile(member).read();expected=manifest['members'][member.name]
   assert len(data)==expected['bytes'] and sha(data)==expected['sha256']
  report=json.loads(tar.extractfile('result.json').read());assert report['status']=='FAIL'
  assert report.get('raw_images',0)==0 and not any(m.name.endswith(('.bgra','.bgra.z','.npz')) for m in members)
  if name=='ddc-manifest-01.json':
   post=json.loads(tar.extractfile('map-integrity-after.json').read());assert post['status']=='PASS_UNCHANGED' and post['sha256']==report['map_sha256']
  if name=='original-profile-cache-manifest-01.json':
   probe=json.loads(tar.extractfile('fresh-client-probe.json').read())
   assert probe['last_frame']>probe['first_frame']>0 and not probe['actors']
   assert report['shutdown']['server_exit']==130 and not report['shutdown'].get('forced_stop')
  phases.append(dict(archive=archive.name,status=report['status'],members=len(members)))
exclusion=json.loads((bundle/'future-exclusion.json').read_text());prior=(bundle/exclusion['prior']).resolve()
assert sha(prior.read_bytes())==exclusion['prior_sha256']
assert exclusion['rgb_sha256']==json.loads(prior.read_text())['rgb_sha256'] and exclusion['count']==9035 and exclusion['new_raw_packets']==0
result=dict(status='PASS_RETAINED_PREPARATION_FAILURES',source_files=len(frozen['files']),phases=phases,paired_attempts=0,raw_images=0,future_exclusion=9035)
(bundle/'preparation-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
