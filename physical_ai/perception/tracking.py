"""Observed image-space histories only: no depth, metric speed, or coasting."""

from collections import deque
from dataclasses import dataclass
import numpy as np
from .contract import PerceptionResult, LIFETIME_NS
from .yolox import iou


@dataclass(frozen=True)
class Observation:
    frame: int
    source_ns: int
    box: tuple[float, float, float, float]
    score: float


@dataclass(frozen=True)
class Track:
    track_id: int
    class_id: int
    observations: tuple[Observation, ...]


class ImageTracker:
    def __init__(self):
        self._session = None
        self._frame = self._source = 0
        self._next_id = 1
        self._tracks = ()

    def update(self, result: PerceptionResult):
        result.validate()
        identity = result.identity
        session = (
            identity.epoch,
            identity.clock_instance,
            identity.camera_id,
            identity.calibration_revision,
        )
        if (
            self._session is not None
            and session != self._session
            and identity.epoch <= self._session[0]
        ):
            raise ValueError("tracker session requires newer epoch")
        if session == self._session and (
            identity.frame <= self._frame or identity.source_ns <= self._source
        ):
            raise ValueError("tracker requires new acquisition")
        if session != self._session:
            self._tracks = ()
            self._next_id = 1
        elif identity.source_ns - self._source > LIFETIME_NS:
            self._tracks = ()
        self._session, self._frame, self._source = (
            session,
            identity.frame,
            identity.source_ns,
        )
        candidates = []
        for ti, track in enumerate(self._tracks):
            for di, detection in enumerate(result.detections):
                if track.class_id == detection.class_id:
                    overlap = float(
                        iou(
                            np.array(track.observations[-1].box),
                            np.array([detection.box]),
                        )[0]
                    )
                    if overlap >= 0.3:
                        candidates.append((-overlap, track.track_id, ti, di))
        assigned, used = {}, set()
        for _, _, ti, di in sorted(candidates):
            if ti not in used and di not in assigned:
                assigned[di] = self._tracks[ti]
                used.add(ti)
        current = []
        for index, detection in enumerate(result.detections):
            prior = assigned.get(index)
            history = deque(prior.observations if prior else (), maxlen=10)
            history.append(
                Observation(
                    identity.frame, identity.source_ns, detection.box, detection.score
                )
            )
            if prior:
                track_id = prior.track_id
            else:
                track_id = self._next_id
                self._next_id += 1
            current.append(Track(track_id, detection.class_id, tuple(history)))
        self._tracks = tuple(current)
        return self._tracks
