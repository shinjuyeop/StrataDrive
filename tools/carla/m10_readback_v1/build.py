#!/usr/bin/env python3
"""Isolated, pinned CARLA unity rebuild; atomic opt-in install and exact restore."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

BASELINE = "099f15274e768049c774166b17eb55838e672f9098f7d9e9f89aeddab6f81134"
CAMERA = "50819673b85e7ebd7b071457cc9c4923ec600886c36aded5c4d1012797d1e333"


def digest(p):
    with Path(p).open("rb") as f:
        h = hashlib.sha256()
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def once(s, before, after):
    if s.count(before) != 1:
        raise ValueError("nonunique build anchor: " + before)
    return s.replace(before, after, 1)


def stopped():
    if (
        subprocess.run(
            ["pgrep", "-x", "UE4Editor"], stdout=subprocess.DEVNULL
        ).returncode
        == 0
    ):
        raise RuntimeError("UE4Editor is running")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("engine", "source", "output"):
        p.add_argument("--" + n, type=Path, required=True)
    p.add_argument("--install", action="store_true")
    p.add_argument("--restore", action="store_true")
    a = p.parse_args()
    if a.install and a.restore:
        p.error("choose install or restore")
    engine, source, out = (
        a.engine.resolve() / "Engine",
        a.source.resolve(),
        a.output.resolve(),
    )
    plugin = source / "Unreal/CarlaUE4/Plugins/Carla"
    module = plugin / "Binaries/Linux/libUE4Editor-Carla.so"
    backup, binary = (
        out / "original-libUE4Editor-Carla.so",
        out / "libUE4Editor-Carla.so",
    )
    if a.install or a.restore:
        stopped()
        m = json.loads((out / "manifest.json").read_text())
        expected = m["instrumented_module_sha256"]
        if digest(backup) != BASELINE or digest(binary) != expected:
            raise ValueError("binary/backup pin")
        if digest(module) != (expected if a.restore else BASELINE):
            raise ValueError("installed module identity")
        temporary = Path(str(module) + ".m10-new")
        shutil.copy2(backup if a.restore else binary, temporary)
        stopped()
        temporary.replace(module)
        print(
            json.dumps(
                {
                    "restored": a.restore,
                    "installed": a.install,
                    "sha256": digest(module),
                }
            )
        )
        return
    if out.exists():
        raise ValueError("fresh output required")
    if digest(module) != BASELINE:
        raise ValueError("baseline module pin")
    for root, head in (
        (source, "294096eb1c38eabf246e4f3a9cdab704e33a7f4c"),
        (a.engine, "e9d9e60c85f643e10eeb03f42f61554d18dcb30f"),
    ):
        if (
            subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
            ).strip()
            != head
        ):
            raise ValueError("external source HEAD")
    intermediate = (
        plugin / "Intermediate/Build/Linux/B4D820EA/UE4Editor/Development/Carla"
    )
    camera = plugin / "Source/Carla/Sensor/SceneCaptureCamera.cpp"
    if digest(camera) != CAMERA:
        raise ValueError("camera source pin")
    out.mkdir(parents=True)
    shutil.copy2(module, backup)
    own = Path(__file__).resolve().parent
    shutil.copy2(own / "readback.inc", out / "readback.inc")
    generated = out / camera.name
    text = once(
        camera.read_text(),
        "#include <chrono>",
        '#include <chrono>\n#include "readback.inc"',
    )
    text = once(
        text,
        "  FPixelReader::SendPixelsInRenderThread<ASceneCaptureCamera, FColor>(*this);",
        "  if (StrataM10Readback::Enabled()) StrataM10Readback::Send(*this, GetDataStream(*this));\n"
        "  else FPixelReader::SendPixelsInRenderThread<ASceneCaptureCamera, FColor>(*this);",
    )
    generated.write_text(text)
    unity = intermediate / "Module.Carla.3_of_4.cpp"
    local_unity = out / unity.name
    local_unity.write_text(once(unity.read_text(), str(camera), str(generated)))
    compiler = (
        engine
        / "Extras/ThirdPartyNotUE/SDKs/HostLinux/Linux_x64/v17_clang-10.0.1-centos7/x86_64-unknown-linux-gnu/bin/clang++"
    )
    rsp = intermediate / (unity.name + ".o.rsp")
    args = shlex.split(rsp.read_text())
    obj = out / (unity.name + ".o")
    args[args.index("-o") + 1] = str(obj)
    args[args.index(str(unity))] = str(local_unity)
    args = [("-MF" + str(out / "unity.d")) if x.startswith("-MF") else x for x in args]
    command = [str(compiler), *args]
    with (out / "compile.log").open("w") as log:
        subprocess.run(
            command,
            cwd=engine / "Source",
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    linkfile = (
        engine
        / "Intermediate/Build/Linux/B4D820EA/UE4Editor/Development/Link-libUE4Editor-Carla.so.link.sh"
    )
    link = shlex.split(
        next(x for x in linkfile.read_text().splitlines() if " -shared " in x)
    )
    ref = next(x for x in link if x.startswith("-Wl,@"))
    original_response = Path(ref[5:])
    response = out / "module.response"
    response.write_text(
        once(original_response.read_text(), str(unity) + ".o", str(obj))
    )
    link[link.index(ref)] = "-Wl,@" + str(response)
    link[link.index("-o") + 1] = str(binary)
    with (out / "link.log").open("w") as log:
        subprocess.run(
            link,
            cwd=engine / "Source",
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    subprocess.run(["strip", "--strip-debug", str(binary)], check=True)
    inputs = [
        camera,
        unity,
        rsp,
        linkfile,
        original_response,
        compiler,
        own / "build.py",
        own / "readback.inc",
    ]
    inputs += [Path(x) for x in re.findall(r'#include "([^"]+)"', unity.read_text())]
    inputs += [
        Path(x) for x in shlex.split(original_response.read_text()) if Path(x).is_file()
    ]
    manifest = dict(
        schema="m10-readback-build-v1",
        original_module_sha256=BASELINE,
        instrumented_module_sha256=digest(binary),
        compile_command=command,
        link_command=link,
        inputs={str(x): digest(x) for x in inputs},
        generated={
            x.name: digest(x)
            for x in (generated, local_unity, out / "readback.inc", response)
        },
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": "built", "module_sha256": digest(binary)}))


if __name__ == "__main__":
    main()
