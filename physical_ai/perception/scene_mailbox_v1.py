"""Private Host snapshot prototype: one in flight and one pending latest.

This carries immutable kinematics, not a camera result or actuation permission.
The caller must bind a complete scene inventory/configuration before live use.
No CARLA clock is converted to wall time. Each endpoint has one mutation owner.
"""
from dataclasses import dataclass
import math
import socket
import struct
import threading

from .contract import LIFETIME_NS, uint

MAX_ACTORS = 128
HEADER = struct.Struct('<8sIII16sQQQQQQQ32s32s')
ACTOR = struct.Struct('<Q13d')
ACK = struct.Struct('<8sQ')
MAX_BYTES = HEADER.size + MAX_ACTORS * ACTOR.size


@dataclass(frozen=True)
class SceneBinding:
    epoch: int
    run: bytes
    world: int
    generation: int
    step_ns: int
    scene_sha256: bytes
    model_sha256: bytes
    actor_ids: tuple

    def __post_init__(self):
        if (not uint(self.epoch,2**32-1,True) or type(self.run) is not bytes or len(self.run)!=16
                or not any(self.run) or not uint(self.world,positive=True) or not uint(self.generation,positive=True)
                or type(self.step_ns) is not int or self.step_ns not in (5_000_000,10_000_000)
                or any(type(x) is not bytes or len(x)!=32 for x in (self.scene_sha256,self.model_sha256))
                or type(self.actor_ids) is not tuple or not 1<=len(self.actor_ids)<=MAX_ACTORS
                or not all(uint(x,positive=True) for x in self.actor_ids)
                or tuple(sorted(set(self.actor_ids)))!=self.actor_ids):
            raise ValueError('trusted scene binding/inventory')


@dataclass(frozen=True)
class ActorPose:
    actor_id: int
    position_m: tuple
    quaternion_xyzw: tuple
    velocity_m_s: tuple
    angular_velocity_rad_s: tuple

    def __post_init__(self):
        if not uint(self.actor_id,positive=True):raise ValueError('actor identity')
        for values,size in ((self.position_m,3),(self.quaternion_xyzw,4),(self.velocity_m_s,3),(self.angular_velocity_rad_s,3)):
            if type(values) is not tuple or len(values)!=size or any(type(x) not in (int,float) or not math.isfinite(x) for x in values):
                raise ValueError('immutable finite actor kinematics')
        if abs(sum(x*x for x in self.quaternion_xyzw)-1)>1e-4:raise ValueError('unit quaternion')


@dataclass(frozen=True)
class SceneSnapshot:
    binding: SceneBinding
    frame: int
    source_ns: int
    acquired_begin_ns: int
    acquired_end_ns: int
    actors: tuple

    def __post_init__(self):
        if (type(self.binding) is not SceneBinding or not all(uint(v,positive=True) for v in
                (self.frame,self.source_ns,self.acquired_begin_ns,self.acquired_end_ns))
                or self.acquired_end_ns<self.acquired_begin_ns or type(self.actors) is not tuple
                or not all(type(x) is ActorPose for x in self.actors)
                or tuple(x.actor_id for x in self.actors)!=self.binding.actor_ids):
            raise ValueError('complete immutable physical snapshot')

    def fresh(self,now):
        if not uint(now) or self.acquired_end_ns>now:raise ValueError('original wall acquisition bracket')
        return now-self.acquired_begin_ns<LIFETIME_NS


def encode(snapshot):
    if type(snapshot) is not SceneSnapshot:raise ValueError('typed physical snapshot')
    b=snapshot.binding
    data=HEADER.pack(b'SDSCENE1',1,len(snapshot.actors),b.epoch,b.run,b.world,b.generation,b.step_ns,
                     snapshot.frame,snapshot.source_ns,snapshot.acquired_begin_ns,snapshot.acquired_end_ns,
                     b.scene_sha256,b.model_sha256)
    return data+b''.join(ACTOR.pack(p.actor_id,*p.position_m,*p.quaternion_xyzw,*p.velocity_m_s,*p.angular_velocity_rad_s) for p in snapshot.actors)


def decode(data,binding):
    if type(binding) is not SceneBinding:raise ValueError('trusted scene binding')
    if len(data)<HEADER.size or len(data)>MAX_BYTES:raise ValueError('bounded scene packet')
    magic,version,count,epoch,run,world,generation,step,frame,source,begin,end,scene,model=HEADER.unpack_from(data)
    if (magic!=b'SDSCENE1' or version!=1 or count!=len(binding.actor_ids)
            or len(data)!=HEADER.size+count*ACTOR.size
            or (epoch,run,world,generation,step,scene,model)!=(binding.epoch,binding.run,binding.world,binding.generation,binding.step_ns,binding.scene_sha256,binding.model_sha256)):
        raise ValueError('scene session/configuration/length')
    actors=[]
    for i in range(count):
        actor,*v=ACTOR.unpack_from(data,HEADER.size+i*ACTOR.size)
        actors.append(ActorPose(actor,tuple(v[:3]),tuple(v[3:7]),tuple(v[7:10]),tuple(v[10:])))
    return SceneSnapshot(binding,frame,source,begin,end,tuple(actors))


def socket_pair():
    pair=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
    for sock in pair:
        sock.setblocking(False)
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,2*MAX_BYTES)
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,2*MAX_BYTES)
    return pair


class _Endpoint:
    def __init__(self,sock,binding):
        if (sock.family!=socket.AF_UNIX or sock.getsockopt(socket.SOL_SOCKET,socket.SO_TYPE)!=socket.SOCK_SEQPACKET
                or sock.getblocking() or type(binding) is not SceneBinding):raise ValueError('private nonblocking scene endpoint')
        self.sock,self.binding=sock,binding
        self.closed=False;self.error='';self._owner=threading.get_ident();self._last_wall=0

    def _check(self,now):
        if threading.get_ident()!=self._owner:raise ValueError('single endpoint mutation owner')
        if not uint(now) or now<self._last_wall:self._fail('wall clock regression')
        self._last_wall=now

    def _fail(self,reason):
        self.error=reason;self.close();raise ValueError(reason)

    def close(self):
        self.closed=True;self.sock.close()


class ScenePublisher(_Endpoint):
    def __init__(self,sock,binding):
        super().__init__(sock,binding)
        self.pending=None;self.inflight=0;self.last=None
        self.offered=self.sent=self.replaced=self.expired=0

    def offer(self,snapshot,now):
        self._check(now)
        if self.closed:return False
        if type(snapshot) is not SceneSnapshot or snapshot.binding!=self.binding:self._fail('snapshot binding')
        if self.last is not None:
            frame,source,end=self.last;gap=snapshot.frame-frame
            if (gap<=0 or snapshot.acquired_begin_ns<=end
                    or abs(snapshot.source_ns-source-gap*self.binding.step_ns)>gap*1000):self._fail('snapshot sequence/source regression')
        try:fresh=snapshot.fresh(now)
        except ValueError:self._fail('future snapshot acquisition')
        self.last=(snapshot.frame,snapshot.source_ns,snapshot.acquired_end_ns);self.offered+=1
        if self.pending is not None:self.replaced+=1
        self.pending=snapshot if fresh else None
        if not fresh:self.expired+=1
        self.pump(now)
        return fresh and not self.closed

    def pump(self,now):
        self._check(now)
        if self.closed:return
        try:
            data,_,flags,_=self.sock.recvmsg(ACK.size+1)
            if not data:self.close();return
            if flags&socket.MSG_TRUNC or len(data)!=ACK.size:self._fail('ack length')
            magic,frame=ACK.unpack(data)
            if magic!=b'SDSCACK1' or not self.inflight or frame!=self.inflight:self._fail('ack sequence')
            self.inflight=0
        except BlockingIOError:pass
        except (BrokenPipeError,ConnectionResetError):self.close();return
        if self.inflight or self.pending is None:return
        if not self.pending.fresh(now):self.pending=None;self.expired+=1;return
        data=encode(self.pending)
        try:
            if self.sock.send(data)!=len(data):self._fail('partial scene packet')
        except BlockingIOError:return
        except (BrokenPipeError,ConnectionResetError):self.close();return
        self.inflight=self.pending.frame;self.pending=None;self.sent+=1

    def close(self):
        self.pending=None;self.inflight=0
        super().close()


class SceneConsumer(_Endpoint):
    def __init__(self,sock,binding):
        super().__init__(sock,binding)
        self.active=None;self.received=self.expired=0;self._last=None;self._ack=0

    def take(self,now):
        self._check(now)
        if self.closed:return None
        if self.active is not None:raise ValueError('release current render snapshot first')
        if self._ack:self._send_ack()
        if self._ack or self.closed:return None
        try:
            data,_,flags,_=self.sock.recvmsg(MAX_BYTES+1)
            if not data:self.close();return None
            if flags&socket.MSG_TRUNC:self._fail('truncated scene packet')
            snapshot=decode(data,self.binding)
            if self._last is not None:
                frame,source,end=self._last;gap=snapshot.frame-frame
                if (gap<=0 or snapshot.acquired_begin_ns<=end
                        or abs(snapshot.source_ns-source-gap*self.binding.step_ns)>gap*1000):
                    self._fail('received scene regression')
            fresh=snapshot.fresh(now)
        except BlockingIOError:return None
        except (BrokenPipeError,ConnectionResetError):self.close();return None
        except ValueError as error:self._fail(str(error))
        self.received+=1;self._last=(snapshot.frame,snapshot.source_ns,snapshot.acquired_end_ns);self.active=snapshot
        if not fresh:self.expired+=1;self.release();return None
        return snapshot

    def current(self,now):
        self._check(now)
        if self.closed or self.active is None:return None
        try:
            data=self.sock.recv(1,socket.MSG_PEEK)
            if not data:self.close();return None
            self._fail('unsolicited scene while active')
        except BlockingIOError:pass
        except (BrokenPipeError,ConnectionResetError):self.close();return None
        if not self.active.fresh(now):self.expired+=1;self.release();return None
        return self.active

    def _send_ack(self):
        if self.closed or not self._ack:return
        try:
            data=ACK.pack(b'SDSCACK1',self._ack)
            if self.sock.send(data)!=len(data):self._fail('partial scene acknowledgement')
            self._ack=0
        except BlockingIOError:pass
        except (BrokenPipeError,ConnectionResetError):self.close()

    def release(self):
        if threading.get_ident()!=self._owner:raise ValueError('single endpoint mutation owner')
        if self.active is not None:self._ack=self.active.frame;self.active=None
        self._send_ack()

    def close(self):
        self.active=None;self._ack=0
        super().close()
