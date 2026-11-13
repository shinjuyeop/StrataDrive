"""Evidence required for progress through an observed renderer process death."""
import select
import time

STALL_NS = 250_000_000
STOP_INTERVAL = 180
CRASH_INTERVAL = 260


def observed_process_exit(pidfd):
    """Observe the inherited descriptor for the exact owned process, never a PID lookup."""
    poller=select.poll();poller.register(pidfd,select.POLLIN)
    events=poller.poll(0)
    if any(flags & select.POLLNVAL for _,flags in events):raise ValueError('invalid process descriptor')
    return time.monotonic_ns() if any(flags & select.POLLIN for _,flags in events) else None


def audit_crash_cleanup(record,crash_ns,cleanup_ns,actor_ids):
    if (not isinstance(record,dict) or record.get('observed_exit_ns',0)<max(crash_ns,cleanup_ns)
        or sorted(record.get('skipped_actor_ids',[]))!=sorted(actor_ids)
        or record.get('skipped_operations')!=['sensor.stop','actor.destroy','world.hold']):
        raise ValueError('exact dead-process cleanup evidence')


def audit_crash_progress(events, physical_starts, observed_exit_ns):
    def require(value, message):
        if not value:raise ValueError(message)
    require([e['action'] for e in events]==['SIGSTOP','SIGCONT','SIGKILL'], 'declared crash actions')
    stop,resume,crash=events
    require(stop['physical_intervals']>=STOP_INTERVAL and crash['physical_intervals']>=CRASH_INTERVAL,
            'declared active-physics fault thresholds')
    stopped=stop.get('observed_stopped_ns')
    require(type(stopped) is int and stop.get('observed_proc_state')=='T'
            and stop['wall_ns']<=stopped<resume['wall_ns'], 'actual renderer stopped state')
    require(resume['wall_ns']-stop['wall_ns']>=STALL_NS, 'declared stall interval')
    require(resume['wall_ns']<crash['wall_ns']<=observed_exit_ns<crash['wall_ns']+1_000_000_000,
            'actual renderer crash observation')
    paused=sum(stopped<t<resume['wall_ns'] for t in physical_starts)
    after=sum(t>observed_exit_ns for t in physical_starts)
    require(paused>10 and after>10, 'physical progress during stop and after actual process death')
    return dict(physical_intervals_while_stopped=paused,physical_intervals_after_observed_exit=after,
                observed_exit_ns=observed_exit_ns,stop_observed_ns=stopped)
