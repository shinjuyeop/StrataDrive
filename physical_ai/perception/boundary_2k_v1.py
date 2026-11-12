"""Opt-in original-time publication for the typed native2K C++ boundary.

The live owner adds no image work, inference wait or IO to the consumer. Text
encoding below is an offline Host replay adapter, NOT a production IPC protocol.
"""

from dataclasses import dataclass

from .async_native_2k_v1 import NativeResult
from .contract import LIFETIME_NS, UINT64_MAX, uint
from .world_async_2k_v1 import WorldAsyncPerception


@dataclass(frozen=True)
class Publication:
    result: NativeResult
    wall_clock: int
    received_wall_ns: int
    wall_expires_ns: int

    def validate(self):
        if type(self.result) is not NativeResult:
            raise ValueError("exact native2K result required")
        self.result.validate()
        if not (
            uint(self.wall_clock, positive=True)
            and uint(self.received_wall_ns, UINT64_MAX - LIFETIME_NS)
            and uint(self.wall_expires_ns)
            and self.wall_expires_ns == self.received_wall_ns + LIFETIME_NS
        ):
            raise ValueError("original callback clock/receipt/expiry required")


@dataclass(frozen=True)
class BoundaryObservation:
    publication: Publication | None
    source_ns: int | None
    wall_ns: int
    state_received_wall_ns: int


class BoundaryWorldPerception(WorldAsyncPerception):
    """Same prepared2K inference owner, with an atomic original-time export.

    wall_clock is a trusted run/monotonic-domain identity supplied at setup,
    never a timestamp or something inferred from model output. Receivers on
    another host require an explicit clock mapping; they cannot reuse this ID.
    """

    def __init__(self, backend, clock, wall_clock, wall_now=None):
        if not uint(wall_clock, positive=True):
            raise ValueError("trusted wall clock identity required")
        self._boundary_wall_clock = wall_clock
        super().__init__(backend, clock, wall_now)

    def boundary_observation(self):
        with self._condition:
            # The inherited condition uses an RLock. No second sampling of the
            # result/deadline outside it, and no lookup in a diagnostic trace.
            sample = self.observation()
            result = sample["result"]
            publication = None
            if result is not None:
                # This value was stored by the inference owner from the original
                # BgraPacket receipt. It is not the publication or read time.
                publication = Publication(
                    result,
                    self._boundary_wall_clock,
                    self._current_wall_expiry - LIFETIME_NS,
                    self._current_wall_expiry,
                )
            return BoundaryObservation(
                publication,
                sample["source_ns"],
                sample["wall_ns"],
                sample["state"]["received_wall_ns"],
            )


def frame_line(publication, source_now_ns, wall_now_ns, state_received_wall_ns):
    """Lossless Host replay only; C++ independently validates every field."""
    if type(publication) is not Publication:
        raise ValueError("typed publication required")
    publication.validate()
    if not all(uint(v) for v in (source_now_ns, wall_now_ns, state_received_wall_ns)):
        raise ValueError("trusted current clocks required")
    r = publication.result
    i = r.identity
    fields = [
        "F", source_now_ns, wall_now_ns, state_received_wall_ns,
        1, 1, i.epoch, i.clock_instance, publication.wall_clock,
        i.frame, i.source_ns, r.expires_ns,
        publication.received_wall_ns, publication.wall_expires_ns,
        i.camera_id, i.calibration_revision, r.width, r.height,
        1, r.model_sha256, len(r.detections),
    ]
    for d in r.detections:
        fields.extend((d.class_id, d.score, *d.box))
    return " ".join(map(str, fields))


class ReplayCursor:
    """A repeated consumer read is a poll, never a newly acquired frame.

    Construct a new cursor after a trusted session change. Do not clear it on
    unavailability: a repeated old publication must not resurrect a lost frame.
    """

    def __init__(self):
        self._last = None

    def line(self, observation):
        if type(observation) is not BoundaryObservation or observation.source_ns is None:
            raise ValueError("no trusted source clock; report unavailable at the control owner")
        now = (observation.source_ns, observation.wall_ns, observation.state_received_wall_ns)
        if not all(uint(v) for v in now):
            raise ValueError("invalid observation clocks")
        if observation.publication is None:
            return "U " + " ".join(map(str, now))
        observation.publication.validate()
        if observation.publication == self._last:
            return "P " + " ".join(map(str, now))
        encoded = frame_line(observation.publication, *now)
        self._last = observation.publication
        return encoded
