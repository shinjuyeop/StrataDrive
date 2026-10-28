#!/usr/bin/env python3
"""Install the opt-in M7 zero-effort diagnostic port into the pinned CARLA fork.

Never downloads/builds/runs the server. Refuses unknown edited integration files.
Original M6 receivers/codecs are copied byte-for-byte and compiled by UE's toolchain.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from model_header import generate
from shutdown_patch import apply as shutdown_patches
from sensor_patch import apply as sensor_patches
from rpc_shutdown_patch import apply as rpc_shutdown_patches
from engine_exit_patch import apply as engine_exit_patch

PIN = "294096eb1c38eabf246e4f3a9cdab704e33a7f4c"
ENGINE_PIN = "e9d9e60c85f643e10eeb03f42f61554d18dcb30f"
PHYSX_ROOT = Path("Engine/Source/ThirdParty/PhysX3/PhysX_3.4")
READOUT_HEADERS = {
    "Source/PhysXVehicle/src/PxVehicleSuspWheelTire4.h": "b1ff84649dfe9fd3482dff0e43ec2d665a7d86cda8b1f3e03668d7a0ebf90c98",
    "Include/vehicle/PxVehicleWheels.h": "acafe4ebd7fdbfccece76f358be2239b3272d3790c242a6ce2de208de32f6b1e",
}
PLUGIN = Path("Unreal/CarlaUE4/Plugins/Carla/Source/Carla")
NATIVE = PLUGIN.parent / "M7Native"
READ_ONLY = {
    "is_traffic_manager_running", "get_traffic_manager_running", "version",
    "get_available_maps", "get_names_of_all_objects", "get_episode_info",
    "get_map_info", "get_map_data", "get_navigation_mesh", "get_required_files",
    "request_file", "get_episode_settings", "get_actor_definitions", "get_spectator",
    "get_all_level_BBs", "get_environment_objects", "get_weather_parameters",
    "get_imui_gravity", "get_actors_by_id", "get_sensor_token",
    "is_sensor_enabled_for_ros", "get_actor_bounding_box",
    "get_actor_component_world_transform", "get_actor_component_relative_transform",
    "get_actor_bone_world_transforms", "get_vehicle_bone_world_transforms",
    "get_actor_bone_relative_transforms", "get_actor_component_names",
    "get_actor_bone_names", "get_actor_socket_world_transforms",
    "get_actor_socket_relative_transforms", "get_actor_socket_names",
    "get_physics_control", "get_vehicle_light_state", "get_wheel_steer_angle",
    "get_wheel_pitch_angle", "get_ackermann_controller_settings", "get_bones_transform",
    "get_telemetry_data", "get_vehicle_light_states", "get_group_traffic_lights",
    "get_light_boxes", "get_gbuffer_token", "are_gbuffers_enabled",
    "show_recorder_file_info", "show_recorder_collisions", "show_recorder_actors_blocked",
    "query_lights_state", "project_point", "cast_ray",
}
STEMS = {
    "common": ["e2e_profile5", "actuator_payload_codec", "actuator_receiver_state"],
    "steering": ["steering_angle_codec", "steering_frame_codec", "steering_receiver"],
    "brake": ["brake_pressure_codec", "brake_frame_codec", "brake_receiver"],
    "drive": ["drive_value_codec", "drive_frame_codec", "drive_receiver"],
    "bms": ["bms_value_codec", "bms_frame_codec", "bms_receiver"],
    "remote": ["owner_wire"],
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replace(text, before, after):
    if text.count(before) != 1:
        raise RuntimeError(f"integration anchor is not unique: {before[:100]!r}")
    return text.replace(before, after, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--carla", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True,
                        help="Pinned UE source required for the read-only internal wheel accessor; never copied or modified")
    args = parser.parse_args()
    root = args.carla.resolve()
    own = Path(__file__).resolve().parent
    project = own.parents[2]
    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if revision != PIN:
        raise RuntimeError(f"expected {PIN}; got {revision}")
    engine = args.engine.resolve()
    engine_revision = subprocess.check_output(["git", "-C", str(engine), "rev-parse", "HEAD"], text=True).strip()
    if engine_revision != ENGINE_PIN:
        raise RuntimeError("unsupported engine revision for direct solver wheel readout")
    for relative, expected in READOUT_HEADERS.items():
        if sha((engine/PHYSX_ROOT/relative).read_bytes()) != expected:
            raise RuntimeError(f"changed solver readout header: {relative}")
    previous = json.loads(args.manifest.read_text()) if args.manifest.exists() else None
    output = {}
    original = {}

    def base(path):
        path = str(path)
        data = (root / path).read_bytes()
        # Re-running regenerates patches from the recorded original, never stacks edits.
        if previous and path in previous["integration"]:
            entry = previous["integration"][path]
            if sha(data) != entry["installed_sha256"]:
                raise RuntimeError(f"unrecognized local change: {path}")
            data = entry["original_utf8"].encode()
        else:
            pinned = subprocess.check_output(["git", "-C", str(root), "show", f"{PIN}:{path}"])
            if data != pinned:
                raise RuntimeError(f"integration file already edited: {path}")
        original[path] = data.decode()
        return data.decode()

    def patch(path, before, after):
        output[str(path)] = replace(base(path), before, after).encode()

    for relative, before, after in [
        ("LibCarla/source/carla/client/detail/Client.h", "    std::string GetServerVersion();",
         "    std::string GetServerVersion();\n\n    std::string M7NoDrive(const std::string &request);"),
        ("LibCarla/source/carla/client/detail/Client.cpp", "  void Client::LoadEpisode(", ""),
    ]:
        if not after:
            # Separate exact anchor: no dependence on the LoadEpisode signature.
            before = '  std::string Client::GetServerVersion() {\n    return _pimpl->CallAndWait<std::string>("version");\n  }'
            after = before + '\n\n  std::string Client::M7NoDrive(const std::string &request) {\n    return _pimpl->CallAndWait<std::string>("m7_nodrive", request);\n  }'
        patch(relative, before, after)
    for path, delegate in [
        ("LibCarla/source/carla/client/detail/Simulator.h", "_client"),
        ("LibCarla/source/carla/client/Client.h", "_simulator->"),
    ]:
        before = "    std::string GetServerVersion()"
        s = base(path)
        at = s.index(before)
        qualifier = " const" if delegate.endswith("->") else ""
        call = delegate if delegate.endswith("->") else delegate + "."
        s = s[:at] + f"    std::string M7NoDrive(const std::string &request){qualifier} {{\n      return {call}M7NoDrive(request);\n    }}\n\n" + s[at:]
        output[path] = s.encode()
    path = "PythonAPI/carla/source/libcarla/Client.cpp"
    before = '    .def("get_server_version", CONST_CALL_WITHOUT_GIL(cc::Client, GetServerVersion))'
    patch(path, before, before + '\n    .def("m7_nodrive", CONST_CALL_WITHOUT_GIL_1(cc::Client, M7NoDrive, std::string))')

    path = PLUGIN / "Carla.Build.cs"
    s = base(path)
    s = replace(s, '    PrivatePCHHeaderFile = "Carla.h";',
                '    PrivatePCHHeaderFile = "Carla.h";\n    CppStandard = CppStandardVersion.Cpp17;\n    PrivateDependencyModuleNames.Add("M7Native");\n    PrivateIncludePaths.Add(Path.Combine(ModuleDirectory, "../M7Native/Native"));\n'
                '    PrivateIncludePaths.Add(Path.Combine(EngineDirectory, "Source/ThirdParty/PhysX3/PhysX_3.4/Source/PhysXVehicle/src"));\n'
                '    PrivateIncludePaths.Add(Path.Combine(EngineDirectory, "Source/ThirdParty/PhysX3/PhysX_3.4/Include/vehicle"));')
    output[str(path)] = s.encode()
    path = PLUGIN.parent.parent / "Carla.uplugin"
    s = base(path)
    s = replace(s, '\t"Modules": [', '\t"Modules": [\n\t\t{"Name": "M7Native", "Type": "Runtime", "LoadingPhase": "PreDefault"},')
    output[str(path)] = s.encode()
    path = PLUGIN / "Vehicle/CarlaWheeledVehicle.cpp"
    s = base(path)
    s = replace(s, '#include "Carla.h"', '#include "Carla.h"\n#include "Carla/M7NoDrive/M7NoDriveMovement.h"')
    s = replace(s, '  Super(ObjectInitializer)\n', '  Super(ObjectInitializer.SetDefaultSubobjectClass<UM7NoDriveMovement>(VehicleMovementComponentName))\n')
    s = replace(s, 'void ACarlaWheeledVehicle::FlushVehicleControl()\n{',
                'void ACarlaWheeledVehicle::FlushVehicleControl()\n{\n  auto* M7 = Cast<UM7NoDriveMovement>(GetVehicleMovementComponent());\n  if (M7 && M7->IsZeroProbe()) return;')
    output[str(path)] = s.encode()
    # Explicit dependencies exposed by UE's changed unity partition. The pinned
    # upstream file otherwise relies on a different .cpp's incidental includes.
    path = PLUGIN / "Util/BoundingBoxCalculator.cpp"
    patch(path, '#include "Carla.h"', '#include "Carla.h"\n#include "Carla/Actor/CarlaActor.h"\n#include "Carla/Game/CarlaEpisode.h"')
    path = PLUGIN / "Server/CarlaServer.cpp"
    s = base(path)
    s = replace(s, '#include "Carla.h"', '#include "Carla.h"\n#include "Carla/M7NoDrive/M7NoDrivePort.h"')
    pattern = re.compile(r"(BIND_(?:SYNC|ASYNC)\((\w+)\)\s*<<[^;]*?\n\s*\{)")
    bindings = []
    def guard(match):
        name = match[2]
        deny = name not in READ_ONLY
        bindings.append({"name": name, "blocked_while_bound": deny})
        if name == "apply_batch":
            return match[1] + '\n    if (M7NoDrive::RejectLegacyRpc("apply_batch")) return std::vector<CR>(commands.size(), CR(carla::rpc::ResponseError("M7 exclusive zero-probe owner")));'
        return match[1] + (f'\n    if (M7NoDrive::RejectLegacyRpc("{name}")) {{ RESPOND_ERROR("M7 exclusive zero-probe owner"); }}' if deny else '')
    s = pattern.sub(guard, s)
    found = set(re.findall(r"BIND_(?:SYNC|ASYNC)\((\w+)\)\s*<<", s))
    if {item["name"] for item in bindings} != found or len(bindings) != len(found):
        raise RuntimeError("not every legacy RPC has an explicit guard decision")
    s = replace(s, '  // ~~ Tick ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~',
                '  BIND_SYNC(m7_nodrive) << [this](const std::string& Request) -> R<std::string>\n  {\n    REQUIRE_CARLA_EPISODE();\n    bool Tick = false;\n    auto Reply = M7NoDrive::Request(*Episode, Request, Tick);\n    if (Tick) (void)TickCuesReceived.fetch_add(1, std::memory_order_release);\n    return Reply;\n  };\n\n  // ~~ Tick ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
    s = replace(s, '  Pimpl->Episode = nullptr;\n}', '  M7NoDrive::EndEpisode();\n  Pimpl->Episode = nullptr;\n}')
    s = replace(s, 'void FCarlaServer::Tick()\n{\n  (void)Pimpl->TickCuesReceived.fetch_add(1, std::memory_order_release);',
                'void FCarlaServer::Tick()\n{\n  if (!M7NoDrive::IsLocked())\n    (void)Pimpl->TickCuesReceived.fetch_add(1, std::memory_order_release);')
    output[str(path)] = s.encode()
    path = PLUGIN / "Game/CarlaEngine.cpp"
    s = base(path)
    s = replace(s, '#include "Carla.h"', '#include "Carla.h"\n#include "Carla/M7NoDrive/M7NoDrivePort.h"')
    s = replace(s, '      while (bSynchronousMode && !Server.TickCueReceived());',
                '      while ((bSynchronousMode && !Server.TickCueReceived()) ||\n        (CurrentEpisode && !M7NoDrive::BeforeTick(*CurrentEpisode, GetFrameCounter() + 1, DeltaSeconds)));')
    s = replace(s, '    // send the worldsnapshot',
                '    M7NoDrive::AfterTick(*CurrentEpisode, GetFrameCounter(), DeltaSeconds);\n\n    // send the worldsnapshot')
    output[str(path)] = engine_exit_patch(s, replace).encode()

    output.update(shutdown_patches(base, replace))
    output.update(rpc_shutdown_patches(base, replace))
    output.update(sensor_patches(base, replace))

    integration = {path: {"original_utf8": original[path], "original_sha256": sha(original[path].encode()),
                          "installed_sha256": sha(data)} for path, data in output.items()}
    # Copy only project-owned code. No engine implementation is vendored here.
    for source in sorted(own.glob("M7NoDrive*.cpp")) + sorted(own.glob("M7NoDrive*.h")):
        output[str(PLUGIN / "M7NoDrive" / source.name)] = source.read_bytes()
    output[str(PLUGIN / "M7NoDrive/M7NoDriveModelConstants.h")] = generate()
    output[str(PLUGIN / "M7NoDrive/M7SolverTrace.h")] = (own / "M7SolverTrace.h").read_bytes()
    output[str(PLUGIN / "M7NoDrive/held_steer_sleep.hpp")] = (own / "held_steer_sleep.hpp").read_bytes()
    output[str(PLUGIN / "M7NoDrive/solver_journal.hpp")] = (own / "solver_journal.hpp").read_bytes()
    for name in ("M7Native.Build.cs", "M7Native.cpp"):
        output[str(NATIVE / name)] = (own / name).read_bytes()
    native_hashes = {}
    headers = {p.name: p for p in (project / "interfaces").rglob("*.hpp")}
    pending_headers = []
    for domain, stems in STEMS.items():
        for stem in stems:
            for suffix in ("hpp", "cpp"):
                source = project / "interfaces" / domain / f"{stem}.{suffix}"
                data = source.read_bytes()
                pending_headers.extend(re.findall(r'#include "([^"]+)"', data.decode()))
                native_hashes[str(source.relative_to(project))] = sha(data)
                if suffix == "hpp":
                    output[str(NATIVE / "Native" / source.name)] = data
                else:
                    target = NATIVE / "Native" / f"{stem}.inc"
                    output[str(target)] = data
                    wrapper = f'#pragma GCC visibility push(default)\n#include "Native/{stem}.inc"\n#pragma GCC visibility pop\n'
                    output[str(NATIVE / f"Native_{stem}.cpp")] = wrapper.encode()
    # Transitive project type headers, copied unchanged; never vendor engine code.
    while pending_headers:
        name = pending_headers.pop()
        source = headers[name]
        relative = str(source.relative_to(project))
        if relative in native_hashes:
            continue
        data = source.read_bytes()
        native_hashes[relative] = sha(data)
        output[str(NATIVE / "Native" / name)] = data
        pending_headers.extend(re.findall(r'#include "([^"]+)"', data.decode()))
    output[str(NATIVE / "Native/native_admission.hpp")] = (own / "native_admission.hpp").read_bytes()
    # No writes until every original and every integration anchor has been checked.
    removals = []
    if previous:
        for path, digest in previous["installed"].items():
            if path not in output and path not in previous["integration"]:
                obsolete = root / path
                if obsolete.exists():
                    if sha(obsolete.read_bytes()) != digest:
                        raise RuntimeError(f"unrecognized obsolete generated file: {path}")
                    removals.append(obsolete)
    for path, data in output.items():
        dest = root / path
        if path not in integration and dest.exists() and dest.read_bytes() != data:
            expected = previous["installed"].get(path) if previous else None
            if sha(dest.read_bytes()) != expected:
                raise RuntimeError(f"unrecognized generated file change: {path}")
    for obsolete in removals:
        obsolete.unlink()
    for path, data in output.items():
        dest = root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.read_bytes() != data:
            dest.write_bytes(data)
    manifest = {"carla_commit": PIN, "schema": "m7-nodrive-zero-probe-v1", "integration": integration,
                "solver_readout_engine": {"root": str(engine), "commit": engine_revision, "headers_sha256": READOUT_HEADERS},
                "native_sources_sha256": native_hashes, "legacy_rpc_decisions": bindings,
                "installed": {path: sha(data) for path, data in output.items()}}
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"installed_files": len(output), "legacy_rpc_decisions": len(bindings),
                      "manifest": str(args.manifest), "normal_driving_enabled": False}))


if __name__ == "__main__":
    main()
