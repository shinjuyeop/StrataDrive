"""Wait passively for the selected UE map before the first SDK request on an owned empty server."""

import json
from pathlib import Path
import subprocess
import time

PROBE = """import carla,json,sys
client=carla.Client('127.0.0.1',int(sys.argv[1]))
client.set_timeout(120.0)
world=client.get_world()
snapshot=world.get_snapshot()
version=client.get_server_version()
if snapshot.frame<=0 or snapshot.id!=world.id or world.id<=0 or not version: raise ValueError('episode identity')
print(json.dumps(dict(world=world.id,frame=snapshot.frame,version=version)))
"""


def prepare_empty_world(python, port, directory, env, process, map_path):
    start = time.monotonic()
    deadline = start + 600
    marker = f" seconds to LoadMap({map_path})".encode()
    tail = b""
    with (Path(directory) / "server.log").open("rb") as stream:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"server exited during map load ({process.returncode})"
                )
            chunk = stream.read(65536)
            if not chunk:
                time.sleep(0.15)
                continue
            data = tail + chunk
            if marker in data:
                break
            tail = data[-len(marker) :]
        else:
            raise TimeoutError("empty map asset preparation exceeded 600 s")
    loaded = time.monotonic()
    # CARLA 0.9.16 services synchronous world RPCs only after game-thread startup.
    # A single private SDK process now observes this episode within the original
    # 180 s verification horizon. It does not create sensors or tick the world.
    probe = subprocess.run(
        [str(python), "-c", PROBE, str(port)],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    record = dict(
        map=map_path,
        load_seconds=loaded - start,
        sdk_seconds=time.monotonic() - loaded,
        sdk_exit=probe.returncode,
        stdout=probe.stdout[-4096:],
        stderr=probe.stderr[-4096:],
    )
    with (Path(directory) / "readiness.jsonl").open("x") as out:
        out.write(json.dumps(record) + "\n")
    if probe.returncode:
        raise RuntimeError("SDK readiness failed after the selected map loaded")
    value = json.loads(probe.stdout)
    if (
        type(value.get("world")) is not int
        or value["world"] <= 0
        or type(value.get("frame")) is not int
        or value["frame"] <= 0
        or not value.get("version")
    ):
        raise ValueError("SDK world confirmation")
    return dict(
        **value,
        map=map_path,
        load_seconds=record["load_seconds"],
        sdk_seconds=record["sdk_seconds"],
    )
