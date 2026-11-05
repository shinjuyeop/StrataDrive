#!/usr/bin/env python3
"""Independent reader for the epoch-free Linux bootstrap incident spool v1."""
import argparse
import json
from pathlib import Path
import re
import struct
import zlib

MAGIC=b'SDBOOT\x00\x01'
OPERATIONS={1:'epoch-initialize',2:'journal-initialize',3:'journal-open',4:'epoch-issue'}
ROLES={0:'supervisor',1:'central',2:'front',3:'rear'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def decode(data):
    require(len(data)==320,'record size')
    require(data[:8]==MAGIC,'record format')
    require(zlib.crc32(data[:316])==struct.unpack_from('<I',data,316)[0],'record CRC')
    kind,operation,role=data[8:11]
    require(kind in (1,2,3) and operation in OPERATIONS and role in ROLES,'record enum')
    pid,began,observed=struct.unpack_from('<IQQ',data,12)
    size=struct.unpack_from('<H',data,64)[0]
    require(pid>0 and began>0 and observed>=began,'record clock/pid')
    require(size<=240 and data[66] in (0,1) and (not data[66] or size==240),'message bounds')
    require(not data[11] and not data[67] and not any(data[68+size:316]),'reserved/padding')
    require(any(data[32:48]) and any(data[48:64]),'missing identity')
    if kind!=3:
        require(size==0 and data[66]==0,'unexpected message')
    if kind==1:
        require(began==observed,'begin timestamp')
    return {'kind':kind,'operation':OPERATIONS[operation],'role':ROLES[role],
            'pid':pid,'began_ns':began,'observed_ns':observed,'attempt':data[32:48].hex(),
            'boot_id':data[48:64].hex(),'message':data[68:68+size].decode('utf-8',errors='replace'),
            'message_truncated':bool(data[66]),'application_epoch':None}


def plain(path):
    require(not path.is_symlink() and path.is_file(),'not a regular record: '+str(path))
    return path.read_bytes()


def audit(root):
    require(not root.is_symlink() and root.is_dir(),'spool directory')
    require(plain(root/'format')==MAGIC,'spool format')
    rows=[]
    for folder in sorted(root.iterdir()):
        if folder.name=='format':
            continue
        require(re.fullmatch('[0-9a-f]{32}',folder.name) is not None and
                not folder.is_symlink() and folder.is_dir(),'attempt directory')
        files={p.name for p in folder.iterdir()}
        require(files in ({'begin'},{'begin','outcome'}),'incomplete or unexpected files: '+str(folder))
        begin=decode(plain(folder/'begin'))
        require(begin['kind']==1 and begin['attempt']==folder.name,'begin binding')
        row=dict(begin,status='interrupted')
        if 'outcome' in files:
            end=decode(plain(folder/'outcome'))
            require(end['kind'] in (2,3),'outcome kind')
            require(all(end[key]==begin[key] for key in
                        ('operation','role','pid','began_ns','attempt','boot_id')),'outcome binding')
            row=dict(end,status='succeeded' if end['kind']==2 else 'failed')
        rows.append(row)
    counts={status:sum(row['status']==status for row in rows) for status in ('succeeded','failed','interrupted')}
    return {'schema':'bootstrap-incidents-v1','integrity':True,'attempts':len(rows),
            **counts,'all_succeeded':bool(rows) and counts['succeeded']==len(rows),'records':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spool',type=Path)
    args=parser.parse_args()
    try:
        print(json.dumps(audit(args.spool),indent=2))
    except (OSError,ValueError) as error:
        print(json.dumps({'integrity':False,'error':str(error)}))
        raise SystemExit(1)
