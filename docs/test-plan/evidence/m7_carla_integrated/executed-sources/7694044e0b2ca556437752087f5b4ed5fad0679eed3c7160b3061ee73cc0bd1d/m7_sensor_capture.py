"""Bounded RGB/evaluation-only GT recorder; never supplies a VehicleRequest."""
import gzip
import hashlib
import threading
import time


class Capture:
    def __init__(self, output, drop_rgb=False):
        self.output = output
        self.drop_rgb = drop_rgb
        self.lock = threading.Lock()
        self.rows = {'rgb': [], 'gt': []}
        self.dropped = []
        self.errors = []
        self.sensors = []

    def attach(self, world, ego, carla):
        for name, kind in (('rgb', 'sensor.camera.rgb'), ('gt', 'sensor.camera.semantic_segmentation')):
            bp = world.get_blueprint_library().find(kind)
            for key, value in (('image_size_x', '320'), ('image_size_y', '240'), ('fov', '90'), ('sensor_tick', '0.05')):
                bp.set_attribute(key, value)
            bp.set_attribute('role_name','m7_frame5')
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=1.6, z=1.7), carla.Rotation(pitch=-8)), attach_to=ego)
            self.sensors.append(sensor)
            sensor.listen(self.callback(name, sensor.id, ego.id))

    def callback(self, name, sensor_id, ego_id):
        def receive(image):
            data = bytes(image.raw_data)
            row = dict(frame=image.frame, timestamp=image.timestamp, sensor_id=sensor_id, ego_id=ego_id,
                       source_identity='CARLA.'+name, validity='VALID', width=image.width,height=image.height,
                       format='BGRA8' if name=='rgb' else 'CARLA semantic tag in R channel',
                       use='perception record' if name=='rgb' else 'TRAIN_EVAL_ONLY',
                       sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),arrival_monotonic_ns=time.monotonic_ns())
            with self.lock:
                if len(self.rows[name])>=256:
                    self.errors.append('bounded camera buffer overflow');return
                if self.drop_rgb and name=='rgb' and len(self.rows[name])==40 and not self.dropped:
                    row['validity']='INJECTED_DELIVERY_DROP';self.dropped.append(row);return
                if self.rows[name] and row['frame']!=self.rows[name][-1]['frame']+5:
                    self.errors.append(name+' frame gap or duplicate')
                if not self.rows[name]:
                    with gzip.open(self.output/(name+'-first.bgra.gz'),'wb') as f:f.write(data)
                self.rows[name].append(row)
        return receive

    def snapshot(self):
        with self.lock:
            return dict(streams={k:list(v) for k,v in self.rows.items()},dropped=list(self.dropped),errors=list(self.errors),
                        sensor_tick_seconds=.05,gt_control_use=False)

    def stop(self):
        for sensor in self.sensors:
            if sensor.is_alive:sensor.stop()

    def destroy(self):
        for sensor in self.sensors:
            if sensor.is_alive:sensor.destroy()
