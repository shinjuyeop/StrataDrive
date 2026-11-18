"""Isolated Carla unity rebuild for optional NullRHI-only visual proxy omission.

Reuse the declared recovery module's unchanged physics/native unity. Never edit
the external source tree, change actor schemas, or install while a server lives.
Install/restore uses build_endurance.py with the resulting compatible manifest.
"""
import argparse
import difflib
import json
from pathlib import Path
import shlex
import shutil
import subprocess

from build_endurance import sha, stopped


def patch(source, header):
    marker = 'namespace crp = carla::rpc;'
    assert source.count(marker) == 1
    result = source.replace(marker, '#include "'+str(header)+'"\n\n'+marker)
    for tail in ('GetStaticMesh()', 'GetSkeletalMeshRenderData()'):
        before = 'if(!Component->IsVisible() || !Component->'+tail+')'
        assert result.count(before) == 1
        result = result.replace(before, 'if(StrataM10OmitVisualTags() || !Component->IsVisible() || !Component->'+tail+')')
    marker = '    // Find a tagged component that is attached to this component\n    UTaggedLandscapeComponent'
    assert result.count(marker) == 1
    return result.replace(marker, '    if (StrataM10OmitVisualTags()) { continue; }\n\n'+marker)


def main(a):
    if not a.offline_quality:
        stopped()
    root = Path(__file__).resolve().parents[3]
    own = Path(__file__).resolve().parent
    out = a.output.resolve(); parent_path = a.parent.resolve()
    parent = json.loads(parent_path.read_text())
    installed = Path(parent['module_path'])
    original = parent_path.parent/'original.so' if a.offline_quality else installed
    assert sha(original) == parent['original_sha256'], 'verified original module required'
    if a.offline_quality and 'quality_asset_barrier.hpp' not in parent['generated']:
        raise ValueError('offline warmup must expose the game resource barrier')
    for name in ('module.response', 'libUE4Editor-Carla.so', 'Module.Carla.2_of_4.cpp.o'):
        assert sha(parent_path.parent/name) == parent['generated'][name], name
    plugin = a.source.resolve()/'Unreal/CarlaUE4/Plugins/Carla'
    engine = a.engine.resolve()/'Engine'
    intermediate = plugin/'Intermediate/Build/Linux/B4D820EA/UE4Editor/Development/Carla'
    unity = intermediate/'Module.Carla.1_of_4.cpp'
    tagger = plugin/'Source/Carla/Game/Tagger.cpp'
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(original, out/'original.so')
    shutil.copy2(own/'owner_visual_tags.hpp', out/'owner_visual_tags.hpp')
    if a.offline_quality:
        local_header = out/'owner_visual_tags.hpp'
        source_header = local_header.read_text()
        anchor = '    const bool Requested ='
        assert source_header.count(anchor) == 1
        local_header.write_text(source_header.replace(anchor, '''    // This private process only primes assets. Its game-mode warmup has no sensors or model.
    if (FParse::Param(FCommandLine::Get(), TEXT("StrataM10QualityAssetBarrier")) &&
        FParse::Param(FCommandLine::Get(), TEXT("StrataM10AssetWarmNoTags"))) return true;
''' + anchor))
    before = tagger.read_text(); after = patch(before, out/'owner_visual_tags.hpp')
    (out/'Tagger.cpp').write_text(after)
    (out/'Tagger.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
        fromfile=str(tagger), tofile='isolated/Tagger.cpp')))
    membership = unity.read_text()
    assert membership.count(str(tagger)) == 1
    local = out/unity.name
    local.write_text(membership.replace(str(tagger), str(out/'Tagger.cpp')))
    rsp = Path(str(unity)+'.o.rsp'); args = shlex.split(rsp.read_text())
    obj = out/(unity.name+'.o')
    args[args.index('-o')+1] = str(obj)
    args[args.index(str(unity))] = str(local)
    args = [('-MF'+str(out/'module.d')) if x.startswith('-MF') else x for x in args]
    pch = next(i for i,x in enumerate(args) if x.endswith('/SharedPCH.UnrealEd.Cpp17.h'))
    assert args[pch-1] == '-include'
    del args[pch-1:pch+1]
    header = engine/'Source/Editor/UnrealEd/Public/UnrealEdSharedPCH.h'
    args += ['-include', str(header), '-I'+str(tagger.parent)]
    compiler = parent['commands'][0][0]
    commands = [[compiler, *args]]
    response = (parent_path.parent/'module.response').read_text()
    for name in shlex.split(response):
        if name.endswith('.o'):
            expected = parent['inputs'].get(name) or parent['generated'].get(Path(name).name)
            assert expected and sha(name) == expected, 'unchanged link object '+name
    (old_obj,) = [Path(token) for token in shlex.split(response) if token.endswith('/'+obj.name)]
    (out/'module.response').write_text(response.replace(str(old_obj), str(obj)))
    link = list(parent['commands'][1])
    ref = next(i for i,x in enumerate(link) if x.startswith('-Wl,@'))
    link[ref] = '-Wl,@'+str(out/'module.response')
    link[link.index('-o')+1] = str(out/installed.name)
    commands += [link, ['strip', '--strip-debug', str(out/installed.name)]]
    for i, command in enumerate(commands):
        with (out/f'build-{i}.log').open('w') as log:
            subprocess.run(command, cwd=engine/'Source', stdout=log, stderr=subprocess.STDOUT,
                check=True, timeout=900)
    inputs = {own/'build_owner_visual_tags.py', own/'owner_visual_tags.hpp', parent_path,
        parent_path.parent/'module.response', tagger, unity, rsp, header, Path(compiler)}
    inputs.update(Path(line.split('"')[1]) for line in membership.splitlines() if line.startswith('#include "'))
    inputs.update(Path(x) for x in shlex.split(response) if Path(x).is_file())
    manifest = dict(schema='m10-endurance-build-v1', module_path=str(installed),
        original_sha256=parent['original_sha256'], module_sha256=sha(out/installed.name),
        parent_module_sha256=parent['module_sha256'], scope=__doc__, commands=commands,
        inputs={str(p):sha(p) for p in sorted(inputs)},
        generated={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.suffix not in ('.log','.d')})
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    if a.offline_quality:
        manifest['offline_game_asset_warmup'] = True
        manifest['barrier_sha256'] = parent['generated']['quality_asset_barrier.hpp']
        (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(module_sha256=manifest['module_sha256'], installed=False)), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'source', 'parent', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument("--offline-quality", action="store_true")
    main(p.parse_args())
