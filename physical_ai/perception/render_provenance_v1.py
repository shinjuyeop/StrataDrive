"""Separate-world image provenance. No conversion to the same-world ECU IPC.

An association proves which immutable kinematic snapshot a renderer was asked to
apply. It does not prove complete dynamic-scene fidelity. That separate admission
is deliberately unavailable until an authoritative scene exporter exists.
"""
from dataclasses import dataclass
import hashlib
from collections import OrderedDict

from .contract import LIFETIME_NS, uint
from .scene_mailbox_v1 import SceneBinding, SceneSnapshot, encode

WIDTH, HEIGHT = 2560, 1536
MAX_TICK_ASSOCIATIONS = 8


@dataclass(frozen=True)
class RenderSession:
    physical: SceneBinding
    renderer_instance: bytes
    renderer_world: int
    camera_id: int
    calibration_sha256: bytes

    def __post_init__(self):
        if (type(self.physical) is not SceneBinding
                or type(self.renderer_instance) is not bytes
                or len(self.renderer_instance) != 16 or not any(self.renderer_instance)
                or self.renderer_instance == self.physical.run
                or not uint(self.renderer_world, positive=True)
                or not uint(self.camera_id, positive=True)
                or type(self.calibration_sha256) is not bytes
                or len(self.calibration_sha256) != 32):
            raise ValueError('trusted separate renderer/camera identity')


@dataclass(frozen=True)
class RenderAssociation:
    session: RenderSession
    scene: SceneSnapshot
    renderer_frame: int
    renderer_source_ns: int
    apply_begin_ns: int
    apply_end_ns: int
    tick_begin_ns: int
    tick_end_ns: int

    def __post_init__(self):
        if (type(self.session) is not RenderSession or type(self.scene) is not SceneSnapshot
                or self.scene.binding != self.session.physical
                or not all(uint(v, positive=True) for v in (
                    self.renderer_frame, self.renderer_source_ns, self.apply_begin_ns,
                    self.apply_end_ns, self.tick_begin_ns, self.tick_end_ns))
                or not self.scene.acquired_end_ns <= self.apply_begin_ns <= self.apply_end_ns
                <= self.tick_begin_ns <= self.tick_end_ns):
            raise ValueError('original acquisition/application/tick provenance')

    @property
    def scene_sha256(self):
        return hashlib.sha256(encode(self.scene)).hexdigest()


@dataclass(frozen=True)
class RenderedImage:
    association: RenderAssociation
    received_wall_ns: int
    width: int
    height: int
    bgra: bytes

    def __post_init__(self):
        if (type(self.association) is not RenderAssociation
                or not uint(self.received_wall_ns, positive=True)
                # A callback can arrive before the tick RPC returns.
                or self.received_wall_ns < self.association.tick_begin_ns
                or type(self.width) is not int or type(self.height) is not int
                or (self.width, self.height) != (WIDTH, HEIGHT)
                or type(self.bgra) is not bytes or len(self.bgra) != WIDTH * HEIGHT * 4):
            raise ValueError('original renderer callback and native2K bytes')

    def unavailable_reason(self, physical_source_now_ns, state_received_wall_ns, now_ns):
        if (not all(uint(v, positive=True) for v in
                    (physical_source_now_ns, state_received_wall_ns, now_ns))
                or self.received_wall_ns > now_ns or state_received_wall_ns > now_ns):
            return 'clock_order'
        scene = self.association.scene
        if physical_source_now_ns < scene.source_ns:
            return 'physical_source_future'
        if physical_source_now_ns - scene.source_ns >= LIFETIME_NS:
            return 'physical_source_expired'
        if not scene.fresh(now_ns):
            return 'original_scene_expired'
        if now_ns - self.received_wall_ns >= LIFETIME_NS:
            return 'callback_expired'
        if now_ns - state_received_wall_ns >= LIFETIME_NS:
            return 'actual_state_expired'
        # Kinematics alone cannot authorize a complete rendered scene. Do not
        # add a caller-provided boolean to bypass this missing exporter.
        return 'complete_scene_export_unavailable'


class RenderAssociations:
    """Bounded tick history, mutated only by the render worker.

    SDK callbacks enqueue immutable bytes separately. The worker records the
    actual returned frame/source before looking up a callback. No frame is guessed
    from a tick request, and a dropped mapping can never be reconstructed later.
    """
    def __init__(self, session):
        if type(session) is not RenderSession:
            raise ValueError('trusted renderer session')
        self.session = session
        self._pending = OrderedDict()
        self._last = None
        self._last_scene = None
        self.evicted = self.consumed = 0
        self.closed = False

    def record(self, association):
        try:
            if self.closed or type(association) is not RenderAssociation or association.session != self.session:
                raise ValueError('renderer association identity')
            previous = self._last
            if previous and (association.renderer_frame <= previous.renderer_frame
                             or association.renderer_source_ns <= previous.renderer_source_ns
                             or association.tick_begin_ns < previous.tick_end_ns):
                raise ValueError('renderer frame/time regression')
            old = self._last_scene
            scene = association.scene
            if old is not None:
                if scene.frame == old.frame:
                    if scene != old:
                        raise ValueError('same physical frame with changed scene')
                else:
                    gap = scene.frame - old.frame
                    if (gap <= 0 or scene.acquired_begin_ns <= old.acquired_begin_ns
                            or scene.acquired_end_ns < old.acquired_end_ns
                            or abs(scene.source_ns - old.source_ns - gap * scene.binding.step_ns) > gap * 1000):
                        raise ValueError('physical scene regression')
            self._last = association
            self._last_scene = scene
            self._pending[association.renderer_frame] = association
            if len(self._pending) > MAX_TICK_ASSOCIATIONS:
                self._pending.popitem(last=False)
                self.evicted += 1
        except ValueError:
            self.close()
            raise

    def consume(self, *, renderer_instance, renderer_world, camera_id, frame,
                source_ns, received_wall_ns, width, height, bgra):
        if self.closed:
            return None
        if (renderer_instance, renderer_world, camera_id) != (
                self.session.renderer_instance, self.session.renderer_world, self.session.camera_id):
            self.close()
            raise ValueError('callback renderer/camera mismatch')
        association = self._pending.pop(frame, None)
        if association is None:
            return None
        try:
            if source_ns != association.renderer_source_ns:
                raise ValueError('callback frame/source mismatch')
            image = RenderedImage(association, received_wall_ns, width, height, bgra)
        except ValueError:
            self.close()
            raise
        self.consumed += 1
        return image

    def close(self):
        self.closed = True
        self._pending.clear()
