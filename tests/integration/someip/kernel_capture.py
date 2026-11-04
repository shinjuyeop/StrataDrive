#!/usr/bin/env python3
"""Opt-in Linux packet observation with kernel timestamps and clock brackets.

SO_TIMESTAMPNS_NEW reports system time, not CLOCK_MONOTONIC. Preserve a nearby
MONOTONIC/REALTIME/MONOTONIC bracket for every frame; never call the converted
value an exact kernel monotonic timestamp. Outgoing AF_PACKET observations are
not hardware transmission timestamps. No host-wide settings are changed.
"""
import csv
import json
import os
import platform
import signal
import socket
import struct
import time

TIMESTAMPNS_NEW=64  # Linux asm-generic/socket.h, __kernel_timespec (two s64)
CAPACITY=262144


def timestamp(ancillary,flags):
    if flags & (socket.MSG_TRUNC|socket.MSG_CTRUNC):raise ValueError('truncated packet or ancillary data')
    stamps=[data for level,kind,data in ancillary if level==socket.SOL_SOCKET and kind==TIMESTAMPNS_NEW]
    if len(stamps)!=1 or len(stamps[0])!=16:raise ValueError('missing or ambiguous kernel timestamp')
    sec,nsec=struct.unpack('=qq',stamps[0])
    if sec<=0 or not 0<=nsec<10**9:raise ValueError('invalid kernel timestamp')
    return sec*10**9+nsec


def capture(folder,device):
    if platform.system()!='Linux' or platform.machine()!='x86_64':
        raise RuntimeError('observation ABI qualified only on Linux x86_64')
    active=True;rows=[];peers={};count=0;error=None
    def stop(*_):
        nonlocal active
        active=False
    signal.signal(signal.SIGINT,stop)
    with socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(3)) as sock:
        sock.setsockopt(socket.SOL_SOCKET,TIMESTAMPNS_NEW,1)
        sock.bind((device,0));sock.settimeout(.1)
        sock.getsockopt(263,6,8)  # reset PACKET_STATISTICS after bind
        with (folder/'traffic.pcap').open('xb') as output:
            output.write(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1))
            (folder/'capture.ready').touch()
            try:
                while True:
                    try:frame,ancillary,flags,address=sock.recvmsg(65535,socket.CMSG_SPACE(16))
                    except socket.timeout:
                        if not active:break
                        continue
                    before=time.monotonic_ns();wall=time.time_ns();after=time.monotonic_ns()
                    stamp=timestamp(ancillary,flags)
                    if len(frame)<34 or frame[12:14]!=b'\x08\x00':continue
                    if len(rows)==CAPACITY:raise ValueError('kernel capture capacity exceeded')
                    rows.append((len(rows)+1,stamp,before,wall,after,address[2],len(frame)))
                    output.write(struct.pack('<IIII',stamp//10**9,(stamp//1000)%10**6,len(frame),len(frame)));output.write(frame)
                    iplen=(frame[14]&15)*4
                    if frame[23]==6 and len(frame)>=14+iplen+20:
                        tcp=14+iplen;ports=struct.unpack_from('!HH',frame,tcp)
                        size=struct.unpack_from('!H',frame,16)[0]-iplen-((frame[tcp+12]>>4)*4)
                        if 30501 in ports and size>0:count+=1
                        if size>0:
                            for ip in (frame[26:30],frame[30:34]):
                                address=socket.inet_ntoa(ip)
                                if address in ('10.88.0.2','10.88.0.3'):peers[address]=peers.get(address,0)+1
            except (OSError,ValueError) as exc:error=str(exc)
        packets,dropped=struct.unpack('=II',sock.getsockopt(263,6,8))
    with (folder/'packet-times.csv').open('x') as output:
        writer=csv.writer(output)
        writer.writerow(('frame','kernel_wall_ns','mono_before_ns','wall_ns','mono_after_ns','packet_type','bytes'))
        writer.writerows(rows)
    result={'timestamp_source':'SO_TIMESTAMPNS_NEW','clock':'CLOCK_REALTIME','interface':device,
            'affinity':sorted(os.sched_getaffinity(0)),'policy':os.sched_getscheduler(0),
            'rows':len(rows),'capacity':CAPACITY,'socket_packets':packets,'socket_drops':dropped,
            'ip_data_packets':count,'peer_data_packets':peers,'error':error,'normal_exit':error is None and dropped==0}
    (folder/'capture.json').write_text(json.dumps(result,indent=2)+'\n')
    return int(not result['normal_exit'])
