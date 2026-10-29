#!/usr/bin/env python3
"""Copy this evidence to a NEW directory and reassemble byte-identical gzip traces."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args()
    source=Path(__file__).resolve().parent;target=a.output.resolve()
    if target==source or source in target.parents:
        p.error('output must be outside the archived evidence directory')
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('*.part[0-9][0-9][0-9]'))
    for item in json.loads((source/'trace-parts.json').read_text()):
        path=target/item['path'];digest=hashlib.sha256();size=0
        if not path.resolve().is_relative_to(target):raise ValueError('invalid destination')
        with path.open('xb') as out:
            for name in item['parts']:
                part=(source/name).resolve()
                if not part.is_relative_to(source):raise ValueError('invalid part path')
                with part.open('rb') as f:
                    for block in iter(lambda:f.read(1024*1024),b''):
                        out.write(block);digest.update(block);size+=len(block)
        if digest.hexdigest()!=item['sha256'] or size!=item['bytes']:
            raise ValueError('restored trace checksum/size mismatch')
        print(item['path'],size,'SHA256 verified')


if __name__=='__main__':main()
