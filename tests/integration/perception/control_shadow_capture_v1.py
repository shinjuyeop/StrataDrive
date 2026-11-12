"""Finite live2K recorder and observer; never writes vehicle control or ticks."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import threading
import time
import traceback
import zlib

from PIL import Image
from native_memory_recorder_v1 import MemoryRecorder
from physical_ai.perception.ipc_2k_v1 import IpcWorldPerception, Publisher, socket_pair
from physical_ai.perception.staged_kernel_2k_v1 import StagedKernelBackend
from physical_ai.perception.world_async_2k_v1 import ObservedWorldClock


class Capture:
    def __init__(self, args):
        self.args = args
        self.world = self.sensor = self.worker = self.thread = self.recorder = None
        self.tick_id = None
        self.tx, self.rx = socket_pair()
        self.stop_event = threading.Event()
        self.state_lock, self.camera_lock = threading.Lock(), threading.Lock()
        self.observing = self.accepting = True
        self.started = False
        self.report = dict(schema="m10-control-shadow-capture-v1", errors=[], cleanup_errors=[],
                           state=[], camera=[], ipc=[], model_calls=[], preparation_calls=[], raw=[],
                           authority="shadow only", cold_calls_excluded=0, epoch=42)

    def attach(self, world, actor, carla):
        self.world = world
        self.report.update(source_clock=world.id, wall_clock=self.args.wall_clock)
        self.detector = StagedKernelBackend(self.args.detector, self.args.models, self.args.library,
            "f851fa22a24576d4e76fa2fa8749f3f4517d5ee625b64de390a360fd32fb0721")
        self.report["providers"] = self.detector.detector.session.get_providers()
        owner = self
        preparing = True

        class Backend:
            def infer(self, packet):
                row = dict(identity=asdict(packet.identity), received_wall_ns=packet.received_wall_ns,
                           owner_thread_id=threading.get_ident(), begin_wall_ns=time.monotonic_ns())
                try:
                    result = owner.detector.infer(packet)
                    row["result"] = asdict(result)
                    return result
                except Exception:
                    row["error"] = traceback.format_exc()
                    raise
                finally:
                    row["end_wall_ns"] = time.monotonic_ns()
                    owner.report["preparation_calls" if preparing else "model_calls"].append(row)

        self.worker = IpcWorldPerception(Backend(), ObservedWorldClock(world.id), self.args.wall_clock)
        if not self.worker.prepare() or not self.worker.wait_prepared(10):
            raise RuntimeError("bounded native2K preparation")
        self.report["preparation"] = self.worker.preparation_status()
        preparing = False
        self.recorder = MemoryRecorder(self.args.output / "raw", 96)
        self.publisher = Publisher(self.tx, 42, world.id, self.args.wall_clock)
        self.report['camera_condition'] = 'absent' if getattr(self.args, 'camera_absent_control', False) else '2k'
        if self.report['camera_condition'] == 'absent':
            # Retain identical model preparation, world observer and IPC. Only
            # the sensor actor is omitted; the caller keeps rendering enabled.
            self.tick_id = world.on_tick(self.observed)
            return
        bp = world.get_blueprint_library().find("sensor.camera.rgb")
        expected = dict(image_size_x="2560", image_size_y="1536", fov="90", sensor_tick="0.05",
                        role_name="m7_frame5", enable_postprocess_effects="True")
        for key, value in expected.items():
            bp.set_attribute(key, value)
        pose = carla.Transform(carla.Location(x=1.4, z=1.7))
        self.report["camera_pose_relative"] = dict(x=1.4, y=0, z=1.7, pitch=0, yaw=0, roll=0)
        self.sensor = world.spawn_actor(bp, pose, attach_to=actor)
        attrs = dict(self.sensor.attributes)
        self.report["sensor_attributes"] = attrs
        for key, value in expected.items():
            if key in ("role_name", "enable_postprocess_effects"):
                if attrs[key].lower() != value.lower():
                    raise ValueError("sensor readback " + key)
            elif float(attrs[key]) != float(value):
                raise ValueError("sensor readback " + key)
        self.tick_id = world.on_tick(self.observed)
        self.sensor.listen(self.camera)

    def observed(self, snap):
        row = dict(begin_wall_ns=time.monotonic_ns(), frame=snap.frame, world_id=snap.id,
                   source_ns=round(snap.timestamp.elapsed_seconds * 1e9),
                   delta_ns=round(snap.timestamp.delta_seconds * 1e9))
        with self.state_lock:
            if not self.observing:
                return
            try:
                row["disposition"] = self.worker.observe_snapshot(row["world_id"], row["frame"],
                    row["source_ns"], row["delta_ns"], row["begin_wall_ns"])
                if row["disposition"] == "fault":
                    raise RuntimeError("actual world observation fault")
                if row["disposition"] == "accepted" and not self.started:
                    if not self.worker.start_observed_session(42):
                        raise RuntimeError("observed session initialization")
                    self.started = True
                if len(self.report["state"]) >= 4096:
                    raise RuntimeError("bounded state recorder")
                row["end_wall_ns"] = time.monotonic_ns()
                self.report["state"].append(row)
            except Exception:
                self.report["errors"].append(traceback.format_exc())
                self.stop_event.set()

    def camera(self, image):
        row = dict(begin_wall_ns=time.monotonic_ns(), frame=image.frame,
                   source_ns=round(image.timestamp * 1e9), width=image.width, height=image.height)
        with self.camera_lock:
            try:
                raw = bytes(image.raw_data)
                row["copy_end_wall_ns"] = time.monotonic_ns()
                row["offer_entry_wall_ns"] = time.monotonic_ns()
                row["offered"] = self.accepting
                row["accepted"] = self.worker.offer(image.frame, image.timestamp, image.width, image.height, raw) if self.accepting else False
                row["offer_end_wall_ns"] = time.monotonic_ns()
                if not self.recorder.offer(row, raw):
                    raise RuntimeError("raw recorder overflow; original retained in spill")
            except Exception:
                row["error"] = traceback.format_exc()
                self.report["errors"].append(row["error"])
                self.worker.invalidate("camera callback fault")
                self.stop_event.set()
            row["end_wall_ns"] = time.monotonic_ns()
            self.report["camera"].append(row)

    def start_publisher(self):
        def consume():
            begin = scheduled = time.monotonic_ns()
            try:
                while not self.stop_event.is_set():
                    remaining = scheduled - time.monotonic_ns()
                    if remaining > 0 and self.stop_event.wait(remaining / 1e9):
                        break
                    sample, frame = self.worker.ipc_observation()
                    sent_at = time.monotonic_ns()
                    data, disposition = self.publisher.send(sample, frame, sent_at)
                    ended = time.monotonic_ns()
                    if len(self.report["ipc"]) >= 1000:
                        raise RuntimeError("bounded publisher recorder")
                    self.report["ipc"].append(dict(scheduled_wall_ns=scheduled, sender_wall_ns=sent_at,
                        observation_wall_ns=sample.wall_ns, end_wall_ns=ended, disposition=disposition, packet_hex=data.hex()))
                    scheduled = begin + ((ended - begin) // 20_000_000 + 1) * 20_000_000
            except Exception:
                self.report["errors"].append(traceback.format_exc())
                self.stop_event.set()
        self.thread = threading.Thread(target=consume, name="shadow-ipc-publisher", daemon=True)
        self.thread.start()

    def snapshot(self):
        return self.report

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(2)
            if self.thread.is_alive():
                self.report["cleanup_errors"].append("publisher stop timeout")
        if self.world and self.tick_id is not None:
            self.world.remove_on_tick(self.tick_id)
        with self.state_lock:
            self.observing = False
        if self.sensor and self.sensor.is_listening:
            self.sensor.stop()
        with self.camera_lock:
            self.accepting = False
        self.tx.close()
        self.rx.close()
        if self.worker:
            self.report["closed"] = self.worker.close(5)
            self.report["worker"] = self.worker.status()
            self.report["decisions"] = self.worker.decision_trace()
            self.report["world_observation"] = self.worker.world_status()
            self.report["preparation_final"] = self.worker.preparation_status()
            self.report["backend_stages"] = self.detector.stages
            if not self.report["closed"]:
                self.report["cleanup_errors"].append("worker close timeout")
        if self.recorder:
            if not self.recorder.close(30):
                self.report["cleanup_errors"].append("recorder close timeout")
            self.report["recorder"] = self.recorder.report()
            for row, raw in self.recorder.iter_raw():
                data = zlib.compress(raw, 1)
                path = f"{row['frame']}.bgra.z"
                (self.args.output / path).write_bytes(data)
                rgb = Image.frombytes("RGB", (2560, 1536), raw, "raw", "BGRX").tobytes()
                self.report["raw"].append(dict(frame=row["frame"], source_ns=row["source_ns"], path=path,
                    rgb_sha256=hashlib.sha256(rgb).hexdigest(), bgra_sha256=hashlib.sha256(raw).hexdigest(),
                    stored_sha256=hashlib.sha256(data).hexdigest(), stored_bytes=len(data), raw_bytes=len(raw)))
        if hasattr(self, "publisher"):
            self.report["publisher"] = dict(sent=self.publisher.sent, dropped=self.publisher.dropped,
                                           disconnected=self.publisher.closed)
        (self.args.output / "perception.json").write_text(json.dumps(self.report, indent=2) + "\n")

    def destroy(self, *, ownership_released=False):
        if self.sensor is None:
            return
        # The exclusive server ownership rejects actor destruction until close.
        # Closing the parent can already remove an attached camera; observe that
        # outcome instead of submitting another ambiguous destruction request.
        if not ownership_released:
            raise RuntimeError("camera destruction requires closed native ownership")
        if self.world.get_actor(self.sensor.id) is None:
            self.report["camera_cleanup"] = "absent after parent close"
            return
        if not self.sensor.destroy():
            raise RuntimeError("camera destruction failed after ownership release")
        self.report["camera_cleanup"] = "destroyed after ownership release"
