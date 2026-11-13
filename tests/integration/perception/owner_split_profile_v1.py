"""Explicit owner-only plant cadence; no implicit change to shadow10ms."""
PROFILES = ('shadow10ms', 'owner5ms')


def validate_client(args):
    common = args.warmup_ticks == 150 and args.hv_dependency_ms == 30 and args.fault == 'none'
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
        raise ValueError('declared shadow10ms or camera-free owner5ms profile required; HV30 unchanged')


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
