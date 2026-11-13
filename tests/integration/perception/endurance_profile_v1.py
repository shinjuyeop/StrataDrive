"""Prospective diagnostic horizon/storage bounds; never controller deadlines."""
def limits(seconds):
    if type(seconds) is not int or seconds not in (0,30,300):raise ValueError('explicit endurance duration')
    return dict(seconds=seconds,frames=seconds*200 if seconds else 400,
        observations=seconds*200+256 if seconds else 4096,
        ipc_rows=(seconds+5)*50+16 if seconds else 1000,
        camera_frames=seconds*20+64 if seconds else 96,
        execution_seconds=seconds+4 if seconds else 18,
        renderer_seconds=seconds+10 if seconds else 15,
        stored_bytes=(seconds*20+64)*9*1024**2 if seconds else 2*1024**3)
