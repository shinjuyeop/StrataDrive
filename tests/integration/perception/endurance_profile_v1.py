"""Prospective diagnostic horizon/storage bounds; never controller deadlines."""
def camera_pacing(renderer_hz,camera_period_ms,raw_recording=False):
    if renderer_hz not in (0,10,20) or camera_period_ms not in (50,100):
        raise ValueError('declared renderer/camera pacing')
    if camera_period_ms==100 and renderer_hz!=20:
        raise ValueError('100ms camera requires declared20Hz renderer')
    if raw_recording and (renderer_hz,camera_period_ms) not in ((10,50),(20,100)):
        raise ValueError('bounded10Hz raw recording only')
    return renderer_hz*50/camera_period_ms if renderer_hz else None


def limits(seconds):
    if type(seconds) is not int or seconds not in (0,30,300):raise ValueError('explicit endurance duration')
    return dict(seconds=seconds,frames=seconds*200 if seconds else 400,
        observations=seconds*200+256 if seconds else 4096,
        ipc_rows=(seconds+5)*50+16 if seconds else 1000,
        camera_frames=seconds*20+64 if seconds else 96,
        execution_seconds=seconds+4 if seconds else 18,
        renderer_seconds=seconds+10 if seconds else 15,
        stored_bytes=(seconds*20+64)*9*1024**2 if seconds else 2*1024**3)
