"""Reproduce DXC exit lifetime failure and verify a candidate without CARLA."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main(a):
    a.output.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).with_name('dxc_shutdown_probe.cpp').resolve()
    probe = (a.output / 'shutdown-probe').resolve()
    report = dict(status='FAIL', source_sha256=sha(source), cases=[])
    try:
        command = [a.compiler, '-std=c++17', '-fms-extensions',
                   '-I' + str(a.headers.resolve()), str(source), '-ldl', '-pthread', '-o', str(probe)]
        report['build_argv'] = command
        with (a.output / 'build.log').open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
        report['probe_sha256'] = sha(probe)
        report['libraries'] = {name: dict(path=str(path.resolve()), sha256=sha(path))
                               for name, path in [('original', a.original), ('candidate', a.candidate)]}
        for name, library, modes in [('original', a.original, ['plain', 'churn', 'churn']),
                                     ('candidate', a.candidate, ['plain'] + ['churn'] * 5)]:
            for index, mode in enumerate(modes):
                shader = (a.output / f'{name}-{index}.spv').resolve()
                argv = [str(probe), str(library.resolve()), mode, str(shader)]
                record = dict(library=name, mode=mode, argv=argv, timeout=False)
                report['cases'].append(record)
                start = time.monotonic()
                try:
                    result = subprocess.run(argv, capture_output=True, timeout=3)
                    record.update(exit=result.returncode, stdout=result.stdout.decode(errors='replace'),
                                  stderr=result.stderr.decode(errors='replace'))
                except subprocess.TimeoutExpired as error:
                    record.update(timeout=True, stdout=(error.stdout or b'').decode(errors='replace'),
                                  stderr=(error.stderr or b'').decode(errors='replace'))
                record['seconds'] = time.monotonic() - start
                record['shader_sha256'] = sha(shader)
                assert 'shader-compiled-and-released' in record['stdout']
                if mode == 'churn':
                    assert 'exit-allocations-complete' in record['stdout']
                if name == 'original' and mode == 'churn':
                    assert record['timeout'], 'original lifetime negative control did not reproduce'
                else:
                    assert not record['timeout'] and record['exit'] == 0, 'normal exit required'
        assert len({case['shader_sha256'] for case in report['cases']}) == 1, 'fixture shader changed'
        assert all(sha(path) == report['libraries'][name]['sha256']
                   for name, path in [('original', a.original), ('candidate', a.candidate)])
        report['status'] = 'PASS_ISOLATED_LIFECYCLE_ONLY'
    except Exception as error:
        report['error'] = repr(error)
    finally:
        (a.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'], cases=len(report['cases']), error=report.get('error'))))
    return 0 if report['status'].startswith('PASS') else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('headers', 'original', 'candidate', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--compiler', required=True)
    raise SystemExit(main(p.parse_args()))
