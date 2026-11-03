#!/usr/bin/env python3
"""Pinned SDK over isolated IP namespaces; live logical owner is a separate clock."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import struct
import subprocess
import sys
import time
import run as base

ROOT = base.ROOT
HERE = Path(__file__).resolve()
CASES = ('normal', 'loss', 'drop-ack', 'restart')


def config(role, generation):
    name = 'diag-source' if role == 'publisher' else 'diag-replica'
    return {'unicast': '10.89.0.'+('1' if role == 'publisher' else '2'), 'netmask': '255.255.255.252',
            'network': 'sd-m9-'+role, 'routing': name,
            'applications': [{'name': name, 'id': hex(0x2211 if role == 'publisher' else 0x2220+generation),
                              'threads': 2, 'max_dispatchers': 1, 'max_dispatch_time': 100}],
            'logging': {'level': 'warning', 'console': 'true', 'dlt': 'false'},
            'max-payload-size-reliable': 2048, 'max-payload-size-local': 4096,
            'endpoint-queue-limit-external': 16384, 'endpoint-queue-limit-local': 16384,
            'services': [{'service': '0x5d10' if role == 'publisher' else '0x5d11', 'instance': '0x0001',
                          'reliable': {'port': 40510 if role == 'publisher' else 40511, 'enable-magic-cookies': 'false'}}],
            'service-discovery': {'enable': 'true', 'multicast': '239.255.9.1', 'port': 30499, 'protocol': 'udp',
                                  'initial_delay_min': 10, 'initial_delay_max': 50, 'repetitions_base_delay': 100,
                                  'repetitions_max': 3, 'ttl': 3, 'cyclic_offer_delay': 500}}


def capture(folder):
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, stop)
    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3)); sock.bind(('sdc', 0)); sock.settimeout(.1)
    count = 0
    with (folder/'traffic.pcap').open('wb') as out:
        out.write(struct.pack('<IHHIIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)); (folder/'capture.ready').touch()
        while running:
            try: frame = sock.recv(65535)
            except socket.timeout: continue
            if len(frame) < 34 or frame[12:14] != b'\x08\x00': continue
            stamp = time.time_ns(); out.write(struct.pack('<IIII', stamp//10**9, (stamp//1000)%10**6, len(frame), len(frame))); out.write(frame); count += 1
    sock.close(); base.save(folder/'capture.json', {'ip_packets': count, 'normal_exit': True})


def inside(folder, binary, case):
    processes = []; streams = []; recorder = None
    result = {'case': case, 'pass': False, 'forced_cleanup': [], 'processes': [],
              'clock_sample': {'wall_ns': time.time_ns(), 'monotonic_ns': time.monotonic_ns()}}
    def call(args): return subprocess.check_output(list(map(str, args)), stderr=subprocess.STDOUT, text=True)
    def launch(role, generation=1):
        name = f'{role}-{generation}'; cfg = folder/(name+'.config.json'); base.save(cfg, config(role, generation))
        env = dict(os.environ, VSOMEIP_CONFIGURATION=str(cfg), VSOMEIP_APPLICATION_NAME='diag-source' if role == 'publisher' else 'diag-replica',
                   LD_LIBRARY_PATH=str(binary.parents[4]/'install/lib'), ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1', TSAN_OPTIONS='halt_on_error=0:exitcode=66')
        cmd = ['ip', 'netns', 'exec', role, 'unshare', '-m', sys.executable, str(HERE), '--node', str(binary), role, str(folder), case, str(generation)]
        base.save(folder/(name+'.command.json'), {'argv': cmd, 'env': {k: env[k] for k in env if k.startswith(('VSOMEIP', 'LD_LIBRARY', 'ASAN', 'UBSAN', 'TSAN'))}})
        out = (folder/(name+'.stdout')).open('w'); err = (folder/(name+'.stderr')).open('w'); streams.extend([out, err])
        p = subprocess.Popen(cmd, stdout=out, stderr=err, env=env); processes.append((role, generation, p))
        return p
    def wait(predicate, timeout=60):
        deadline = time.monotonic()+timeout
        while not predicate():
            if any(role == 'publisher' and p.poll() is not None for role, _, p in processes): raise RuntimeError('publisher exited before expected marker')
            if time.monotonic() >= deadline: raise TimeoutError('expected live transition')
            time.sleep(.005)
    def snapshot(role, generation, p):
        threads = []
        for t in Path(f'/proc/{p.pid}/task').iterdir():
            try: threads.append(dict(tid=int(t.name), name=(t/'comm').read_text().strip(), affinity=sorted(os.sched_getaffinity(int(t.name))),
                                     policy=os.sched_getscheduler(int(t.name)), priority=os.sched_getparam(int(t.name)).sched_priority))
            except ProcessLookupError: pass
        base.save(folder/f'{role}-{generation}.runtime.json', dict(pid=p.pid, netns=os.readlink(f'/proc/{p.pid}/ns/net'), threads=threads))
        (folder/f'{role}-{generation}.maps').write_text(Path(f'/proc/{p.pid}/maps').read_text())
        (folder/f'{role}-{generation}.sockets.txt').write_text(call(['ip', 'netns', 'exec', role, 'ss', '-antup']))
    try:
        call(['mount', '-t', 'tmpfs', 'tmpfs', '/run'])
        for role in ('publisher', 'replica'): call(['ip', 'netns', 'add', role])
        call(['ip', 'link', 'add', 'sdc', 'type', 'veth', 'peer', 'name', 'sdr'])
        for role, dev, ip in [('publisher', 'sdc', '10.89.0.1/30'), ('replica', 'sdr', '10.89.0.2/30')]:
            call(['ip', 'link', 'set', dev, 'netns', role])
            for args in (['link', 'set', 'lo', 'up'], ['addr', 'add', ip, 'dev', dev], ['link', 'set', dev, 'up'], ['route', 'add', '224.0.0.0/4', 'dev', dev]):
                call(['ip', 'netns', 'exec', role, 'ip', *args])
            (folder/(role+'.network.txt')).write_text(call(['ip', 'netns', 'exec', role, 'ip', '-details', 'addr']))
        with (folder/'bootstrap.log').open('w') as log:
            subprocess.run([str(binary), 'bootstrap', str(folder), case, '1'], check=True, stdout=log, stderr=subprocess.STDOUT)
        err = (folder/'capture.stderr').open('w'); streams.append(err)
        recorder = subprocess.Popen(['ip', 'netns', 'exec', 'publisher', sys.executable, str(HERE), '--capture', str(folder)], stderr=err)
        base.wait_for(lambda: (folder/'capture.ready').exists())
        receiver = launch('replica'); publisher = launch('publisher')
        wait(lambda: (folder/'publisher.csv').exists()); snapshot('publisher', 1, publisher); snapshot('replica', 1, receiver)
        if case == 'restart':
            wait(lambda: (folder/'restart-needed').exists(), 30)
            result['injected_replica_kill'] = {'pid': receiver.pid, 'monotonic_ns': time.monotonic_ns()}
            receiver.kill(); receiver.wait(timeout=5)
            shutil.copytree(folder/'replica-store', folder/'replica-before-restart')
            receiver = launch('replica', 2)
            base.wait_for(lambda: (folder/'replica-2.csv').exists() or receiver.poll() is not None, 10)
            if receiver.poll() is not None: raise RuntimeError('replacement failed')
            snapshot('replica', 2, receiver)
        wait(lambda: (folder/'publisher-done').exists(), 60); publisher.wait(timeout=5)
        (folder/'finish').touch(); receiver.wait(timeout=10)
        result['pass'] = publisher.returncode == receiver.returncode == 0 and (folder/'replica-done').exists()
    except Exception as error:
        result['error'] = repr(error)
    finally:
        for role, generation, p in processes:
            if p.poll() is None: result['forced_cleanup'].append(f'{role}-{generation}'); p.kill(); p.wait()
            result['processes'].append({'role': role, 'generation': generation, 'pid': p.pid, 'exit': p.returncode})
        if recorder is not None:
            if recorder.poll() is None: recorder.send_signal(signal.SIGINT)
            try: recorder.wait(timeout=5)
            except subprocess.TimeoutExpired: recorder.kill(); recorder.wait(); result['forced_cleanup'].append('capture')
            result['capture_exit'] = recorder.returncode
        for stream in streams: stream.close()
        result['sanitizer_errors'] = [p.name for p in folder.iterdir() if p.suffix in ('.stdout', '.stderr') and base.sanitizer_errors(p.read_text())]
        result['pass'] = result['pass'] and not result['forced_cleanup'] and not result['sanitizer_errors'] and result.get('capture_exit') == 0
        base.save(folder/'result.json', result)
    return 0 if result['pass'] else 1


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--inside', nargs=3); parser.add_argument('--node', nargs=5); parser.add_argument('--capture', type=Path)
    parser.add_argument('--profile', choices=('normal', 'asan', 'tsan'), default='normal'); parser.add_argument('--cases', nargs='+', choices=CASES, default=list(CASES))
    parser.add_argument('output', nargs='?', type=Path); args = parser.parse_args()
    if args.capture: return capture(args.capture)
    if args.node:
        subprocess.run(['mount', '-t', 'tmpfs', 'tmpfs', '/tmp'], check=True); subprocess.run(['mount', '-t', 'tmpfs', 'tmpfs', '/dev/shm'], check=True)
        os.execv(args.node[0], args.node)
    if args.inside: return inside(Path(args.inside[0]), Path(args.inside[1]), args.inside[2])
    folder = args.output.resolve(); folder.mkdir(parents=True, exist_ok=False)
    binary = ROOT/f'build/m5-someip-{args.profile}/project/tests/integration/someip/someip_diagnostics_live'
    with base.open_lock() as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        base.save(folder/'plan.json', dict(profile=args.profile, cases=args.cases, timeout_s=80, base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                                         binary=str(binary), binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
        results = []
        for case in args.cases:
            dest = folder/case; dest.mkdir()
            code = base.supervise(['unshare', '-Urnm', sys.executable, str(HERE), '--inside', str(dest), str(binary), case], dest, 80)
            results.append(dict(case=case, exit=code)); base.save(folder/'results.json', results)
    return 0 if all(row['exit'] == 0 for row in results) else 1


if __name__ == '__main__': sys.exit(main())
