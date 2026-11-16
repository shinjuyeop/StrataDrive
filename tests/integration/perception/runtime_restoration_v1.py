"""Guard repeated cleanup without weakening candidate identity checks."""
import hashlib
from pathlib import Path


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def restore_component(path, original, candidate, restore):
    before = sha(path)
    if before == original:
        return dict(status='ALREADY_ORIGINAL', command_exit=None, sha256=before)
    if before != candidate:
        raise ValueError('unknown installed runtime identity: ' + str(path))
    code = restore()
    after = sha(path)
    if code != 0 or after != original:
        raise RuntimeError('runtime restoration failed: ' + str(path))
    return dict(status='RESTORED', command_exit=code, sha256=after)
