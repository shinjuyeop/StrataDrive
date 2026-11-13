"""Opt-in paired scene observer. It never owns a physical tick or control write."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import traceback
import uuid

from physical_ai.perception.scene_capture_v1 import ReceiptSceneJoiner, observe, catalog_digest
from physical_ai.perception.scene_mailbox_v1 import SceneBinding, ScenePublisher, encode, socket_pair
from paired_fault_v1 import STOP_INTERVAL,CRASH_INTERVAL,STALL_NS
from endurance_profile_v1 import limits

WEATHER_FIELDS=('cloudiness','precipitation','precipitation_deposits','wind_intensity',
    'sun_azimuth_angle','sun_altitude_angle','fog_density','fog_distance','fog_falloff',
    'wetness','scattering_intensity','mie_scattering_scale','rayleigh_scattering_scale','dust_storm')


def environment(world):
    weather=world.get_weather()
    lights=[dict(matrix=x.get_transform().get_matrix(),state=str(x.get_state()),frozen=x.is_frozen())
            for x in world.get_actors().filter('traffic.traffic_light')]
    return dict(weather={n:getattr(weather,n) for n in WEATHER_FIELDS if hasattr(weather,n)},
                traffic_lights=sorted(lights,key=lambda x:json.dumps(x['matrix'])))


def prepare_actors(world,ego,carla):
    """One declared parked vehicle and walker; no autonomous traffic controller."""
    extras=[]
    try:
        # SpawnActor returns before the SDK episode cache necessarily contains
        # the new ego. Its immediate Actor.get_transform() can still be identity.
        # This explicit preparation tick precedes native bind/START.
        frame=world.tick();snapshot=world.get_snapshot();state=snapshot.find(ego.id)
        if snapshot.frame!=frame or state is None:raise ValueError('ego preparation snapshot')
        pose=state.get_transform()
        for light in world.get_actors().filter('traffic.traffic_light'):
            light.set_state(carla.TrafficLightState.Red);light.freeze(True)
        bp=world.get_blueprint_library().find('vehicle.tesla.model3');bp.set_attribute('role_name','m10_static_car')
        parked=world.spawn_actor(bp,world.get_map().get_spawn_points()[1]);extras.append(parked)
        parked.set_simulate_physics(False)
        bp=world.get_blueprint_library().find('walker.pedestrian.0001')
        if bp.has_attribute('is_invincible'):bp.set_attribute('is_invincible','true')
        point=pose.transform(carla.Location(x=8,y=3,z=1));requested=carla.Transform(point,pose.rotation)
        walker=world.spawn_actor(bp,requested);extras.append(walker)
        walker.set_simulate_physics(False)
        return extras,dict(frame=frame,world=snapshot.id,ego_actor=ego.id,
            ego_matrix=pose.get_matrix(),walker_actor=walker.id,walker_requested_matrix=requested.get_matrix(),
            walker_relative_m=[8.,3.,1.],native_session_started=False,control_writes=0)
    except Exception:
        for actor in reversed(extras):actor.destroy()
        raise


class PairedCapture:
    def __init__(self,args,world,ego,binding,geometry):
        self.args,self.world=args,world
        self.bounds=limits(getattr(args,'endurance_seconds',0))
        self.root=args.output/'paired';self.root.mkdir()
        self.lock=threading.Lock();self.stopping=False;self.process=None;self.publisher=None;self.tick_id=None
        self.report=dict(schema='m10-paired-scene-source-v1',observations=[],exports=[],queries=[],events=[],errors=[],
                         query_timings=[],cleanup_errors=[],complete_visual_scene=False,perception_publications=0)
        self.poll_period_ns=1_000_000_000//args.paired_export_hz
        self.report['export_period_ns']=self.poll_period_ns
        self.report['endurance_seconds']=self.bounds['seconds']
        self.last_poll=0;self.stopped_at=None;self.resumed=False;self.exited=False
        # Keep a pidfd for the runner-owned renderer; PID reuse cannot retarget a fault.
        cmdline=Path(f'/proc/{args.paired_renderer_pid}/cmdline').read_bytes().split(b'\0')
        if b'-carla-rpc-port=2300' not in cmdline or not cmdline[0].endswith(b'/UE4Editor'):
            raise ValueError('expected dedicated renderer process')
        self.renderer_fd=os.pidfd_open(args.paired_renderer_pid)
        actors=sorted([a for a in world.get_actors() if a.type_id.startswith(('vehicle.','walker.'))],key=lambda a:a.id)
        if len(actors)!=3 or ego.id not in [a.id for a in actors]:raise ValueError('declared three-actor scene')
        ids=tuple(a.id for a in actors);snap=world.get_snapshot();now=time.monotonic_ns()
        initial=observe(snap,ids,now,time.monotonic_ns)
        road=world.get_map()
        self.catalog=dict(schema='m10-live-actor-catalog-v1',map=road.name,
            xodr_sha256=hashlib.sha256(road.to_opendrive().encode()).hexdigest(),
            source_world=world.id,ego_id=ego.id,world_actor_ids=list(initial.inventory),
            actors=[dict(id=a.id,blueprint=a.type_id,attributes=dict(a.attributes),
                         initial_pose=asdict(p)) for a,p in zip(actors,initial.actors)],
            environment=environment(world),geometry=geometry,
            actor_preparation=args.paired_actor_preparation,
            export_period_ns=self.poll_period_ns,
            camera_relative=dict(x=1.4,y=0.,z=1.7,pitch=0.,yaw=0.,roll=0.),
            visual_state_missing=['same-frame wheel/bone animation','material/asset-content verification'],
            scope='same-frame actor roots and frozen environment; diagnostic rendering, no visual admission')
        self.binding=SceneBinding(42,uuid.UUID(binding['run']).bytes,world.id,int(binding['physics']['generation']),
            5_000_000,catalog_digest(self.catalog),bytes.fromhex(binding['model_sha256']),ids)
        self.joiner=ReceiptSceneJoiner(self.binding,initial.inventory,ego.id,int(binding['session']),geometry)
        b=asdict(self.binding)
        for key in ('run','scene_sha256','model_sha256'):b[key]=b[key].hex()
        (self.root/'catalog.json').write_text(json.dumps(dict(catalog=self.catalog,binding=b),indent=2)+'\n')

    def start(self):
        tx,rx=socket_pair();self.publisher=ScenePublisher(tx,self.binding)
        try:
            command=[os.sys.executable,str(Path(__file__).with_name('carla_paired_renderer_v1.py')),
                '--catalog',str(self.root/'catalog.json'),'--socket-fd',str(rx.fileno()),
                '--server-pidfd',str(self.renderer_fd),
                '--port',str(self.args.paired_renderer_port),'--output',str(self.root/'renderer'),
                '--condition',self.args.paired_condition,'--detector',str(self.args.detector),
                '--endurance-seconds',str(self.bounds['seconds']),
                '--models',str(self.args.models),'--library',str(self.args.library)]
            self.log=(self.root/'renderer-client.log').open('w')
            env=dict(os.environ);env.pop('STRATADRIVE_M7_OWNER_KEY',None)
            self.process=subprocess.Popen(command,pass_fds=(rx.fileno(),self.renderer_fd),stdout=self.log,stderr=subprocess.STDOUT,env=env)
        finally:rx.close()
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            if self.process.poll() is not None:raise RuntimeError('renderer preparation failed; see renderer-client.log')
            if (self.root/'renderer/ready.json').exists():break
            time.sleep(.02)
        else:raise TimeoutError('bounded paired renderer preparation')
        self.tick_id=self.world.on_tick(self.observed)

    def observed(self,snapshot):
        begin=time.monotonic_ns()
        with self.lock:
            if self.stopping:return
            try:
                o=observe(snapshot,self.binding.actor_ids,begin,time.monotonic_ns)
                self.joiner.add(o)
                if len(self.report['observations'])>=self.bounds['observations']:raise ValueError('bounded paired observer')
                self.report['observations'].append(asdict(o))
            except Exception:self.report['errors'].append(traceback.format_exc());self.stopping=True

    def pump(self,status,rpc):
        now=time.monotonic_ns();count=int(status['wall_frames'])
        if self.report['errors']:raise RuntimeError('paired scene observer failed')
        if self.args.paired_condition in ('stall-exit','stall-crash'):
            crash=self.args.paired_condition=='stall-crash'
            if count>=(STOP_INTERVAL if crash else 120) and self.stopped_at is None:
                signal.pidfd_send_signal(self.renderer_fd,signal.SIGSTOP);self.stopped_at=now
                self.report['events'].append(dict(action='SIGSTOP',wall_ns=now,physical_intervals=count))
                self.save_events()
            if self.stopped_at and not self.resumed and crash:
                event=self.report['events'][0]
                if 'observed_stopped_ns' not in event:
                    stat=Path(f'/proc/{self.args.paired_renderer_pid}/stat').read_text()
                    state=stat[stat.rfind(')')+2:].split()[0]
                    if state=='T':
                        event.update(observed_stopped_ns=time.monotonic_ns(),observed_proc_state=state)
                        self.save_events()
            if self.stopped_at and not self.resumed and now-self.stopped_at>=STALL_NS:
                signal.pidfd_send_signal(self.renderer_fd,signal.SIGCONT);self.resumed=True
                self.report['events'].append(dict(action='SIGCONT',wall_ns=now,physical_intervals=count))
                self.save_events()
            if count>=(CRASH_INTERVAL if crash else 280) and self.resumed and not self.exited:
                signal.pidfd_send_signal(self.renderer_fd,signal.SIGKILL if crash else signal.SIGINT);self.exited=True
                self.report['events'].append(dict(action='SIGKILL' if crash else 'SIGINT',wall_ns=now,physical_intervals=count))
                self.save_events()
        if now-self.last_poll<self.poll_period_ns:return
        self.last_poll=now
        begin=time.monotonic_ns();response=rpc('receipt');end=time.monotonic_ns();receipt=response.get('receipt')
        self.report['query_timings'].append(dict(begin_ns=begin,end_ns=end,frame=receipt.get('frame') if receipt else None))
        if receipt is None:return
        with self.lock:scene=self.joiner.join(receipt,time.monotonic_ns())
        self.report['queries'].append(receipt)
        if scene is not None:
            at=time.monotonic_ns();offered=self.publisher.offer(scene,at)
            self.report['exports'].append(dict(frame=scene.frame,source_ns=scene.source_ns,
                acquired_begin_ns=scene.acquired_begin_ns,acquired_end_ns=scene.acquired_end_ns,
                offered_wall_ns=at,offered=offered,packet_hex=encode(scene).hex()))
        else:self.publisher.pump(time.monotonic_ns())

    def save_events(self):
        path=self.root/'control.tmp'
        path.write_text(json.dumps(self.report['events'])+'\n');path.replace(self.root/'control.json')

    def stop(self):
        if self.stopped_at and not self.resumed:
            try:signal.pidfd_send_signal(self.renderer_fd,signal.SIGCONT)
            except ProcessLookupError:pass
        if self.tick_id is not None:self.world.remove_on_tick(self.tick_id)
        with self.lock:self.stopping=True
        if self.publisher:
            self.report['publisher']=dict(sent=self.publisher.sent,replaced=self.publisher.replaced,
                expired=self.publisher.expired,closed=self.publisher.closed)
            self.publisher.close()
        if self.process:
            try:self.report['renderer_client_exit']=self.process.wait(timeout=45)
            except subprocess.TimeoutExpired:
                self.process.kill();self.process.wait();self.report['cleanup_errors'].append('renderer client forced stop')
            self.log.close()
        os.close(self.renderer_fd)
        self.report['joiner']=dict(joined=self.joiner.joined,missing=self.joiner.missing,evicted=self.joiner.evicted,
                                  body_to_actor=self.joiner.body_to_actor,failed=self.joiner.failed)
        self.report['environment_after']=environment(self.world)
        if self.report['environment_after']!=self.catalog['environment']:self.report['errors'].append('source environment changed')
        (self.root/'source.json').write_text(json.dumps(self.report,indent=2)+'\n')
