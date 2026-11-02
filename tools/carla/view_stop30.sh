#!/usr/bin/env bash
# Prepared Linux host: live chase camera for the fixed M8 STOP30 functional run.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
carla_tools="${STRATADRIVE_TOOLS:-/d/shin/stratadrive-tools}"
sdk_python="$carla_tools/m7-source/m7-nodrive-venv/bin/python"
native="$repo_root/build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow"
if [[ ! -x "$native" ]]; then
  echo 'Build m7_wheel_shadow in build/m7-functional before starting the viewer.' >&2
  exit 1
fi
# Fail before engine startup if the desktop/Tk connection is unavailable.
"$sdk_python" -c 'import tkinter as tk; root=tk.Tk(); root.withdraw(); root.update(); root.destroy()'
mkdir -p build
run_dir="$(mktemp -d "$repo_root/build/carla-live-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
echo "Live CARLA run: $run_dir"
echo 'The chase-camera window opens after map loading. Ctrl+C stops the run.'
exec python3 tests/integration/carla/m7_1o_run.py \
  --engine "$carla_tools/UnrealEngine_4.26" \
  --source "$carla_tools/m7-source/carla-0.9.16" \
  --python "$sdk_python" \
  --fixture "$carla_tools/m7-source/m7-1m-fixture" \
  --native-actual "$native" \
  --runtime "$run_dir/runtime" --output "$run_dir/run" \
  --vehicle-substeps 320 --solver-work --held-steer-sleep --simulation-continuous \
  --route-profile tests/integration/carla/scenarios/m8_stop30_v1.json \
  --route-startup-seconds 600 --ticks 6000 --cameras --live-view "$@"
