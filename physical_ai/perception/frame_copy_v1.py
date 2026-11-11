"""One-use immutable snapshots; Host diagnostic capacity is not a deployment queue."""

import importlib.util
import threading

from .contract import sha256_file


class SnapshotPool:
    def __init__(self, library, digest, capacity=120):
        if type(capacity) is not int or not 1 <= capacity <= 120:
            raise ValueError("finite integer capacity1..120")
        if sha256_file(library) != digest:
            raise ValueError("pinned frame-copy library required")
        spec = importlib.util.spec_from_file_location("_frame_copy_v1", library)
        if spec is None or spec.loader is None:
            raise ValueError("loadable frame-copy library required")
        self._module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self._module)
        self._capsule = self._module.create(capacity)
        self._lock = threading.Lock()

    def copy(self, view, owner):
        # A local capsule reference pins all reserved/private destinations during
        # a concurrent close. The extension pins the view AND its SDK owner.
        with self._lock:
            capsule = self._capsule
        if capsule is None:
            raise ValueError("closed snapshot pool")
        return self._module.snapshot(capsule, view, owner)

    def stats(self):
        with self._lock:
            if self._capsule is None:
                raise ValueError("closed snapshot pool")
            return self._module.stats(self._capsule)

    def close(self):
        with self._lock:
            self._capsule = None
