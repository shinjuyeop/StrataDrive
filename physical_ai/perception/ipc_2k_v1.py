"""Private, bounded nonblocking shadow IPC. No remote-clock conversion or control."""

import socket
import struct

from .boundary_2k_v1 import BoundaryObservation, BoundaryWorldPerception
from .contract import uint

HEADER = struct.Struct("<8sIIQIIQQQQQQ")
RESULT = struct.Struct("<IIQQQQQIIIIII32s")
DETECTION = struct.Struct("<II5d")
MAX_BYTES = 184 + 48 * 100


class IpcWorldPerception(BoundaryWorldPerception):
    def ipc_observation(self):
        with self._condition:
            sample = self.boundary_observation()
            return sample, self._clock.status()["frame"]


def socket_pair():
    pair = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    for sock in pair:
        sock.setblocking(False)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 16384)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16384)
    return pair


def encode(observation, *, sequence, epoch, source_clock, wall_clock, state_frame, sender_wall_ns, repeated=False):
    if type(observation) is not BoundaryObservation:
        raise ValueError("atomic boundary observation required")
    for v in (sequence, source_clock, wall_clock):
        if not uint(v, positive=True):
            raise ValueError("sequence/trusted clock identity")
    if not uint(epoch, 2**32 - 1, True) or not uint(state_frame) or not uint(sender_wall_ns):
        raise ValueError("trusted epoch/state/clock")
    if observation.source_ns is None:
        if observation.publication is not None:
            raise ValueError("publication without trusted state")
        state_frame = source = receipt = 0
    else:
        source, receipt = observation.source_ns, observation.state_received_wall_ns
        if not uint(source) or not uint(receipt) or not state_frame:
            raise ValueError("actual state identity")
    p = observation.publication
    kind = 0 if p is None else 1 if repeated else 2
    data = HEADER.pack(b"S2KPIPC1", 1, kind, sequence, epoch, 0, source_clock, wall_clock,
                       sender_wall_ns, state_frame, source, receipt)
    if p is not None:
        p.validate()
        r, i = p.result, p.result.identity
        if (i.epoch, i.clock_instance, p.wall_clock) != (epoch, source_clock, wall_clock):
            raise ValueError("publication differs from trusted IPC session")
        if not repeated:
            data += RESULT.pack(1, 1, i.frame, i.source_ns, r.expires_ns, p.received_wall_ns, p.wall_expires_ns,
                                i.camera_id, i.calibration_revision, r.width, r.height, 1, len(r.detections),
                                bytes.fromhex(r.model_sha256))
            data += b"".join(DETECTION.pack(d.class_id, 0, d.score, *d.box) for d in r.detections)
    if len(data) > MAX_BYTES:
        raise ValueError("bounded IPC payload")
    return data


class Publisher:
    """One observer/IO owner. A full socket is a recorded drop, never a wait.

    Duplicates become polls only AFTER a successful send of the same publication.
    Neither a send failure nor an unavailable observation advances that cache.
    Keep the published bytes in the finite run recorder outside control code.
    """

    def __init__(self, sock, epoch, source_clock, wall_clock):
        if sock.getblocking() or sock.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_SEQPACKET:
            raise ValueError("nonblocking private seqpacket required")
        self.socket, self.epoch, self.source_clock, self.wall_clock = sock, epoch, source_clock, wall_clock
        self.sequence = self.sent = self.dropped = 0
        self.closed = False
        self._last = None

    def send(self, observation, state_frame, wall_ns):
        self.sequence += 1
        data = encode(observation, sequence=self.sequence, epoch=self.epoch, source_clock=self.source_clock,
                      wall_clock=self.wall_clock, state_frame=state_frame, sender_wall_ns=wall_ns,
                      repeated=observation.publication is not None and observation.publication == self._last)
        try:
            if self.closed:
                raise BrokenPipeError("closed peer")
            written = self.socket.send(data, socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL)
            if written != len(data):
                raise RuntimeError("seqpacket partial write")
        except BlockingIOError:
            self.dropped += 1
            return data, "full"
        except (BrokenPipeError, ConnectionResetError):
            self.closed = True
            self.dropped += 1
            return data, "disconnected"
        self.sent += 1
        if observation.publication is not None:
            self._last = observation.publication
        return data, "sent"
