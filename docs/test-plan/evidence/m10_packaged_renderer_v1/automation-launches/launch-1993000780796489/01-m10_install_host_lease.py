#!/usr/bin/python3 -I
"""Install/remove one root-owned, passwordless M10 boost lease command.

Run --plan without sudo to review the exact installation. The installed command
is the existing hash-pinned lease, with only its interpreter made isolated.
This installer never starts a lease or changes a CPU setting.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import tempfile

HELPER = Path('/usr/local/sbin/stratadrive-m10-boost-lease')
POLICY = Path('/etc/sudoers.d/stratadrive-m10-boost')
LOCK = Path('/run/stratadrive-m10-boost.lock')
SOURCE_SHA256 = '1904908d8c8a29aa2379fb75f0a10a0903776007ea7a429ab27ad7a74f8c4f15'


def payload(source):
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('Lease source differs from the reviewed fixed version.')
    if data.split(b'\n', 1)[0] != b'#!/usr/bin/env python3':
        raise ValueError('Unexpected lease interpreter.')
    return b'#!/usr/bin/python3 -I\n' + data.split(b'\n', 1)[1]


def account():
    uid = int(os.environ['SUDO_UID']) if os.geteuid() == 0 else os.getuid()
    user = pwd.getpwuid(uid)
    if uid == 0 or not re.fullmatch(r'[a-z_][a-z0-9_-]*', user.pw_name):
        raise ValueError('A normal local invoking user is required.')
    return user


def policy_bytes(username):
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*', username):
        raise ValueError('Unsupported username.')
    return ('# Managed by StrataDrive m10_install_host_lease.py; one fixed command.\n'
            f'{username} ALL=(root) NOPASSWD: NOSETENV: {HELPER}\n').encode()


def trusted_directory(path):
    for item in (path, *path.parents):
        info = item.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Expected a root-owned, non-writable directory: ' + str(item))


def existing_matches(path, data, mode):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
            or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != mode
            or path.read_bytes() != data):
        raise ValueError('Existing file differs; refusing to replace/remove it: ' + str(path))
    return True


def create_file(path, data, mode, validate=None):
    """Publish a complete file without overwriting an existing destination."""
    fd, name = tempfile.mkstemp(prefix='.stratadrive-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            os.fchown(stream.fileno(), 0, 0)
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        if validate:
            validate(temporary)
        os.link(temporary, path, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)


def visudo(path=None):
    argv = ['/usr/sbin/visudo', '-c']
    if path is not None:
        argv += ['-f', str(path)]
    subprocess.run(argv, check=True)


def check_passwordless(user):
    # -k with a command ignores cached credentials, so success proves that this
    # command works without the password entered for the installer itself.
    subprocess.run(['/usr/bin/sudo', '-n', '-k', str(HELPER), '--help'],
                   user=user.pw_uid, group=user.pw_gid, extra_groups=[], cwd='/',
                   env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C'},
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, check=True)


@contextmanager
def exclusive_guard():
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != 0 or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Lease lock identity.')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def install(user, data):
    rule = policy_bytes(user.pw_name)
    targets = [(HELPER, data, 0o755), (POLICY, rule, 0o440)]
    for path, content, mode in targets:
        trusted_directory(path.parent)
        existing_matches(path, content, mode)
    created = []
    visudo()
    try:
        for path, content, mode in targets:
            if not existing_matches(path, content, mode):
                create_file(path, content, mode, visudo if path == POLICY else None)
                created.append((path, content, mode))
        visudo()
        check_passwordless(user)
    except BaseException:
        # Revoke a newly added rule before removing its helper. Never overwrite
        # or remove another administrator's changed file during rollback.
        for path, content, mode in reversed(created):
            if existing_matches(path, content, mode):
                path.unlink()
        raise


def remove(user, data):
    targets = [(POLICY, policy_bytes(user.pw_name), 0o440), (HELPER, data, 0o755)]
    for path, content, mode in targets:
        trusted_directory(path.parent)
        existing_matches(path, content, mode)
    for path, content, mode in targets:
        if existing_matches(path, content, mode):
            path.unlink()
    visudo()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--plan', action='store_true')
    group.add_argument('--install', action='store_true')
    group.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    user = account()
    data = payload(Path(__file__).with_name('m10_boost_lease.py'))
    if args.plan:
        print(json.dumps(dict(user=user.pw_name, uid=user.pw_uid,
            helper=str(HELPER), helper_sha256=hashlib.sha256(data).hexdigest(),
            source_sha256=SOURCE_SHA256, policy=str(POLICY),
            rule=policy_bytes(user.pw_name).decode(), helper_mode='root:root 0755',
            policy_mode='root:root 0440', max_seconds=1800,
            cpu_action='max_perf_pct 100 -> 70 -> original100 only',
            installation_changes_cpu_settings=False), indent=2))
        return
    if os.geteuid() != 0:
        raise PermissionError('One-time installation/removal requires sudo.')
    with exclusive_guard():
        if args.install:
            install(user, data)
        else:
            remove(user, data)
    print('INSTALLED: passwordless helper verified; no trial started.' if args.install
          else 'REMOVED: dedicated rule and helper removed.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
