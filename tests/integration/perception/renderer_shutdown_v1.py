"""Bounded post-SIGINT diagnostics for a runner-owned renderer only.

No debugger attaches during normal rendering. Child-only ptrace permission is
opt-in; the host Yama policy is never modified. No environment or memory dump.
"""
import ctypes
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time

MAX_THREADS = 512
MAX_LOG_BYTES = 8 * 1024 * 1024


def allow_shutdown_tracer():
    """preexec_fn hook for this new child, retained across its exec."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(ctypes.c_int(0x59616d61), ctypes.c_ulong(-1),
                  ctypes.c_ulong(0), ctypes.c_ulong(0), ctypes.c_ulong(0)) != 0:
        raise OSError(ctypes.get_errno(), 'PR_SET_PTRACER on owned diagnostic child')


def read_bounded(path, limit=65536):
    try:
        with Path(path).open('rb') as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            return dict(error='bounded proc file overflow')
        return dict(text=data.decode('utf-8', errors='replace'))
    except OSError as error:
        return dict(error=str(error))


def proc_snapshot(pid):
    root = Path('/proc') / str(pid)
    tids = sorted((root/'task').iterdir(), key=lambda p:int(p.name))
    if len(tids) > MAX_THREADS:
        raise ValueError('bounded thread inventory exceeded')
    return dict(pid=pid, observed_wall_ns=time.monotonic_ns(),
                stat=read_bounded(root/'stat'), status=read_bounded(root/'status'),
                maps=read_bounded(root/'maps', 1024*1024),
                threads=[dict(tid=int(t.name), comm=read_bounded(t/'comm'),
                              stat=read_bounded(t/'stat'), wchan=read_bounded(t/'wchan'),
                              syscall=read_bounded(t/'syscall')) for t in tids])


def capture(process, output, timeout_seconds=8):
    """Read a live owned Popen child; an exited/reused PID is never attached."""
    if not isinstance(process, subprocess.Popen) or process.poll() is not None:
        return dict(status='ALREADY_EXITED')
    if not 0 < timeout_seconds <= 8:
        raise ValueError('bounded debugger deadline')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    began = time.monotonic_ns()
    report = dict(status='DIAGNOSTIC_FAILED', begin_wall_ns=began, pid=process.pid,
                  timeout_seconds=timeout_seconds, intrusive_after_exit_request=True)
    try:
        before = proc_snapshot(process.pid)
        (output/'before.json').write_text(json.dumps(before, indent=2)+'\n')
        if process.poll() is not None:
            report['status'] = 'EXITED_BEFORE_ATTACH'
            return report
        command = ['/usr/bin/gdb', '-nx', '-nh', '-batch',
                   '-iex', 'set auto-solib-add off', '-iex', 'set debuginfod enabled off',
                   '-iex', 'set index-cache enabled off', '-iex', 'set pagination off',
                   '-iex', 'set print thread-events off', '-iex', 'set print frame-arguments none',
                   '-p', str(process.pid),
                   '-ex', 'sharedlibrary libpthread|libc\\.so|libstdc\\+\\+|libUE4Editor-Core\\.so|libUE4Editor-Carla\\.so|libUE4Editor-VulkanRHI\\.so',
                   '-ex', 'info threads', '-ex', 'thread apply all bt 16', '-ex', 'detach']
        report['argv'] = command
        def limits():
            resource.setrlimit(resource.RLIMIT_CORE, (0,0))
            resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_LOG_BYTES,MAX_LOG_BYTES))
        with (output/'gdb.log').open('w') as log:
            tracer = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                      env=dict(os.environ, DEBUGINFOD_URLS=''),
                                      start_new_session=True, preexec_fn=limits)
            try:
                report['gdb_exit'] = tracer.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                report['gdb_timeout'] = True
                os.killpg(tracer.pid,signal.SIGKILL); report['gdb_exit'] = tracer.wait(timeout=2)
        # Killing a timed-out tracer must not leave the renderer ptrace-stopped.
        if process.poll() is None:
            os.kill(process.pid, signal.SIGCONT)
            (output/'after.json').write_text(json.dumps(proc_snapshot(process.pid), indent=2)+'\n')
        text = (output/'gdb.log').read_text(errors='replace')
        report['log_bytes'] = (output/'gdb.log').stat().st_size
        if report['gdb_exit'] == 0 and not report.get('gdb_timeout') and 'detached' in text.lower() and '#0' in text:
            report['status'] = 'CAPTURED'
    except (OSError, ValueError) as error:
        report['error'] = str(error)
    finally:
        report['end_wall_ns'] = time.monotonic_ns()
        (output/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def shutdown(process, output, *, diagnostics=False, limit_seconds=30, diagnostic_after_seconds=10):
    """Original wall limit includes debugger time; no successful-exit relabel."""
    if not 0 < diagnostic_after_seconds < limit_seconds <= 30:
        raise ValueError('bounded shutdown profile')
    result = dict(begin_wall_ns=time.monotonic_ns(), limit_seconds=limit_seconds,
                  diagnostic_after_seconds=diagnostic_after_seconds, diagnostics_enabled=diagnostics)
    deadline = time.monotonic() + limit_seconds
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGINT)
        try:
            process.wait(timeout=diagnostic_after_seconds if diagnostics else limit_seconds)
        except subprocess.TimeoutExpired:
            if diagnostics:
                result['diagnostic'] = capture(process, Path(output)/'shutdown', min(8, max(.001,deadline-time.monotonic())))
            remaining = max(0, deadline-time.monotonic())
            try: process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                result['forced_stop'] = True
                os.killpg(process.pid,signal.SIGKILL); process.wait(timeout=10)
    result.update(end_wall_ns=time.monotonic_ns(), server_exit=process.returncode)
    return result
