"""Explicit owner-only plant cadence; no implicit change to shadow10ms."""
PROFILES = ('shadow10ms', 'owner5ms')
WALL_PROFILES = {'wall5-hv30-v1': 30, 'wall5-hv50-v1': 50}


def validate_client(args):
    policy = getattr(args, 'wall_profile', 'wall5-hv30-v1')
    common = (args.warmup_ticks == 150 and args.fault == 'none' and
              policy in WALL_PROFILES and args.hv_dependency_ms == WALL_PROFILES[policy])
    if policy == 'wall5-hv50-v1':
        common = common and args.execution_profile == 'owner5ms' and bool(getattr(args, 'endurance_seconds', 0))
    if args.execution_profile == 'shadow10ms':
        valid = args.cameras and args.ticks == 200 and args.step_ms == 10
    elif args.execution_profile == 'owner5ms':
        duration=getattr(args,'endurance_seconds',0)
        from endurance_profile_v1 import limits
        bound=limits(duration)
        valid = not args.cameras and args.camera_absent_control and args.ticks == bound['frames'] and args.step_ms == 5
        if duration:valid=valid and getattr(args,'paired_renderer_port',None)==2300 and args.paired_condition=='normal' and args.paired_export_hz==20
    else:
        valid = False
    if not common or not valid:
        raise ValueError('declared camera/cadence and matching explicit HV policy required')


def configure_owner(command, client, profile, condition):
    if profile not in PROFILES:
        raise ValueError('unknown execution profile')
    if profile == 'shadow10ms':
        return command, client
    if condition != 'absent':
        raise ValueError('owner5ms cannot create a camera')
    command = [arg for arg in command if arg not in ('-StrataM7SensorFrame5','-StrataM10ReadbackProfile')]
    command += ['-StrataM7Wall5ms', '-nullrhi', '-norenderthread']
    client = list(client)
    client.remove('--cameras')
    client[client.index('--ticks') + 1] = '400'
    client += ['--execution-profile', 'owner5ms', '--step-ms', '5']
    return command, client
