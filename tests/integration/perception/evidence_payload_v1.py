"""Resolve materialized evidence or a canonical Git LFS pointer in a local cache."""

import hashlib
from pathlib import Path
import re


POINTER = re.compile(
    rb"version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n"
)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def payload(path, expected_sha, expected_size, media_root=None):
    path = Path(path)
    if (
        not re.fullmatch("[0-9a-f]{64}", expected_sha)
        or type(expected_size) is not int
        or expected_size < 0
    ):
        raise ValueError("payload identity")
    if path.stat().st_size < 256:
        pointer = POINTER.fullmatch(path.read_bytes())
        if pointer:
            oid, size = pointer[1].decode(), int(pointer[2])
            if oid != expected_sha or size != expected_size or media_root is None:
                raise ValueError("pointer identity/cache required")
            path = Path(media_root) / oid[:2] / oid[2:4] / oid
    if path.stat().st_size != expected_size or digest(path) != expected_sha:
        raise ValueError("payload size/hash mismatch")
    return path
