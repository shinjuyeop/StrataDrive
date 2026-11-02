"""Bounded RGB/evaluation-only GT recorder; never supplies a VehicleRequest."""
import gzip
import hashlib
import threading
import time


class Capture:
    def __init__(self, output, drop_rgb=False, capacity=256, record_video=False, live_view=False):
        if not 1 <= capacity <= 1201:
            raise ValueError('bounded sensor recording capacity')
        self.record_video = record_video
        self.live_view = live_view
        self.latest_rgb = None
        self.viewer = None
        self.video_file = None
        self.capacity = capacity
        self.output = output
        self.drop_rgb = drop_rgb
        self.lock = threading.Lock()
        self.rows = {'rgb': [], 'gt': []}
        self.dropped = []
        self.errors = []
        self.sensors = []

    def attach(self, world, ego, carla):
        if self.live_view:
            self.viewer = LiveView()
        for name, kind in (('rgb', 'sensor.camera.rgb'), ('gt', 'sensor.camera.semantic_segmentation')):
            bp = world.get_blueprint_library().find(kind)
            video_rgb = (self.record_video or self.live_view) and name == 'rgb'
            for key, value in (('image_size_x', '960' if video_rgb else '320'), ('image_size_y', '540' if video_rgb else '240'), ('fov', '90'), ('sensor_tick', '0.05')):
                bp.set_attribute(key, value)
            bp.set_attribute('role_name','m7_frame5')
            transform = (carla.Transform(carla.Location(x=-7, z=3.5), carla.Rotation(pitch=-12)) if video_rgb
                         else carla.Transform(carla.Location(x=1.6, z=1.7), carla.Rotation(pitch=-8)))
            sensor = world.spawn_actor(bp, transform, attach_to=ego)
            self.sensors.append(sensor)
            if video_rgb and self.record_video:
                self.video_file = (self.output/'rgb-video.bgra').open('xb')
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
                if len(self.rows[name])>=self.capacity:
                    self.errors.append('bounded camera buffer overflow');return
                if self.drop_rgb and name=='rgb' and len(self.rows[name])==40 and not self.dropped:
                    row['validity']='INJECTED_DELIVERY_DROP';self.dropped.append(row);return
                if self.rows[name] and row['frame']!=self.rows[name][-1]['frame']+5:
                    self.errors.append(name+' frame gap or duplicate')
                if not self.rows[name]:
                    with gzip.open(self.output/(name+'-first.bgra.gz'),'wb') as f:f.write(data)
                if name == 'rgb' and self.video_file is not None:
                    try:
                        self.video_file.write(data)
                    except OSError as error:
                        self.errors.append('video write failed: '+str(error));return
                self.rows[name].append(row)
                if self.live_view and name == 'rgb':
                    self.latest_rgb = (row, data)
        return receive

    def show_live(self, simulation_seconds, speed_kmh):
        if self.viewer is not None:
            with self.lock:
                latest = self.latest_rgb
            self.viewer.update(latest, simulation_seconds, speed_kmh)

    def snapshot(self):
        with self.lock:
            return dict(streams={k:list(v) for k,v in self.rows.items()},dropped=list(self.dropped),errors=list(self.errors),
                        sensor_tick_seconds=.05,gt_control_use=False)

    def stop(self):
        try:
            for sensor in self.sensors:
                if sensor.is_alive:sensor.stop()
        finally:
            if self.viewer is not None:
                self.viewer.close()
            with self.lock:
                if self.video_file is not None:
                    self.video_file.close()
                    self.video_file = None

    def destroy(self):
        for sensor in self.sensors:
            if sensor.is_alive:sensor.destroy()


class LiveView:
    """Main-thread display of the latest RGB only; never ticks or controls CARLA."""

    def __init__(self):
        import tkinter as tk
        self.tk = tk
        self.root = tk.Tk()
        self.root.title('StrataDrive CARLA LIVE — STOP30')
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.picture = tk.Label(self.root, text='Waiting for CARLA camera...', width=120, height=30)
        self.picture.pack()
        self.status = tk.Label(self.root, text='Live camera | closing this window keeps the simulation running')
        self.status.pack(fill='x')
        self.photo = None
        self.last_frame = None
        self.next_update = 0.
        self.frames_shown = 0
        self.root.update()

    def update(self, latest, simulation_seconds, speed_kmh):
        now = time.monotonic()
        if self.root is None or now < self.next_update:
            return
        self.next_update = now + .05
        if latest is not None:
            row, bgra = latest
            if row['frame'] != self.last_frame:
                rgb = bytearray(row['width'] * row['height'] * 3)
                rgb[0::3], rgb[1::3], rgb[2::3] = bgra[2::4], bgra[1::4], bgra[0::4]
                ppm = ('P6\n%d %d\n255\n' % (row['width'], row['height'])).encode() + rgb
                self.photo = self.tk.PhotoImage(data=ppm, format='PPM')
                self.picture.configure(image=self.photo, text='', width=0, height=0)
                self.last_frame = row['frame']
                self.frames_shown += 1
        self.status.configure(text='LIVE | simulation %.2f s | current speed %.1f km/h | camera frame %s\n'
                              'Close window: continue without display | Ctrl+C in terminal: stop run' %
                              (simulation_seconds, speed_kmh, self.last_frame))
        self.root.update_idletasks()
        self.root.update()

    def close(self):
        if self.root is not None:
            self.root.destroy()
            self.root = None
        self.photo = None
