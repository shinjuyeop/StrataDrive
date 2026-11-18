#!/usr/bin/env python3
"""Run the existing frozen M10 sequence with the installed narrow host helper.

No interactive authentication, elevated Python interpreter or privileged
workspace script. --check only validates readiness and the helper's --help.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
import fcntl

from m10_install_host_lease import HELPER, payload, trusted_directory


def legacy(root):
    path = root/'tools/m10_start_owner_gc.py'
    spec = importlib.util.spec_from_file_location('m10_manual_launcher', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def helper_check(source):
    trusted_directory(HELPER.parent)
    info = HELPER.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
            or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o755
            or HELPER.read_bytes() != payload(source)):
        raise ValueError('Installed helper differs from the reviewed lease.')
    subprocess.run(['/usr/bin/sudo', '-n', '-k', str(HELPER), '--help'],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, check=True)


def check(root):
    manual = legacy(root)
    values = manual.check(root)
    series, work, runner, source, python = values
    frozen = json.loads((series/'sources.json').read_text())['files']
    launcher = root/'tools/m10_start_owner_gc.py'
    if hashlib.sha256(launcher.read_bytes()).hexdigest() != frozen[str(launcher.relative_to(root))]['sha256']:
        raise ValueError('Frozen manual launcher changed.')
    helper_check(source)
    return manual, values


def run(root):
    manual, (series, work, runner, source, python) = check(root)
    with (work/'launcher.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Record automation inputs separately; leave the original frozen source
        # archive and runtime untouched. Preserve each attempt, including setup failures.
        attempt = series/'automation-launches'/f'launch-{time.monotonic_ns()}'
        attempt.mkdir(parents=True)
        inputs = [Path(__file__).resolve(), root/'tools/m10_install_host_lease.py',
                  root/'tools/m10_start_owner_gc.py', source, HELPER]
        record = dict(status='PREPARING', helper=str(HELPER), source_files={},
                      scope='launch and host authorization only; unchanged frozen physical sequence')
        for index, path in enumerate(inputs):
            data = path.read_bytes()
            retained = f'{index:02d}-{path.name}'
            (attempt/retained).write_bytes(data)
            record['source_files'][str(path)] = dict(sha256=hashlib.sha256(data).hexdigest(), retained=retained)
        def save():
            (attempt/'invocation.json').write_text(json.dumps(record, indent=2)+'\n')
        save()
        try:
            subprocess.run([str(python), str(series/'prepare-assets.py')], cwd=root, check=True)
            manual.require_prepared(series)
            manual.check(root)
            helper_check(source)
            with (work/'sequence.log').open('x') as output, (work/'power-lease.jsonl').open('x') as lease_log:
                owner = subprocess.Popen([str(python), str(runner)], cwd=root,
                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), stdin=subprocess.DEVNULL,
                    stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                stopped = []
                def stop(*_):
                    stopped.append(True)
                    if owner.poll() is None:
                        owner.terminate()
                old = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
                try:
                    deadline = time.monotonic()+10
                    identity = None
                    while time.monotonic() < deadline and owner.poll() is None:
                        try:
                            identity = json.loads((work/'experiment-owner.json').read_text())
                        except (FileNotFoundError, json.JSONDecodeError):
                            time.sleep(.05)
                            continue
                        break
                    if stopped or owner.poll() is not None or not identity or identity['pid'] != owner.pid or identity['uid'] != os.getuid():
                        raise RuntimeError('Fresh owner did not become ready; see sequence.log.')
                    record.update(status='LEASE_REQUESTED', owner=identity)
                    save()
                    argv = ['/usr/bin/sudo', '-n', '-k', str(HELPER),
                            '--owner-pid', str(owner.pid), '--seconds', '1800']
                    with subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                          stdout=subprocess.PIPE, text=True) as lease:
                        for line in lease.stdout:
                            lease_log.write(line)
                            lease_log.flush()
                            print(line, end='', flush=True)
                        lease_code = lease.wait()
                    if lease_code:
                        raise RuntimeError(f'Host lease failed ({lease_code}); no automatic retry.')
                    code = owner.wait()
                    record.update(status='OWNER_EXITED_CHECK_ORIGINAL_DISPOSITION', owner_exit=code)
                    save()
                    return code
                finally:
                    stop()
                    owner.wait()
                    for sig, handler in old.items():
                        signal.signal(sig, handler)
        except BaseException as error:
            record.update(status='ERROR', error=str(error))
            save()
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if args.check:
            check(root)
            print('READY: passwordless helper checked; no trial or CPU change.')
        else:
            raise SystemExit(run(root))
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
