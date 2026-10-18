#!/usr/bin/env python3
"""Exercise a real Trampoline POSIX Steering task against the external SIL plant."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

from check_timing import distribution, require

ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = ('normal', 'command-loss', 'corrupt', 'control-stall')


def rows(path, floats=()):
    with path.open() as stream:
        return [{k: float(v) if k in floats else int(v) for k, v in r.items()} for r in csv.DictReader(stream)]


def validate_jobs(jobs):
    for i, job in enumerate(jobs):
        require(job['job'] == i and job['deadline_ns'] - job['release_ns'] == 5_000_000, 'release/completion budget changed')
        if job['start_ns']:
            require(job['release_ns'] <= job['start_ns'] <= job['phase_ns'] <= job['end_ns'], 'invalid execution interval')
            require(job['source_ns'] <= job['phase_ns'], 'future source')
        else:
            require(job['end_ns'] == job['source_ns'] == job['reported'] == 0, 'fabricated skipped work')
        if job['reported']:
            require(job['end_ns'] <= job['deadline_ns'] and job['actual_source_ns'] == (job['source_ns'] if job['actual_valid'] else job['phase_ns']), 'late/retimestamped Actual')
        if not job['start_ns'] or job['end_ns'] > job['deadline_ns']:
            require(job['detected_ns'] >= job['deadline_ns'], 'OS watchdog missed unfinished job')


def analyze(directory, scenario):
    osmeta = json.loads((directory / 'rtos.json').read_text())
    plant = json.loads((directory / 'plant.json').read_text())
    jobs = rows(directory / 'rtos-jobs.csv')
    physical = rows(directory / 'plant.csv', ('angle_rad',))
    actual = rows(directory / 'actual.csv', ('angle_rad', 'expected_rad'))
    require(osmeta['schema'] == plant['schema'] == 1 and osmeta['tick_ns'] == 10_000_000, 'wrong pilot schema/tick')
    require(osmeta['enable_ns'] == plant['enable_ns'], 'clock/session mismatch')
    require(all(osmeta[k] == 0 for k in ('os_errors', 'fatal_errors', 'ipc_errors', 'shutdown_status')), 'RTOS/API/transport error')
    require(all(plant[k] == 0 for k in ('sensor_drops', 'trace_drops', 'source_errors', 'kernel_drops', 'expired_outputs')), 'plant/feedback error')
    require(len(jobs) == osmeta['released'] > 100 and osmeta['watch_calls'] > 100 and osmeta['rx_calls'] > 100, 'OS alarms did not run')
    require(plant['actual_accepted'] > 20 and osmeta['accepted'] > 20, 'CAN path not established')
    require(any(p['angle_rad'] > .15 for p in physical), 'steering never moved')
    validate_jobs(jobs)
    require(all(a['source_ns'] <= a['time_ns'] for a in actual), 'future wire Actual')
    if scenario == 'normal':
        require(not plant['hold_applied_ns'] and not osmeta['first_guard_ns'] and all(not j['fault'] for j in jobs), 'normal protection/fault')
        require(all(j['start_ns'] for j in jobs) and abs(plant['final_angle_rad'] - .2) < 1e-8, 'normal response')
    else:
        require(plant['hold_applied_ns'] > 0, 'protection not applied')
        held = [p for p in physical if p['held']]
        require(held and all(abs(p['angle_rad'] - held[0]['angle_rad']) < 1e-12 for p in held), 'hold did not preserve actual angle')
        if scenario == 'control-stall':
            injected = [j for j in jobs if j['suspend_ns']]
            require(len(injected) == 1, 'missing OS WaitEvent injection')
            j = injected[0]
            require(j['resume_ns'] - j['suspend_ns'] >= 120_000_000 and not j['reported'], 'OS task did not suspend/discard late report')
            require(j['suspend_ns'] <= osmeta['first_guard_ns'] <= plant['guard_applied_ns'] < j['resume_ns'], 'watch/plant waited for blocked Control')
            require(osmeta['first_guard_ns'] - j['deadline_ns'] <= 20_000_000, 'watch exceeded POSIX fixture margin')
            require(sum(j['suspend_ns'] < p['time_ns'] < j['resume_ns'] for p in physical) >= 20, 'external plant stopped with OS task')
        else:
            require(0 <= plant['hold_applied_ns'] - osmeta['last_command_accepted_ns'] <= 100_000_000, 'command loss protection late')
            require(osmeta['last_command_source_ns'] <= plant['last_valid_command_source_ns'], 'bad traffic refreshed valid command')
            if scenario == 'corrupt':
                require(osmeta['rejected'] > 20, 'corrupt CAN did not continue')
    ran = [j for j in jobs if j['start_ns']]
    return dict(verdict='PASS', scope='hosted OSEK OS functional pilot; RTE/BSW and Target/system TC NOT RUN',
                os=osmeta, plant=plant, nominal_tick_ns=10_000_000,
                release_interval_ms=distribution([(b['release_ns']-a['release_ns'])/1e6 for a,b in zip(jobs,jobs[1:])]),
                release_to_start_ms=distribution([(j['start_ns']-j['release_ns'])/1e6 for j in ran]),
                release_to_end_ms=distribution([(j['end_ns']-j['release_ns'])/1e6 for j in ran]),
                nominal_wall_drift_ms=(jobs[-1]['release_ns']-jobs[0]['release_ns']-(len(jobs)-1)*10_000_000)/1e6,
                wall_timing_verdict='NOT ACCEPTED: virtual tick and host monotonic time are measured separately')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, default=ROOT / 'build/m3-rtos-host')
    parser.add_argument('--pilot-dir', type=Path, default=ROOT / 'build/m3-rtos-pilot')
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'build/deps/trampoline')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=1)
    args = parser.parse_args()
    require(1 <= args.repetitions <= 10, 'repetitions must be 1..10')
    output, pilot, build = (p.resolve() for p in (args.output_dir, args.pilot_dir, args.build_dir))
    output.mkdir(parents=True, exist_ok=False)
    built = json.loads((pilot/'build.json').read_text())
    require(digest(pilot/'steering_rtos') == built['binary_sha256'], 'RTOS binary differs from build record')
    for path, expected in built['input_sha256'].items():
        require(digest(ROOT/path)==expected, 'RTOS build is stale: '+path)
    for path, expected in built['bridge_libraries'].items():
        require(digest(Path(path))==expected, 'RTOS linked archive changed: '+path)
    tracked = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    sources = {p: digest(ROOT / p) for p in sorted(set(tracked)) if (ROOT / p).is_file() and (Path(p).suffix in ('.c','.cpp','.h','.hpp','.py','.json','.oil','.in','.yaml') or p == 'CMakeLists.txt')}
    env = dict(utc_started=datetime.now(timezone.utc).isoformat(), commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
               source_sha256=sources, rtos_build=built,
               plant_binary_sha256=digest(build / 'actuator_demo'), linux_kernel=os.uname().release, allowed_cpus=sorted(os.sched_getaffinity(0)))
    (output / 'environment.json').write_text(json.dumps(env, indent=2)+'\n')
    interface = 'rtospilot0'
    subprocess.run(['ip','link','add','dev',interface,'type','vcan'],check=True)
    reports = []
    try:
        subprocess.run(['ip','link','set','dev',interface,'mtu','72','up'],check=True)
        for repetition in range(args.repetitions):
            for scenario in SCENARIOS:
                directory = output / f'{scenario}-{repetition+1}'; directory.mkdir()
                parent_channel, child_channel = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET|socket.SOCK_NONBLOCK)
                enable = time.monotonic_ns()+500_000_000
                processes = []
                report = dict(scenario=scenario,directory=str(directory),verdict='FAIL')
                with (directory/'rtos.log').open('w') as rlog, (directory/'plant.log').open('w') as plog:
                    try:
                        rt = subprocess.Popen([str(pilot/'steering_rtos'),interface,str(child_channel.fileno()),str(enable),scenario,str(directory)],
                            pass_fds=(child_channel.fileno(),),stdin=subprocess.PIPE,stdout=rlog,stderr=subprocess.STDOUT,start_new_session=True,
                            env=dict(os.environ,VIPER_PATH=str(args.source_dir.resolve()/'viper')))
                        processes.append(rt)
                        pt = subprocess.Popen([str(build/'actuator_demo'),'steering-rtos-plant',scenario,interface,str(parent_channel.fileno()),str(enable),str(directory)],
                            pass_fds=(parent_channel.fileno(),),stdout=plog,stderr=subprocess.STDOUT,start_new_session=True)
                        processes.append(pt)
                        parent_channel.close(); child_channel.close()
                        require(pt.wait(timeout=8)==0, 'plant process failed')
                        require(rt.wait(timeout=4)==0, 'RTOS process failed')
                        report.update(analyze(directory,scenario))
                    except (AssertionError,ValueError,KeyError,OSError,subprocess.SubprocessError) as error:
                        report['error'] = str(error)
                    finally:
                        parent_channel.close(); child_channel.close()
                        for process in processes:
                            # The POSIX target forks a console shim and ViPer; own the entire group.
                            try: os.killpg(process.pid,signal.SIGKILL)
                            except ProcessLookupError: pass
                            process.wait()
                            if process.stdin: process.stdin.close()
                        # Upstream leaves some per-application POSIX IPC names behind.
                        metadata=directory/'rtos-start.json'
                        if metadata.exists():
                            pid=json.loads(metadata.read_text())['rtos_pid']
                            for prefix in ('viper.data.','viper.ctrl.','viper.stat.','sem.viper.rsem.','sem.viper.wsem.'):
                                (Path('/dev/shm')/(prefix+str(pid))).unlink(missing_ok=True)
                reports.append(report)
                print(directory.name,report['verdict'],report.get('error',''),flush=True)
    finally:
        subprocess.run(['ip','link','delete','dev',interface],check=True)
    summary = dict(verdict='PASS' if all(r['verdict']=='PASS' for r in reports) else 'FAIL',runs=reports,system_tc='NOT RUN')
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (output/'artifact-sha256.json').write_text(json.dumps({str(p.relative_to(output)):digest(p) for p in output.rglob('*') if p.is_file()},indent=2)+'\n')
    return int(summary['verdict']!='PASS')


if __name__ == '__main__':
    raise SystemExit(main())
