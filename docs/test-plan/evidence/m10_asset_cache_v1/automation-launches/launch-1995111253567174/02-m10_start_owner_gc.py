#!/usr/bin/env python3
"""Prepare renderer assets, authenticate, then start the GC trial with a fresh PID."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def check(root):
    series = root/'docs/test-plan/evidence/m10_asset_cache_v1'
    work = root/'build/m10-asset-cache-v1'
    if os.geteuid() == 0:
        raise RuntimeError('Run this launcher as your normal user, without sudo.')
    prepared = json.loads((series/'prepared.json').read_text())
    frozen = json.loads((series/'sources.json').read_text())
    if prepared['status'] != 'READY_FOR_EXPLICIT_HOST_LEASE':
        raise RuntimeError('Trial is not prepared.')
    runner = series/'run-sequence.py'; helper = root/'tools/m10_boost_lease.py'
    python = root/'build/m10-perception/cuda-venv/bin/python'
    if not python.is_file() or not os.access(python, os.X_OK):
        raise RuntimeError('Prepared Python environment is missing.')
    for path in (runner, helper, series/'prepare-assets.py'):
        expected = frozen['files'][str(path.relative_to(root))]['sha256']
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Frozen source changed: '+str(path))
    pending = [work/'experiment-owner.json', work/'sequence.log', work/'power-lease.jsonl',
               series/'sequence-disposition.json', series/'lease-activation.json',
               series/'sequence-restoration.json', *series.glob('normal-*')]
    if any(p.exists() or p.is_symlink() for p in pending):
        raise RuntimeError('A prior attempt exists; preserve and inspect it before restarting.')
    return series, work, runner, helper, python


def require_prepared(series):
    preparation = json.loads((series/'asset-preparation.json').read_text())
    age = time.monotonic_ns()-preparation['completed_wall_ns']
    if (preparation['status'] != 'PREPARED_NOT_PHYSICAL_ACCEPTANCE'
            or preparation['validation_only'] is not False
            or preparation['restoration']['status'] != 'PASS'
            or not 0 <= age <= 300_000_000_000):
        raise RuntimeError('Fresh asset preparation is missing or over 5 minutes old; run the launcher again.')


def run(root):
    series, work, runner, helper, python = check(root)
    # Lock is unprivileged and held across authentication and the entire sequence.
    with (work/'launcher.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print('먼저 빈 영상 서버의 자산을 준비합니다. 이 단계는 제어 시험에 포함하지 않습니다.', flush=True)
        subprocess.run([str(python), str(series/'prepare-assets.py')], cwd=root, check=True)
        require_prepared(series)
        print('sudo 인증 후 새 실행기를 시작합니다. 비밀번호는 sudo가 직접 받습니다.', flush=True)
        # Waiting at the password prompt must not consume the owner's 30min wait.
        subprocess.run(['/usr/bin/sudo', '-v'], check=True)
        check(root)
        require_prepared(series)  # do not reuse cold assets after a delayed password prompt
        with (work/'sequence.log').open('x') as output, (work/'power-lease.jsonl').open('x') as lease_log:
            owner = subprocess.Popen([str(python), str(runner)], cwd=root,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), stdin=subprocess.DEVNULL,
                stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            stopped = []
            def stop(*_):
                stopped.append(True)
                if owner.poll() is None:
                    owner.terminate()  # runner finishes current evidence and restores its runtime
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
                print(f'새 실행기 PID {owner.pid}: 30초 → 30초 → 5분 시험을 시작합니다.', flush=True)
                argv = ['/usr/bin/sudo', '-n', '/usr/bin/python3', str(helper),
                        '--owner-pid', str(owner.pid), '--seconds', '1800']
                with subprocess.Popen(argv, stdout=subprocess.PIPE, text=True) as lease:
                    for line in lease.stdout:
                        lease_log.write(line); lease_log.flush()
                        print(line, end='', flush=True)
                    lease_code = lease.wait()
                if lease_code:
                    raise RuntimeError(f'Host lease failed ({lease_code}); no automatic retry.')
                code = owner.wait()
                print(f'실행기 종료 코드 {code}. 판정: {series / "sequence-disposition.json"}', flush=True)
                return code
            finally:
                stop()
                owner.wait()
                for sig, handler in old.items():
                    signal.signal(sig, handler)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check', action='store_true', help='Check readiness without sudo or starting a process.')
    args = p.parse_args(); root = Path(__file__).resolve().parents[1]
    try:
        if args.check:
            check(root); print('READY: no process started and no host setting changed.')
        else:
            raise SystemExit(run(root))
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
