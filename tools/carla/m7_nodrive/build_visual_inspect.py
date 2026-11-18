"""Build an isolated read-only visual inspection module from verified parent objects.

No install, external source edits, physics hooks, or authority changes. Existing
build_endurance.py performs guarded baseline install/restoration after compilation.
"""
import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess

from build_endurance import sha, stopped


def patched_port(source, header, parent_folder, generated):
    # The other four sources in this unity use the parent's private headers.
    # Use the same physical files so pragma-once and native ABI stay identical.
    for name, digest in generated.items():
        include = f'#include "{name}"'
        if name.endswith(('.hpp', '.h')) and include in source:
            original = parent_folder/name
            if sha(original) != digest:
                raise ValueError(f'Parent header changed: {original}')
            source = source.replace(include, f'#include "{original}"')
    marker = '#include "Carla.h"'
    assert source.count(marker) == 1
    source = source.replace(marker, marker + '\n#include "' + str(header) + '"')
    before = ('std::string Request(UCarlaEpisode& Episode, const std::string& Input, bool& Tick) {\n'
              '  return RequestImpl(Episode,&Input,Json(),Tick);\n}')
    after = ('std::string Request(UCarlaEpisode& Episode, const std::string& Input, bool& Tick) {\n'
             '  std::string Inspected;\n'
             '  if(StrataM10VisualInspect::Request(Episode,Input,S.Locked,Inspected)) {Tick=false;return Inspected;}\n'
             '  return RequestImpl(Episode,&Input,Json(),Tick);\n}')
    assert source.count(before) == 1
    return source.replace(before, after)


def main(args):
    stopped()
    own = Path(__file__).resolve().parent
    parent_path = args.parent.resolve()
    parent = json.loads(parent_path.read_text())
    installed = Path(parent['module_path'])
    # Compilation never changes the installed module. A completed parent's
    # postprocessing may still own its candidate before guarded restoration.
    assert sha(installed) in (parent['original_sha256'], parent['module_sha256']), 'declared runtime only'
    original = parent_path.parent/'original.so'
    assert sha(original) == parent['original_sha256'], 'verified original module'
    response_path = parent_path.parent / 'module.response'
    assert sha(response_path) == parent['generated']['module.response']
    response = response_path.read_text()
    objects = [Path(x) for x in shlex.split(response) if x.endswith('.o')]
    for path in objects:
        expected = parent['inputs'].get(str(path)) or parent['generated'].get(path.name)
        assert expected and sha(path) == expected, 'parent object changed: ' + str(path)
    old_object, = [p for p in objects if p.name == 'Module.Carla.2_of_4.cpp.o']
    old_folder = old_object.parent
    prior_path = old_folder / 'manifest.json'
    prior = json.loads(prior_path.read_text())
    for name in ('Module.Carla.2_of_4.cpp', 'M7NoDrivePort.cpp'):
        assert sha(old_folder/name) == prior['generated'][name]
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(original, out/'original.so')
    shutil.copy2(own/'visual_inspect.hpp', out/'visual_inspect.hpp')
    port = out/'M7NoDrivePort.cpp'
    port.write_text(patched_port((old_folder/port.name).read_text(), out/'visual_inspect.hpp',
                                 old_folder, prior['generated']))
    unity = out/'Module.Carla.2_of_4.cpp'
    original_unity = (old_folder/unity.name).read_text()
    assert original_unity.count(str(old_folder/port.name)) == 1
    unity.write_text(original_unity.replace(str(old_folder/port.name), str(port)))
    command = list(prior['commands'][0])
    command[command.index(str(old_folder/unity.name))] = str(unity)
    command[command.index('-o')+1] = str(out/old_object.name)
    command = [('-MF'+str(out/'module.d')) if x.startswith('-MF') else x for x in command]
    command += ['-I'+str(old_folder)]
    local_response = out/'module.response'
    assert response.count(str(old_object)) == 1
    local_response.write_text(response.replace(str(old_object), str(out/old_object.name)))
    link = list(parent['commands'][1])
    reference = next(i for i,x in enumerate(link) if x.startswith('-Wl,@'))
    link[reference] = '-Wl,@'+str(local_response)
    link[link.index('-o')+1] = str(out/installed.name)
    commands = [command, link, ['strip', '--strip-debug', str(out/installed.name)]]
    engine = args.engine.resolve()/'Engine'
    for i, cmd in enumerate(commands):
        with (out/f'build-{i}.log').open('w') as log:
            subprocess.run(cmd, cwd=engine/'Source', stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=300)
    inputs = {own/'build_visual_inspect.py', own/'visual_inspect.hpp', parent_path,
              response_path, prior_path, original, old_folder/port.name, old_folder/unity.name,
              Path(command[0]), *objects}
    inputs.update(Path(line.split('"')[1]) for line in original_unity.splitlines()
                  if line.startswith('#include "'))
    inputs.update(Path(p) for p in prior['inputs'] if Path(p).is_file())
    result = dict(schema='m10-endurance-build-v1', module_path=str(installed),
        original_sha256=parent['original_sha256'], module_sha256=sha(out/installed.name),
        parent_module_sha256=parent['module_sha256'], scope=__doc__, commands=commands,
        inputs={str(p):sha(p) for p in sorted(inputs)},
        generated={p.name:sha(p) for p in sorted(out.iterdir())
                   if p.is_file() and p.suffix not in ('.log','.d')})
    (out/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(module_sha256=result['module_sha256'], installed=False)), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'parent', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    main(p.parse_args())
