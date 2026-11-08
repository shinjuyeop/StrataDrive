"""Explicit, pinned, bounded artifact installation; never unpickle model input."""

import argparse
from pathlib import Path
import os
import tempfile
import urllib.request
from .contract import MODEL_BYTES, MODEL_SHA256, MODEL_URL, profile, sha256_file


def verify(path):
    path = Path(path)
    if path.stat().st_size != MODEL_BYTES or sha256_file(path) != MODEL_SHA256:
        raise ValueError("model size/SHA256 mismatch")
    return path


def fetch(destination):
    profile()
    destination = Path(destination)
    if destination.exists():
        return verify(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, delete=False
        ) as output:
            temporary = Path(output.name)
            with urllib.request.urlopen(MODEL_URL, timeout=60) as response:
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > MODEL_BYTES:
                        raise ValueError("oversized model download")
                    output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        verify(temporary)
        # Atomic exclusive publication; never replace another writer's artifact.
        os.link(temporary, destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(fetch(args.destination))


if __name__ == "__main__":
    main()
