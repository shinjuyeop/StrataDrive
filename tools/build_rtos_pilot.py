#!/usr/bin/env python3
"""Explicit, pinned Trampoline build; never downloads during a normal CMake build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(command, directory, log, env=None):
    result = subprocess.run(list(map(str, command)), cwd=directory, stdout=log,
                            stderr=subprocess.STDOUT, env=env, check=False)
    if result.returncode:
        raise RuntimeError(f"exit {result.returncode}: {command}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, default=ROOT / 'build/m3-rtos-host')
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'build/deps/trampoline')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build/m3-rtos-pilot')
    parser.add_argument('--fetch', action='store_true', help='explicitly fetch the pinned upstream revision if absent')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 16:
        parser.error('jobs must be 1..16')
    lock = json.loads((ROOT / 'third_party/trampoline.json').read_text())
    source, build, output = (p.resolve() for p in (args.source_dir, args.build_dir, args.output_dir))
    output.mkdir(parents=True, exist_ok=True)
    cache=build/'CMakeCache.txt'
    if cache.exists() and 'STRATADRIVE_SANITIZERS:BOOL=ON' in cache.read_text():
        raise RuntimeError('hosted alternate-stack kernel is not validated with sanitizers; use a separate pilot build')
    with (output / 'build.log').open('w') as log:
        if not source.exists():
            if not args.fetch:
                parser.error('source absent; use --fetch or provide a checkout of the locked commit')
            source.mkdir(parents=True)
            run(['git', 'init'], source, log)
            run(['git', 'remote', 'add', 'origin', lock['repository']], source, log)
            run(['git', 'fetch', '--depth', '1', 'origin', lock['commit']], source, log)
            run(['git', 'checkout', '--detach', 'FETCH_HEAD'], source, log)
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
        dirty = subprocess.check_output(['git', 'diff', 'HEAD', '--name-only'], cwd=source, text=True).strip()
        if commit != lock['commit'] or dirty:
            raise RuntimeError('upstream revision differs or tracked source was modified')
        run(['python3', 'build.py', 'release', args.jobs], source / 'goil/makefile-unix', log)
        run(['make', '-j', args.jobs], source / 'viper', log)
        run(['cmake', '-S', ROOT, '-B', build, '-DBUILD_TESTING=OFF', '-DSTRATADRIVE_TRAMPOLINE_PILOT=ON'], ROOT, log)
        run(['cmake', '--build', build, '--parallel', args.jobs, '--target', 'steering_rtos_bridge', 'actuator_demo'], ROOT, log)
        adapter = ROOT / 'vecu/platform/trampoline_posix'
        for name in ('steering.c', 'pilot_bridge.h'):
            shutil.copy2(adapter / name, output / name)
        names = ('steering_rtos_bridge', 'steering_actuator', 'steering_response_monitor', 'steering_receiver',
                 'steering_frame_codec', 'steering_angle_codec', 'actuator_receiver_state', 'actuator_socketcan',
                 'socketcan_endpoint', 'actuator_payload_codec', 'e2e_profile5')
        libraries = [build / ('lib' + n + '.a') for n in names]
        if any(not p.is_file() for p in libraries):
            raise RuntimeError('missing CMake bridge dependency')
        # The upstream generator splits linker flags on whitespace.
        if any(any(c.isspace() or c in '\\"' for c in str(p)) for p in [source, output, *libraries]):
            raise RuntimeError('upstream POSIX build requires paths without whitespace, quotes or backslashes')
        oil = (adapter / 'steering.oil.in').read_text().replace('@TRAMPOLINE@', json.dumps(str(source)))
        oil = oil.replace('@LIBRARIES@', json.dumps('-Wl,--start-group ' + ' '.join(map(str, libraries)) + ' -Wl,--end-group -lrt -lpthread'))
        (output / 'steering.oil').write_text(oil)
        goil = source / 'goil/makefile-unix/goil'
        env = dict(os.environ, PATH=str(goil.parent) + os.pathsep + os.environ.get('PATH', ''))
        run([goil, '--target=posix/linux', '--templates=' + str(source / 'goil/templates'), 'steering.oil'], output, log, env)
        run(['python3', 'build.py', 'all', args.jobs], output, log, env)
        def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
        evidence = dict(upstream=lock, license_sha256=digest(source / lock['kernel_license_file']),
                        goil_version=subprocess.check_output([goil, '--version'], text=True),
                        goil_binary_sha256=digest(goil), viper_binary_sha256=digest(source/'viper/viper'),
                        cmake_cache_sha256=digest(build/'CMakeCache.txt'), compiler=subprocess.check_output(['g++','--version'],text=True),
                        binary_sha256=digest(output / 'steering_rtos'), bridge_libraries={str(p): digest(p) for p in libraries},
                        input_sha256={str(p.relative_to(ROOT)): digest(p) for p in adapter.iterdir() if p.is_file()})
        (output / 'build.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(output / 'steering_rtos')


if __name__ == '__main__':
    main()
