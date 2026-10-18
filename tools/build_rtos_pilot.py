#!/usr/bin/env python3
"""Explicit, pinned Trampoline build; never downloads during a normal CMake build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ELF_MACHINES = {62: 'x86_64', 183: 'aarch64'}


def elf_architecture(path):
    """Inspect the output, rather than inferring its architecture from a flag."""
    with path.open('rb') as stream:
        header = stream.read(20)
    if len(header) != 20 or header[:6] != b'\x7fELF\x02\x01':
        raise ValueError(f'expected a 64-bit little-endian ELF: {path}')
    machine = struct.unpack_from('<H', header, 18)[0]
    if machine not in ELF_MACHINES:
        raise ValueError(f'unsupported ELF machine {machine}: {path}')
    return ELF_MACHINES[machine]


def validate_runtime_architecture(artifacts, host=None):
    host = host or platform.machine()
    host = {'arm64': 'aarch64', 'amd64': 'x86_64'}.get(host, host)
    for artifact in artifacts:
        actual = elf_architecture(artifact)
        if actual != host:
            raise ValueError(f'cannot execute {actual} artifact on {host}: {artifact}; cross-build is not a runtime test')


def elf_runtime_requirements(path):
    """Record loader/library ABI requirements without executing a target binary."""
    headers = subprocess.check_output(['readelf', '-lW', path], text=True)
    dynamic = subprocess.check_output(['readelf', '-dW', path], text=True)
    versions = subprocess.check_output(['readelf', '--version-info', path], text=True)
    interpreter = re.search(r'Requesting program interpreter: ([^\]]+)', headers)
    return dict(interpreter=interpreter.group(1) if interpreter else None,
                needed_libraries=re.findall(r'Shared library: \[([^\]]+)\]', dynamic),
                required_symbol_versions=sorted(set(re.findall(r'Name: (\S+)', versions))))


def validate_cached_compiler(build, compiler):
    # A toolchain may set a normal CMake variable, leaving no compiler entry in
    # CMakeCache.txt. Include CMake's detected compiler instead of guessing.
    cached = re.findall(r'^CMAKE_CXX_COMPILER:[^=\n]+=([^\n]+)', (build / 'CMakeCache.txt').read_text(), re.MULTILINE)
    for detected in build.glob('CMakeFiles/*/CMakeCXXCompiler.cmake'):
        cached += re.findall(r'set\(CMAKE_CXX_COMPILER "([^"]+)"\)', detected.read_text())
    requested = Path(shutil.which(compiler) or compiler).resolve()
    if not cached or any(Path(shutil.which(path) or path).resolve() != requested for path in cached):
        raise RuntimeError('CMake compiler differs; use a fresh architecture-specific build directory')


def run(command, directory, log, env=None):
    result = subprocess.run(list(map(str, command)), cwd=directory, stdout=log,
                            stderr=subprocess.STDOUT, env=env, check=False)
    if result.returncode:
        raise RuntimeError(f"exit {result.returncode}: {command}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--architecture', choices=('native', 'aarch64'), default='native')
    parser.add_argument('--build-dir', type=Path)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'build/deps/trampoline')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--fetch', action='store_true', help='explicitly fetch the pinned upstream revision if absent')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 16:
        parser.error('jobs must be 1..16')
    lock = json.loads((ROOT / 'third_party/trampoline.json').read_text())
    cross = args.architecture == 'aarch64'
    build = (args.build_dir or ROOT / ('build/m3-rtos-aarch64-host' if cross else 'build/m3-rtos-host')).resolve()
    output = (args.output_dir or ROOT / ('build/m3-rtos-aarch64-pilot' if cross else 'build/m3-rtos-pilot')).resolve()
    source = args.source_dir.resolve()
    toolchain = ROOT / 'cmake/toolchains/aarch64-linux-gnu.cmake' if cross else None
    cc, cxx = ('aarch64-linux-gnu-gcc', 'aarch64-linux-gnu-g++') if cross else ('gcc', 'g++')
    if any(not shutil.which(tool) for tool in (cc, cxx, 'readelf')):
        parser.error(f'install/provide {cc}, {cxx} and readelf; no toolchain is downloaded automatically')
    if build == output or source in build.parents or source in output.parents or source in (build, output):
        parser.error('use distinct build/output directories outside the upstream source checkout')
    architecture = 'aarch64' if cross else {'arm64': 'aarch64', 'amd64': 'x86_64'}.get(platform.machine(), platform.machine())
    previous = output / 'build.json'
    if previous.exists() and json.loads(previous.read_text()).get('architecture', architecture) != architecture:
        parser.error('output architecture differs; use a fresh architecture-specific output directory')
    output.mkdir(parents=True, exist_ok=True)
    cache=build/'CMakeCache.txt'
    if cache.exists() and 'STRATADRIVE_SANITIZERS:BOOL=ON' in cache.read_text():
        raise RuntimeError('hosted alternate-stack kernel is not validated with sanitizers; use a separate pilot build')
    # Never reuse native objects for a cross build, or silently change its compiler.
    if cache.exists():
        validate_cached_compiler(build, cxx)
    (output / 'build.json').unlink(missing_ok=True)  # A failed rebuild cannot retain a successful manifest.
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
        # ViPer is target code; GOIL above is always a host executable. Keep their
        # objects apart so native/cross builds cannot contaminate one another.
        viper = output / 'viper'
        viper.mkdir(exist_ok=True)
        run(['make', '-j', args.jobs, 'CC=' + cc, 'OBJ_DIR=' + str(viper / 'obj'), 'EXE=' + str(viper / 'viper')], source / 'viper', log)
        configuration = ['cmake', '-S', ROOT, '-B', build, '-DBUILD_TESTING=OFF', '-DSTRATADRIVE_TRAMPOLINE_PILOT=ON']
        if toolchain:
            configuration += ['-DCMAKE_TOOLCHAIN_FILE=' + str(toolchain)]
        run(configuration, ROOT, log)
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
        oil = oil.replace('@CC@', json.dumps(cc)).replace('@CXX@', json.dumps(cxx))
        oil = oil.replace('@LIBRARIES@', json.dumps('-Wl,--start-group ' + ' '.join(map(str, libraries)) + ' -Wl,--end-group -lrt -lpthread'))
        (output / 'steering.oil').write_text(oil)
        goil = source / 'goil/makefile-unix/goil'
        env = dict(os.environ, PATH=str(goil.parent) + os.pathsep + os.environ.get('PATH', ''))
        run([goil, '--target=posix/linux', '--templates=' + str(source / 'goil/templates'), 'steering.oil'], output, log, env)
        run(['python3', 'build.py', 'all', args.jobs], output, log, env)
        def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
        artifacts = [output / 'steering_rtos', viper / 'viper', build / 'actuator_demo']
        if any(elf_architecture(p) != architecture for p in artifacts):
            raise RuntimeError('compiler output architecture differs from requested architecture')
        tracked = subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
        inputs = [ROOT / p for p in tracked if Path(p).suffix in ('.cpp', '.hpp', '.c', '.h') or p == 'CMakeLists.txt']
        inputs += [p for p in adapter.iterdir() if p.is_file()] + [Path(__file__).resolve(), ROOT / 'third_party/trampoline.json']
        if toolchain:
            inputs.append(toolchain)
        evidence = dict(upstream=lock, license_sha256=digest(source / lock['kernel_license_file']),
                        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                        working_tree=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines(),
                        goil_version=subprocess.check_output([goil, '--version'], text=True),
                        goil_binary_sha256=digest(goil), viper_binary_sha256=digest(viper / 'viper'), viper_path=str(viper / 'viper'),
                        cmake_cache_sha256=digest(build/'CMakeCache.txt'), compiler=subprocess.check_output([cxx,'--version'],text=True),
                        compiler_target=subprocess.check_output([cxx,'-dumpmachine'],text=True).strip(),
                        compiler_sysroot=subprocess.check_output([cxx,'-print-sysroot'],text=True).strip(),
                        architecture=architecture, host_architecture=platform.machine(),
                        runtime_validation='NOT RUN by builder; cross-build does not demonstrate Jetson/JetPack compatibility',
                        elf_artifacts={str(p): dict(architecture=elf_architecture(p), sha256=digest(p),
                                                   runtime_requirements=elf_runtime_requirements(p)) for p in artifacts},
                        binary_sha256=digest(output / 'steering_rtos'), bridge_libraries={str(p): digest(p) for p in libraries},
                        input_sha256={str(p.relative_to(ROOT)): digest(p) for p in inputs})
        (output / 'build.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(output / 'steering_rtos')


if __name__ == '__main__':
    main()
