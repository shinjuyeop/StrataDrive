"""Renderer-side kinematic application; never connects to an ECU or physical owner.

This intentionally does not call itself a complete scene adapter. Wheel animation,
other dynamic actors and immutable scene configuration require authoritative
same-frame capture before any resulting image can be admitted to perception.
"""
import math

from .scene_mailbox_v1 import ActorPose, SceneSnapshot


def carla_rotation(quaternion):
    """PhysX/UE quaternion to CARLA pitch/yaw/roll, using UE's axis convention."""
    x, y, z, w = quaternion
    # Rows of the quaternion's rotation matrix. CARLA's matrix is
    # Rz(yaw) Ry(-pitch) Rx(-roll), as in pinned LibCarla geom/Rotation.h.
    xx = 1 - 2 * (y*y + z*z)
    yx = 2 * (x*y + z*w)
    zx = 2 * (x*z - y*w)
    zy = 2 * (y*z + x*w)
    zz = 1 - 2 * (x*x + y*y)
    pitch = math.asin(max(-1., min(1., zx)))
    if abs(math.cos(pitch)) < 1e-7:
        # Gimbal lock: choose roll zero while preserving the rotation matrix.
        xy = 2 * (x*y - z*w)
        yy = 1 - 2 * (x*x + z*z)
        yaw, roll = math.atan2(-xy, yy), 0.
    else:
        yaw, roll = math.atan2(yx, xx), math.atan2(-zy, zz)
    return tuple(math.degrees(a) for a in (pitch, yaw, roll))


def transform(carla, pose):
    if type(pose) is not ActorPose:
        raise ValueError('original immutable actor pose')
    pitch, yaw, roll = carla_rotation(pose.quaternion_xyzw)
    return carla.Transform(carla.Location(*pose.position_m), carla.Rotation(pitch, yaw, roll))


def spawn_clone(world, carla, blueprint, spawn_pose, original_pose):
    """Create at a declared spawn point, then apply the settled pose without physics.

    CARLA's creation collision check can reject an already-settled body pose.
    The spawn transform is preparation only; it never replaces the source pose.
    """
    actor = world.spawn_actor(blueprint, spawn_pose)
    try:
        actor.set_simulate_physics(False)
        actor.set_transform(transform(carla, original_pose))
        return actor
    except Exception:
        actor.destroy()
        raise


class KinematicRenderer:
    """Apply an explicit source→clone mapping; every clone has physics disabled.

    Mapping IDs are world-local. No source ID is ever sent to the renderer as a
    destination ID, and no tick is issued by a batch mutation.
    """
    def __init__(self, client, world, carla, binding, clones):
        if tuple(sorted(clones)) != binding.actor_ids or len(set(a.id for a in clones.values())) != len(clones):
            raise ValueError('complete distinct source-to-renderer actor mapping')
        self.client, self.world, self.carla = client, world, carla
        self.binding, self.clones = binding, dict(clones)
        self.closed = False
        for actor in self.clones.values():
            actor.set_simulate_physics(False)

    def apply(self, scene):
        if self.closed or type(scene) is not SceneSnapshot or scene.binding != self.binding:
            raise ValueError('renderer scene binding')
        commands = [self.carla.command.ApplyTransform(self.clones[p.actor_id].id, transform(self.carla, p))
                    for p in scene.actors]
        responses = self.client.apply_batch_sync(commands, False)
        if len(responses) != len(commands) or any(r.has_error() for r in responses):
            self.closed = True
            raise ValueError('renderer transform batch rejected')

    def verify(self, scene, snapshot):
        """Read actual post-tick clone poses; fail instead of accepting teleport drift."""
        if self.closed or scene.binding != self.binding or snapshot.id != self.world.id:
            raise ValueError('renderer readback identity')
        readback = []
        for pose in scene.actors:
            state = snapshot.find(self.clones[pose.actor_id].id)
            if state is None:
                raise ValueError('renderer clone absent from actual snapshot')
            actual, expected = state.get_transform(), transform(self.carla, pose)
            matrix = actual.get_matrix()
            if (not all(math.isfinite(v) for row in matrix for v in row)
                    or max(abs(a-b) for ar, er in zip(matrix, expected.get_matrix())
                           for a, b in zip(ar, er)) > 1e-4):
                self.closed = True
                raise ValueError('renderer pose differs from original applied pose')
            readback.append(dict(source_actor_id=pose.actor_id, clone_actor_id=self.clones[pose.actor_id].id,
                                 actual_transform_matrix=matrix))
        return readback
