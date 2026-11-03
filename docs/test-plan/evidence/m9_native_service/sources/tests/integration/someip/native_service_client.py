"""Trusted finite local operator client, run inside the three-ECU supervisor."""
import json
import os
import socket
import struct
import time
from pathlib import Path


def run(folder, central):
    from run import wait_for
    folder = Path(folder)
    wait_for(lambda: (folder/'service-epoch-ready').exists() or central.poll() is not None, 5)
    if central.poll() is not None: raise RuntimeError('Central exited before service startup request')
    (folder/'service-epoch-request').write_text('explicit operator startup after Epoch2 NormalStop; service review never issues INIT')
    wait_for(lambda: (folder/'service-stop-ready').exists() or central.poll() is not None, 5)
    if central.poll() is not None: raise RuntimeError('Central exited before Epoch3 normal stop')
    (folder/'service-freeze').write_text(str(time.monotonic_ns()))
    for role in ('front', 'rear'):
        wait_for(lambda role=role: (folder/(role+'.service-frozen')).exists() or central.poll() is not None, 3)
        if not (folder/(role+'.service-frozen')).exists(): raise RuntimeError('source service freeze missing '+role)
    (folder/'service-collector-freeze').write_text(str(time.monotonic_ns()))
    wait_for(lambda: (folder/'service-ready.json').exists() or central.poll() is not None, 3)
    if not (folder/'service-ready.json').exists(): raise RuntimeError('service endpoint missing')
    ready = json.loads((folder/'service-ready.json').read_text());token = bytes.fromhex(os.environ['STRATADRIVE_SERVICE_CAPABILITY'])
    def request(number, revision, op=1, disposition=1, epoch=3, capability=token):
        return b'SDS\x01'+capability+struct.pack('<QQIQQQQBBH', number, 8001, epoch, 8001, (1 << 32)|8, 1, revision, op, disposition, 0)
    def exchange(raw):
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as s:
            s.settimeout(1);s.connect(ready['socket']);s.sendall(raw);data = s.recv(128)
        if len(data) != 32 or data[:4] != b'SDR\x01': raise RuntimeError('canonical service reply missing')
        number, watermark, revision, status, stage, blocked, reserved = struct.unpack('<QQQBBBB', data[4:])
        if reserved: raise RuntimeError('service response reserved')
        return dict(number=number, watermark=watermark, revision=revision, status=status, stage=stage, blocked=blocked)
    rows = []
    child = os.fork()
    if child == 0:
        try: ok = exchange(request(1, ready['revision']))['status'] == 1
        except Exception: ok = False
        os._exit(0 if ok else 1)
    _, status = os.waitpid(child, 0)
    if status: raise RuntimeError('unauthorized real PID was not refused')
    for label, raw, expected in [
        ('wrong-capability', request(1, ready['revision'], capability=bytes([token[0]^1])+token[1:]), 1),
        ('no-disposition', request(1, ready['revision'], disposition=0), 2),
        ('old-epoch', request(1, ready['revision'], epoch=2), 3),
        ('stale-revision', request(2, ready['revision']+1), 4),
        ('review', request(3, ready['revision']), 0),
        ('duplicate-review', request(3, ready['revision']), 0),
        ('conflicting-review', request(3, ready['revision']+1), 10)]:
        reply = exchange(raw);rows.append(dict(label=label, request=raw.hex(), reply=reply));
        (folder/'service-client.json').write_text(json.dumps(dict(pid=os.getpid(), unauthorized_pid=child, ready=ready, requests=rows), indent=2)+'\n')
        if reply['status'] != expected: raise RuntimeError('service '+label+' returned '+str(reply))
    approved = rows[-3]['reply']
    if approved['stage'] != 3 or rows[-2]['reply'] != approved: raise RuntimeError('Review/Passed receipt or duplicate changed')
    clear = request(4, approved['revision'], op=2, disposition=0);reply = exchange(clear);rows.append(dict(label='clear', request=clear.hex(), reply=reply))
    (folder/'service-client.json').write_text(json.dumps(dict(pid=os.getpid(), unauthorized_pid=child, ready=ready, requests=rows), indent=2)+'\n')
    if reply['status'] != 0 or reply['stage'] != 4: raise RuntimeError('explicit separate clear failed '+str(reply))
    return dict(pass_=True, epoch=3, authorized_pid=os.getpid(), unauthorized_pid=child, requests=len(rows)+1)
