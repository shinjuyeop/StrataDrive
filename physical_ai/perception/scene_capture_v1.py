"""Same-frame actor-root capture joined to original native physics receipts.

This is a live kinematic scene exporter, not complete visual-state admission.
Wheel/bone/material state is deliberately not inferred from actor transforms.
"""
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import math
import uuid

from .scene_mailbox_v1 import ActorPose, SceneBinding, SceneSnapshot
from .contract import uint

MAX_OBSERVATIONS = 64
MAX_WORLD_ACTORS = 4096


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def quaternion(pitch, yaw, roll):
    """CARLA degrees: Rz(yaw) Ry(-pitch) Rx(-roll)."""
    p, y, r = (math.radians(v) / 2 for v in (-pitch, yaw, -roll))
    cp, sp, cy, sy, cr, sr = math.cos(p), math.sin(p), math.cos(y), math.sin(y), math.cos(r), math.sin(r)
    return (sr*cp*cy-cr*sp*sy, cr*sp*cy+sr*cp*sy,
            cr*cp*sy-sr*sp*cy, cr*cp*cy+sr*sp*sy)


def matrix(position, q):
    x,y,z,w=q
    return ((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),position[0]),
            (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),position[1]),
            (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y),position[2]),(0.,0.,0.,1.))


def multiply(a,b):
    return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)) for i in range(4))


def inverse(a):
    return tuple(tuple(a[j][i] for j in range(3))+(-sum(a[j][i]*a[j][3] for j in range(3)),)
                 for i in range(3))+((0.,0.,0.,1.),)


def geometry_matrix(value):
    if value['scale'] != [1.,1.,1.]:
        raise ValueError('nonunit body/actor geometry scale is unsupported')
    pose=ActorPose(1,tuple(value['translation_m']),tuple(value['quaternion_xyzw']),(0.,)*3,(0.,)*3)
    return matrix(pose.position_m,pose.quaternion_xyzw)


def body_to_actor(geometry):
    if not geometry['valid']:
        raise ValueError('verified rest geometry required')
    return multiply(inverse(geometry_matrix(geometry['body_world'])),geometry_matrix(geometry['actor_world']))


@dataclass(frozen=True)
class ActorObservation:
    world: int
    frame: int
    source_ns: int
    step_ns: int
    callback_begin_ns: int
    callback_end_ns: int
    inventory: tuple
    actors: tuple

    def __post_init__(self):
        if (not all(uint(v,positive=True) for v in (self.world,self.frame,self.source_ns,self.step_ns,
                                                   self.callback_begin_ns,self.callback_end_ns))
                or self.callback_end_ns<self.callback_begin_ns
                or type(self.inventory) is not tuple or not 1<=len(self.inventory)<=MAX_WORLD_ACTORS
                or any(not uint(v,positive=True) for v in self.inventory)
                or tuple(sorted(set(self.inventory)))!=self.inventory
                or type(self.actors) is not tuple or not self.actors
                or not all(type(p) is ActorPose for p in self.actors)
                or tuple(sorted(set(p.actor_id for p in self.actors)))!=tuple(p.actor_id for p in self.actors)
                or not set(p.actor_id for p in self.actors)<=set(self.inventory)):
            raise ValueError('immutable same-frame actor observation')


def observe(snapshot, actor_ids, begin, end_clock):
    """Read only the supplied immutable SDK snapshot, never Actor.get_transform()."""
    actors=[]
    for actor_id in actor_ids:
        state=snapshot.find(actor_id)
        if state is None:raise ValueError('declared actor absent from same-frame snapshot')
        t=state.get_transform();v=state.get_velocity();a=state.get_angular_velocity()
        actors.append(ActorPose(actor_id,(t.location.x,t.location.y,t.location.z),
            quaternion(t.rotation.pitch,t.rotation.yaw,t.rotation.roll),
            (v.x,v.y,v.z),tuple(math.radians(x) for x in (a.x,a.y,a.z))))
    return ActorObservation(snapshot.id,snapshot.frame,round(snapshot.timestamp.elapsed_seconds*1e9),
        round(snapshot.timestamp.delta_seconds*1e9),begin,end_clock(),
        tuple(sorted(s.id for s in snapshot)),tuple(actors))


class ReceiptSceneJoiner:
    """Caller holds one short lock; missing/evicted frame is rejected, not filled."""
    def __init__(self,binding,inventory,ego_id,session,geometry):
        if (type(binding) is not SceneBinding or ego_id not in binding.actor_ids
                or type(inventory) is not tuple or tuple(sorted(set(inventory)))!=inventory
                or not set(binding.actor_ids)<=set(inventory) or not uint(session,positive=True)
                or int(geometry['generation'])!=binding.generation):
            raise ValueError('trusted source catalog/session')
        self.binding,self.inventory,self.ego_id,self.session=binding,inventory,ego_id,session
        self.body_to_actor=body_to_actor(geometry)
        self.observations=OrderedDict();self.last=None;self.last_export=0
        self.evicted=self.joined=self.missing=0;self.failed=False

    def add(self,observation):
        b=self.binding;o=observation
        try:
            if (self.failed or type(o) is not ActorObservation or o.world!=b.world
                    or abs(o.step_ns-b.step_ns)>1000 or o.inventory!=self.inventory
                    or tuple(p.actor_id for p in o.actors)!=b.actor_ids):
                raise ValueError('scene world/inventory/period mismatch')
            if self.last:
                gap=o.frame-self.last.frame
                if (gap<=0 or o.callback_begin_ns<self.last.callback_end_ns
                        or abs(o.source_ns-self.last.source_ns-gap*b.step_ns)>gap*1000):
                    raise ValueError('scene frame/source/callback regression')
            self.last=o;self.observations[o.frame]=o
            if len(self.observations)>MAX_OBSERVATIONS:self.observations.popitem(last=False);self.evicted+=1
        except ValueError:
            self.failed=True;self.observations.clear();raise

    def join(self,receipt,now):
        if self.failed:raise ValueError('latched scene capture')
        try:
            return self._join(receipt,now)
        except (KeyError,TypeError,ValueError,OverflowError) as error:
            self.failed=True;self.observations.clear()
            raise ValueError('invalid original physical receipt: '+str(error)) from error

    def _join(self,receipt,now):
        b=self.binding;r=receipt
        if (uuid.UUID(r['run']).bytes!=b.run or int(r['session'])!=self.session
                or int(r['actor'])!=self.ego_id or int(r['physics_generation'])!=b.generation
                or r['model_sha256']!=b.model_sha256.hex() or int(r['model_step_ns'])!=b.step_ns
                or r['interval_work_valid'] is not True or r['inputs_cleared_after_physics'] is not True):
            self.failed=True;raise ValueError('original physical receipt identity/work')
        frame=int(r['frame'])
        if frame<=self.last_export:return None
        o=self.observations.get(frame)
        if o is None:self.missing+=1;return None
        begin=int(r['physics_acquisition_begin_ns']);end=int(r['physics_acquisition_end_ns'])
        if (o.source_ns!=round(r['simulation_end_seconds']*1e9)
                or not 0<begin<=end<=o.callback_end_ns<=now):
            self.failed=True;raise ValueError('same-frame original source/acquisition order')
        body=r['physics'];ego=next(p for p in o.actors if p.actor_id==self.ego_id)
        body_pose=ActorPose(self.ego_id,tuple(body['body_world_position_m']),tuple(body['body_quaternion_xyzw']),
                            (0.,)*3,(0.,)*3)
        expected=multiply(matrix(body_pose.position_m,body_pose.quaternion_xyzw),self.body_to_actor)
        actual=matrix(ego.position_m,ego.quaternion_xyzw)
        error=max(abs(actual[i][j]-expected[i][j]) for i in range(4) for j in range(4))
        if error>1e-3:
            self.failed=True;raise ValueError('same-frame body-to-actor transform mismatch')
        self.last_export=frame;self.joined+=1
        # Conservative bracket starts at the original server physics acquisition;
        # SDK callback or later RPC query never renews scene age.
        return SceneSnapshot(b,frame,o.source_ns,begin,max(end,o.callback_end_ns),o.actors)


def catalog_digest(catalog):
    return hashlib.sha256(canonical(catalog)).digest()
