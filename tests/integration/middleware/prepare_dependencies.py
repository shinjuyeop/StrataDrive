#!/usr/bin/env python3
"""Fetch/verify the two pinned optional M4 probe dependencies into an explicit directory."""
import argparse, hashlib, io, json, subprocess, tarfile, urllib.request, zipfile
from pathlib import Path
INPUTS=[
    {'name':'cyclonedds','version':'11.0.1','url':'https://api.github.com/repos/eclipse-cyclonedds/cyclonedds/tarball/11.0.1','sha256':'472a0aade963891961ee8fd52ed02d138c6eedf288856e020090f8eb662948a5'},
    {'name':'zenoh-c','version':'1.10.1','url':'https://github.com/eclipse-zenoh/zenoh-c/releases/download/1.10.1/zenoh-c-1.10.1-x86_64-unknown-linux-gnu-standalone.zip','sha256':'9ee0f2d732b0f3042a7e1cd3076042a2bc3ac0415587c40bc3ed7b8b62fbde11'},
]
def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();root=a.output.resolve();root.mkdir(parents=True,exist_ok=False)
    (root/'inputs.json').write_text(json.dumps(INPUTS,indent=2)+'\n')
    for item in INPUTS:
        data=urllib.request.urlopen(item['url'],timeout=120).read()
        if hashlib.sha256(data).hexdigest()!=item['sha256']:raise RuntimeError('dependency SHA mismatch: '+item['name'])
        dest=root/item['name'];dest.mkdir()
        (root/(item['name']+('.tar.gz' if item['name']=='cyclonedds' else '.zip'))).write_bytes(data)
        if item['name']=='cyclonedds':
            with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                for member in archive.getmembers():
                    if not (dest/member.name).resolve().is_relative_to(dest):raise ValueError('archive path')
                archive.extractall(dest)
        else:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:archive.extractall(dest)
    source=next((root/'cyclonedds').iterdir())
    commands=[['cmake','-S',str(source),'-B',str(root/'cyclone-build'),'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_PREFIX='+str(root/'install'),'-DBUILD_TESTING=OFF','-DBUILD_EXAMPLES=OFF','-DBUILD_DDSPERF=OFF','-DENABLE_SECURITY=OFF','-DENABLE_ICEORYX=OFF'],['cmake','--build',str(root/'cyclone-build'),'-j4'],['cmake','--install',str(root/'cyclone-build')]]
    (root/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    for i,cmd in enumerate(commands):
        with (root/f'build-{i}.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':main()
