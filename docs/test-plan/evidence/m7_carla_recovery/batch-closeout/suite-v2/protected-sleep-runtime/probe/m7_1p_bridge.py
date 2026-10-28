"""Opt-in, local direct-solver sensor bridge to the existing native shadow.

No CARLA writer or tick API. The caller must pause the backend on any failure.
Native scope (1,42,7) is a fresh-process fixture, NOT CARLA's authority/clock.
CARLA UUID/session/actor/generation stay pinned here; acquisition uses the
original simulation-end timestamp, never the synthetic Actual logical clock.
"""
import copy
import json
import math
import select
import subprocess
import time

SOURCE = "PhysX3.4.mWheelSpeeds.direct.v1"
DOMAIN = 0x4D3746554E435449


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def aligned_snapshot(get_snapshot, expected_frame, timeout=10):
    """Wait only for episode-stream delivery; never acquire a tick permit."""
    started = time.monotonic()
    snapshot = get_snapshot()
    first, polls = snapshot.frame, 0
    while snapshot.frame < expected_frame and time.monotonic()-started < timeout:
        time.sleep(.001)
        snapshot = get_snapshot()
        polls += 1
    require(snapshot.frame == expected_frame, "snapshot missing/skipped at receipt barrier")
    return snapshot, dict(first_frame=first, polls=polls, wall_seconds=time.monotonic()-started)


class ReceiptGate:
    def __init__(self, binding):
        self.binding = copy.deepcopy(binding)
        require(binding["ok"] and binding["locked"] and not binding["latched"], "binding")
        require(not binding["normal_driving_enabled"] and not binding["interval_work_valid"], "scope")
        self.frame = int(binding["frame"])
        self.end = binding["simulation_seconds"]
        require(math.isfinite(self.end) and 0 < self.end < 1e8, "binding simulation timestamp")
        self.logical = int(binding["logical_begin_ns"])
        self.tickets = set()
        self.failed = False

    def accept(self, r):
        try:
            require(not self.failed, "receipt gate latched")
            b = self.binding
            require(all(r[k] == b[k] for k in ("run", "session", "actor", "model_id", "model_sha256", "effort_profile")), "receipt identity")
            ph = r["physics"]
            require(r["physics_generation"] == ph["generation"] == b["physics"]["generation"], "physics generation")
            require(ph["nodrive"] and all(ph[k] == b["physics"][k] for k in
                    ("numerical_profile", "vehicle_substeps_low", "vehicle_substeps_high", "vehicle_substeps_threshold_m_s")), "physics profile")
            require(r["clock_domain"] == "m7-zero-probe-logical-frame" and
                    r["source_identity"] == "synthetic-steering/brake/drive-CAN-P05-fixture; NOT native authority", "diagnostic clock/scope")
            require(r["inputs_cleared_after_physics"] and not r["interval_work_valid"] and
                    not r["solver_substep_work_observed"], "receipt completion/scope")
            frame = int(r["frame"])
            require(frame == self.frame+1 and 0 < frame <= 0xFFFFFFFF, "receipt frame")
            require(r["ticket"] not in self.tickets, "duplicate ticket")
            begin, end = r["simulation_begin_seconds"], r["simulation_end_seconds"]
            require(all(isinstance(x, (int, float)) and math.isfinite(x) and 0 < x < 1e8 for x in (begin, end)), "simulation timestamp")
            require(abs(end-begin-.01) < 1e-6 and abs(begin-self.end) < 1e-9, "simulation continuity")
            require(int(r["logical_begin_ns"]) == self.logical and
                    int(r["logical_end_ns"]) == self.logical+10000000, "diagnostic interval")
            wheels = ph["wheels"]
            require(len(wheels) == 4, "missing wheel")
            for i, w in enumerate(wheels):
                require(w["index"] == i and w["bone"] == b["physics"]["wheels"][i]["bone"], "wheel order")
                require(w["solver_omega_source"] == SOURCE, "solver source identity")
                require(math.isfinite(w["solver_omega_rad_s"]), "nonfinite solver wheel")
            # Negative and range checks are also performed by the unchanged
            # native forward-only contract, before any next-frame barrier.
            omega = [w["solver_omega_rad_s"] for w in wheels]
            ns = math.floor(end*1e9+.5)  # same positive llround as native FrameClock
            line = (f"WHEEL 1 42 7 {DOMAIN} {frame} {end:.17g} {end-begin:.17g} "
                    f"{b['actor']} {frame} {ns} " + " ".join(f"{v:.17g}" for v in omega))
            self.frame, self.end, self.logical = frame, end, int(r["logical_end_ns"])
            self.tickets.add(r["ticket"])
            return dict(line=line, frame=frame, source_ns=ns, rad_s=(omega[2]+omega[3])/2,
                        solver_omega_rad_s=omega, solver_omega_source=SOURCE)
        except Exception:
            self.failed = True
            raise


class NativeBridge:
    def __init__(self, executable, binding, stderr_path):
        self.gate = ReceiptGate(binding)
        self.stderr = stderr_path.open("w")
        self.proc = subprocess.Popen([str(executable.resolve()), "--wheel-shadow", "1", "42", "7", binding["actor"]],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, text=True)
        self.history = {}
        self.failed = False
        self.closed = False

    def observe(self, receipt):
        try:
            require(not self.failed and not self.closed, "native bridge latched/closed")
            sample = self.gate.accept(receipt)
            self.history[sample["source_ns"]] = sample["rad_s"]
            self.proc.stdin.write(sample["line"]+"\n")
            self.proc.stdin.flush()
            require(bool(select.select([self.proc.stdout], [], [], 10)[0]), "native barrier timeout")
            reply = json.loads(self.proc.stdout.readline())
            require(reply["status"] == "WHEEL_SHADOW_BARRIER" and not reply["driving"], "native rejected wheel")
            require(reply["now_ns"] == sample["source_ns"] and reply["next_frame"] == sample["frame"]+1 and
                    reply["service_mask"] == 255, "native barrier identity")
            for field in ("sensor_wheel", "returned_wheel"):
                w = reply[field]
                if w is None:
                    require(not reply["armed_fixture"], "armed wheel missing")
                    continue
                require(w["source_ns"] in self.history and w["source_ns"] <= reply["now_ns"], "native source restamped/unknown")
                tolerance = 0 if field == "sensor_wheel" else .005+1e-12
                require(math.isfinite(w["rad_s"]) and abs(w["rad_s"]-self.history[w["source_ns"]]) <= tolerance,
                        "native wheel value changed beyond CAN resolution")
                if reply["armed_fixture"]:
                    require(reply["now_ns"]+10000000-w["source_ns"] <= 30000000, "native next interval stale")
            if reply["armed_fixture"]:
                require(reply["release_mask"] == reply["credit_mask"] == 255, "native authority fixture")
            return dict(sample=sample, native=reply)
        except Exception:
            self.failed = True
            self.gate.failed = True
            raise

    def close(self):
        self.closed = True
        if self.proc.stdin and not self.proc.stdin.closed:
            self.proc.stdin.close()
        try:
            code = self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
            raise RuntimeError("native owned child required forced stop")
        finally:
            self.proc.stdout.close()
            self.stderr.close()
        return code
