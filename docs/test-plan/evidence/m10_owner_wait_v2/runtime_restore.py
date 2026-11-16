"""Idempotent orchestration guard around the unchanged strict runtime installers."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


def restore(root, series, work, output, raise_on_failure=True):
    sys.path.insert(0, str(root/'tests/integration/perception'))
    from runtime_restoration_v1 import restore_component, sha
    original = json.loads((series/'pre-install.json').read_text())['files']
    module = json.loads((root/'build/m10-owner-wait-v1/server-build-01/manifest.json').read_text())
    dxc = json.loads((root/'build/m10-dxc-lifetime-v1/manifest.json').read_text())
    engine = '/d/shin/stratadrive-tools/UnrealEngine_4.26'
    carla = '/d/shin/stratadrive-tools/m7-source/carla-0.9.16'
    components = [
        ('dxcompiler', dxc['installed_path'], dxc['candidate_sha256'], dxc['original_sha256'],
         ['python3', root/'tools/carla/m7_nodrive/build_dxc_lifetime.py', '--engine', engine,
          '--output', root/'build/m10-dxc-lifetime-v1', '--restore']),
        ('module', module['module_path'], module['module_sha256'], module['original_sha256'],
         ['python3', root/'tools/carla/m7_nodrive/build_endurance.py', '--engine', engine,
          '--source', carla, '--output', root/'build/m10-owner-wait-v1/server-build-01', '--restore'])]
    reports, errors, files = {}, [], {}
    processes = subprocess.check_output(['ps', '-eo', 'comm='], text=True).splitlines()
    if any(name.strip() == 'UE4Editor' for name in processes):
        errors.append('runtime restoration requires no UE4Editor process')
    else:
        for name, path, candidate, baseline, argv in components:
            try:
                assert path == original[name]['path'] and baseline == original[name]['sha256']
                def command():
                    with (work/('guarded-restore-'+name+'.log')).open('w') as log:
                        return subprocess.run(list(map(str, argv)), stdout=log, stderr=subprocess.STDOUT).returncode
                reports[name] = restore_component(path, baseline, candidate, command)
            except Exception as error:
                errors.append(name+': '+str(error))
    for name, item in original.items():
        try:
            files[name] = dict(item, checked_sha256=sha(item['path']))
            if files[name]['checked_sha256'] != item['sha256']:
                errors.append(name+': original hash not restored')
        except Exception as error:
            errors.append(name+': '+str(error))
    result = dict(status='FAIL' if errors else 'PASS', components=reports, files=files,
                  errors=errors, checked_utc=datetime.now(timezone.utc).isoformat())
    assert not output.exists(), 'immutable restoration record'
    output.write_text(json.dumps(result, indent=2)+'\n')
    if errors and raise_on_failure:
        raise RuntimeError('runtime restoration failed; see '+str(output))
    return result
