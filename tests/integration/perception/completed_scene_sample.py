"""Inspect the actual three-actor world while a completed native simulation frame is held."""

import hashlib
import json
from pathlib import Path

from paired_scene_capture_v1 import environment, prepare_actors
from m7_1p_bridge import aligned_snapshot


class CompletedSceneSample:
    def __init__(self, world, ego, carla, output):
        self.world, self.ego = world, ego
        self.output = Path(output) / "completed-visual"
        self.output.mkdir()
        self.extras, prep = prepare_actors(world, ego, carla)
        self.actors = [ego, *self.extras]
        self.index = dict(
            preparation=prep,
            preparation_environment=environment(world),
            world=world.id,
            actors=[
                dict(id=a.id, blueprint=a.type_id, attributes=dict(a.attributes))
                for a in self.actors
            ],
            frames=[],
        )
        self.save()

    def save(self):
        (self.output / "index.json").write_text(json.dumps(self.index, indent=2) + "\n")

    def inspect(self, ordinal, rpc, receipt):
        if ordinal not in range(10, 400, 25):
            return
        frame = int(receipt["frame"])
        first, delivery = aligned_snapshot(self.world.get_snapshot, frame)
        ids = [a.id for a in self.actors]
        if not self.index["frames"]:
            rejected = rpc(
                "visual_completed",
                record=False,
                frame=str(frame),
                ticket="0",
                actors=sorted(ids),
            )
            if rejected["ok"] or rejected["reason"] != "completed_visual_context":
                raise ValueError("wrong completed ticket accepted")
            self.index["rejected_ticket"] = rejected["reason"]
        data = rpc(
            "visual_completed",
            record=False,
            frame=str(frame),
            ticket=receipt["ticket"],
            actors=sorted(ids),
        )
        if (
            not data["ok"]
            or data["original_receipt"] != receipt
            or data["complete_scene_proof"]
        ):
            raise ValueError(
                "original native physics receipt did not match the observed visual frame"
            )
        observed_environment = environment(self.world)
        if not all(
            light["state"] == "Red" and light["frozen"]
            for light in observed_environment["traffic_lights"]
        ):
            raise ValueError("traffic light source observation after native physics")
        if (
            self.index.setdefault("environment", observed_environment)
            != observed_environment
        ):
            raise ValueError("environment changed between completed native samples")
        poses = []
        for actor in self.actors:
            state = first.find(actor.id)
            if state is None:
                raise ValueError("missing observed actor")
            pose = state.get_transform()
            poses.append(
                dict(
                    id=actor.id,
                    xyz=[pose.location.x, pose.location.y, pose.location.z],
                    pyr=[pose.rotation.pitch, pose.rotation.yaw, pose.rotation.roll],
                    matrix=pose.get_matrix(),
                )
            )
        last = self.world.get_snapshot()
        if (
            first.id != self.world.id
            or first.frame != frame
            or last.frame != frame
            or first.timestamp.elapsed_seconds != last.timestamp.elapsed_seconds
            or abs(first.timestamp.elapsed_seconds - receipt["simulation_end_seconds"])
            > 1e-8
        ):
            raise ValueError(
                "moving scene did not remain on this completed simulation frame"
            )
        visual = data["visual"]
        if (
            set(a["actor"] for a in visual["actors"]) != set(ids)
            or int(receipt["physics_acquisition_end_ns"]) > int(visual["begin_ns"])
            or int(visual["begin_ns"]) > int(visual["end_ns"])
        ):
            raise ValueError("completed scene inventory or acquisition bracket")
        if "wheel_animation" in visual and len(visual["wheel_animation"]) != 4:
            raise ValueError("source vehicle animation did not expose all four wheels")
        path = self.output / f"frame-{frame}.json"
        path.write_text(
            json.dumps(
                dict(
                    ordinal=ordinal,
                    world=first.id,
                    poses=poses,
                    source_seconds=first.timestamp.elapsed_seconds,
                    snapshot_delivery=delivery,
                    visual=visual,
                    original_receipt=receipt,
                ),
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        )
        self.index["frames"].append(
            dict(
                frame=frame,
                ordinal=ordinal,
                path=path.name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
        self.save()

    def close(self):
        for actor in reversed(self.extras):
            if (
                self.world.get_actor(actor.id) is not None
                and not actor.destroy()
                and self.world.get_actor(actor.id) is not None
            ):
                raise RuntimeError("moving scene cleanup failed")
