"""Transient spawn request only; no world tick before physics-off and final placement."""

from copy import deepcopy
import math

STAGING = dict(height_m=50, actor_step_m=10, no_tick_before_final_placement=True)


def staging_pose(planned, index):
    if type(index) is not int or not 0 <= index < 100:
        raise ValueError("staging actor index")
    values = tuple(planned["location"].values()) + tuple(planned["rotation"].values())
    if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
        raise ValueError("finite staging pose")
    result = deepcopy(planned)
    result["location"]["z"] += STAGING["height_m"] + index * STAGING["actor_step_m"]
    return result
