"""Quiescent cleanup for a dedicated renderer that is about to exit.

No ApplySettings: CARLA's Python ApplySettings can itself issue hidden ticks.
Keep the already-synchronous renderer at its actual final frame during storage.
"""
import time


def hold(world, wall_now=time.monotonic_ns):
    settings = world.get_settings()
    if not settings.synchronous_mode or abs(settings.fixed_delta_seconds-.05) > 1e-9:
        raise ValueError('dedicated renderer must already be synchronous50ms')
    snapshot = world.get_snapshot()
    if snapshot.id != world.id:
        raise ValueError('renderer hold world identity')
    return dict(world=world.id, frame=snapshot.frame,
                source_ns=round(snapshot.timestamp.elapsed_seconds*1e9),
                begin_wall_ns=wall_now(), synchronous_mode=True, fixed_delta_seconds=.05,
                scope='owned renderer awaiting process shutdown; no world-settings restoration')


def verify_hold(world, held, wall_now=time.monotonic_ns):
    current = hold(world, wall_now)
    if (any(current[k] != held[k] for k in ('world','frame','source_ns'))
            or current['begin_wall_ns'] < held['begin_wall_ns']):
        raise ValueError('renderer advanced while quiescent')
    return dict(**held, end_wall_ns=current['begin_wall_ns'], frame_unchanged=True)
