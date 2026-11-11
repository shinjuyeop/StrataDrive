"""Finite Host diagnostic recorder; no normal disk writes during measurement."""

from collections import deque
from native_raw_recorder_v1 import RawRecorder


class MemoryRecorder:
    def __init__(self, root, capacity=240):
        if type(capacity) is not int or not 1 <= capacity <= 240:
            raise ValueError("finite memory capacity1..240")
        self.capacity = capacity
        self.root = root
        self.spill = RawRecorder(root, 8)
        self.pending = deque()
        self.offered = self.peak = self.raw_bytes = self.peak_bytes = 0
        self.closed = False
        self.overflow = []

    def offer(self, row, raw):
        if (
            self.closed
            or type(raw) is not bytes
            or type(row.get("frame")) is not int
            or row["frame"] <= 0
        ):
            raise ValueError(
                "open recorder, immutable bytes and positive frame required"
            )
        self.offered += 1
        if len(self.pending) < self.capacity:
            self.pending.append((dict(row), raw))
            self.raw_bytes += len(raw)
            self.peak_bytes = max(self.peak_bytes, self.raw_bytes)
            self.peak = max(self.peak, len(self.pending))
            return True
        # Unexpected extra input is an explicit failed run, still preserved.
        self.overflow.append(row["frame"])
        self.spill.offer(row, raw)
        return False

    def close(self, timeout=30):
        self.closed = True
        return self.spill.close(timeout)

    def report(self):
        spill = self.spill.report()
        records = [
            dict(row, raw_bytes=len(raw), storage="memory") for row, raw in self.pending
        ]
        records.extend(spill["records"])
        return dict(
            mode="finite-memory",
            offered=self.offered,
            records=sorted(records, key=lambda x: x["frame"]),
            capacity=self.capacity,
            peak_memory_frames=self.peak,
            peak_raw_bytes=self.peak_bytes,
            errors=spill["errors"],
            overflow=list(self.overflow),
            stopped=self.closed and spill["stopped"],
            disk_frames_during_measurement=spill["offered"],
        )

    def iter_raw(self):
        if not self.closed or not self.spill.report()["stopped"]:
            raise ValueError("recording must stop before archive reads")
        while self.pending:
            yield self.pending.popleft()
        for row in self.spill.report()["records"]:
            yield row, (self.spill.root / row["path"]).read_bytes()
