"""Independent recomputation of every reported wall timing statistic."""

from physical_ai.perception.run import distribution


def metrics(r):
    expected = {}
    for name in ("state", "camera", "consumer"):
        rows = sorted(r["traces"][name], key=lambda x: x["begin_wall_ns"])
        expected[name] = dict(
            jobs=len(rows),
            observed_hz=(len(rows) - 1)
            * 1e9
            / (rows[-1]["begin_wall_ns"] - rows[0]["begin_wall_ns"]),
            job_wall=distribution(
                [x["end_wall_ns"] - x["begin_wall_ns"] for x in rows]
            ),
            interval_wall=distribution(
                [
                    b["begin_wall_ns"] - a["begin_wall_ns"]
                    for a, b in zip(rows, rows[1:])
                ]
            ),
        )
    expected["receipt_to_backend_return"] = distribution(
        [x["end_wall_ns"] - x["received_wall_ns"] for x in r["model_calls"]]
    )
    states = [
        x
        for x in r["traces"]["state"]
        if x["disposition"] == "accepted" and x["frame"] <= r["primary_end_frame"]
    ]
    first, last = states[0], states[-1]
    expected["simulation_realtime_factor"] = (
        last["source_ns"] - first["source_ns"]
    ) / (last["begin_wall_ns"] - first["begin_wall_ns"])
    expected["observed_world_hz"] = (
        (len(states) - 1) * 1e9 / (last["begin_wall_ns"] - first["begin_wall_ns"])
    )
    images = [
        x
        for x in r["traces"]["camera"]
        if r["enabled_wall_ns"] <= x["begin_wall_ns"] < r["primary_end_wall_ns"]
    ]
    expected["primary_camera_hz"] = (
        (len(images) - 1)
        * 1e9
        / (images[-1]["begin_wall_ns"] - images[0]["begin_wall_ns"])
    )
    if expected != r["metrics"]:
        raise ValueError("independently recomputed timing metrics")
