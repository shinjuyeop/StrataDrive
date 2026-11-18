"""Temporarily select the existing Town03 map in the stock shipping config."""
import hashlib
import os
from pathlib import Path
import stat
import subprocess

ORIGINAL='ff5dee93abb0e29054be6189fe3d530860019b91713824bd400c9f332810c00e'
OLD=b'GameDefaultMap=/Game/Carla/Maps/Town10HD_Opt.Town10HD_Opt'
NEW=b'GameDefaultMap=/Game/Carla/Maps/Town03_Opt.Town03_Opt'


def digest(data):return hashlib.sha256(data).hexdigest()


def stopped():
    if any(n.startswith('CarlaUE4-Linux') for n in subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()):
        raise RuntimeError('map configuration requires stopped stock renderer')


def candidate(original):
    if original.count(OLD)!=1 or NEW in original:
        raise ValueError('one known default map field')
    return original.replace(OLD,NEW)


def declare(path):
    path=Path(path)
    if not stat.S_ISREG(path.lstat().st_mode):raise ValueError('regular config, no symlink')
    data=path.read_bytes()
    if digest(data)!=ORIGINAL:raise ValueError('pinned original shipping configuration')
    return dict(path=str(path.resolve()),original_sha256=ORIGINAL,candidate_sha256=digest(candidate(data)),
                scope='only GameDefaultMap; existing Town03 asset bytes unchanged')


def install(declaration):
    stopped();path=Path(declaration['path']);backup=path.with_name(path.name+'.stratadrive-original')
    if backup.exists() or backup.is_symlink():raise ValueError('recover previous configuration first')
    if declare(path)!=declaration:raise ValueError('declared map configuration')
    original=path.read_bytes();info=path.stat();updated=candidate(original)
    # Preserve the original inode. The backup also survives a launcher crash.
    path.rename(backup)
    try:
        with path.open('xb') as stream:stream.write(updated);stream.flush();os.fsync(stream.fileno())
        os.chmod(path,stat.S_IMODE(info.st_mode))
    except BaseException:
        path.unlink(missing_ok=True);backup.rename(path);raise
    return dict(status='INSTALLED',**declaration,original_inode=info.st_ino,original_device=info.st_dev)


def restore(declaration):
    stopped();path=Path(declaration['path']);backup=path.with_name(path.name+'.stratadrive-original')
    if not backup.exists():
        if declare(path)!=declaration:raise ValueError('original configuration missing')
        return dict(status='PASS_ORIGINAL_CONFIG',sha256=ORIGINAL)
    if not stat.S_ISREG(backup.lstat().st_mode) or digest(backup.read_bytes())!=declaration['original_sha256']:
        raise ValueError('original configuration backup changed')
    if path.exists() or path.is_symlink():
        if not stat.S_ISREG(path.lstat().st_mode) or digest(path.read_bytes())!=declaration['candidate_sha256']:
            raise ValueError('unexpected config replacement; retain both files for review')
    info=backup.stat();backup.replace(path)
    return dict(status='PASS_ORIGINAL_CONFIG',sha256=digest(path.read_bytes()),inode=path.stat().st_ino,
                original_inode_retained=path.stat().st_ino==info.st_ino)
