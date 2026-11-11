"""Bounded diagnostic raw writer; production inference mailbox remains latest1."""

from pathlib import Path
import queue
import threading
import time


class RawRecorder:
    def __init__(self, root, capacity=8):
        if type(capacity) is not int or not 1 <= capacity <= 16:
            raise ValueError("bounded recorder capacity")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.queue = queue.Queue(maxsize=capacity)
        self.lock = threading.Lock()
        self.records, self.errors, self.overflow = [], [], []
        self.offered = 0
        self.closed = False
        self.sentinel_queued = False
        self.thread = threading.Thread(
            target=self._run, name="native-raw-recorder", daemon=True
        )
        self.thread.start()

    def _write(self, row, raw):
        before = time.monotonic_ns()
        name = f"{row['frame']}.bgra"
        try:
            with (self.root / name).open("xb") as stream:
                if stream.write(raw) != len(raw):
                    raise OSError("incomplete raw recording")
            record = dict(
                row,
                path=name,
                raw_bytes=len(raw),
                write_begin_wall_ns=before,
                write_end_wall_ns=time.monotonic_ns(),
            )
            with self.lock:
                self.records.append(record)
        except Exception as error:
            with self.lock:
                self.errors.append(
                    dict(frame=row["frame"], error=f"{type(error).__name__}: {error}")
                )

    def offer(self, row, raw):
        if (
            type(raw) is not bytes
            or type(row.get("frame")) is not int
            or row["frame"] <= 0
        ):
            raise ValueError("immutable bytes and positive frame required")
        if self.closed:
            raise ValueError("recorder is closed")
        self.offered += 1
        try:
            self.queue.put_nowait((dict(row), raw))
            return True
        except queue.Full:
            # Overflow is an explicit failed run. Emergency synchronous writing
            # preserves this image rather than losing its future-exclusion hash.
            self.overflow.append(row["frame"])
            self._write(dict(row), raw)
            return False

    def _run(self):
        while True:
            value = self.queue.get()
            try:
                if value is None:
                    return
                self._write(*value)
            finally:
                self.queue.task_done()

    def close(self, timeout=30):
        until = time.monotonic() + timeout
        self.closed = True
        if not self.sentinel_queued:
            try:
                self.queue.put(None, timeout=timeout)
                self.sentinel_queued = True
            except queue.Full:
                return False
        self.thread.join(max(0, until - time.monotonic()))
        return not self.thread.is_alive()

    def report(self):
        with self.lock:
            return dict(
                offered=self.offered,
                records=sorted(self.records, key=lambda r: r["frame"]),
                errors=list(self.errors),
                overflow=list(self.overflow),
                capacity=self.queue.maxsize,
                stopped=not self.thread.is_alive(),
            )
