# M10 DXC shutdown lifetime fix

The original shader compiler can acquire an already-destroyed mutex during
process shutdown. The isolated fix passes the declared lifecycle checks, including
two real empty CARLA server exits. M10 normal endurance remains FAIL/OPEN.

## Cause and change

The original V3 hang reached `MutexImpl::acquire` from `llvm_shutdown` and
`DllShutdown`. The [GDB diagnosis](../m10_remediation_v1/shutdown-diagnosis/README.md)
observes destruction of the function-static ManagedStatic mutex before the later
DSO shutdown function acquires it. The destructor destroys and frees the mutex.

[ManagedStatic.patch](ManagedStatic.patch) retains that one small lock until
process teardown. Other ManagedStatic objects still receive their usual cleanup.
This intentionally retains one mutex per library load; the engine loads it once.
Repeated arbitrary dlopen/dlclose cycles are not claimed to be leak-free.
The isolated source copy also normalizes config.guess CRLF for Linux. The build
manifest verifies that these are its only two source changes across 11,456 files.

## Results

The [prospective protocol](../../perception-dxc-lifetime-v1-protocol.md), source
archive and external hashes were frozen before the engine smoke test.

| Check | Original library | Candidate |
| --- | --- | --- |
| Standalone shader compile/release, plain exit | exit 0 | exit 0 |
| Ordinary exit-handler allocation churn | 2 of 2 time out after 3s | 5 of 5 exit 0 |
| Shader bytes from all those processes | same 336-byte fixture | byte-identical |
| Empty Epic/Vulkan Town03_Opt server, attempt 1 | not rerun | exit 130 after 2.569s |
| Empty Epic/Vulkan Town03_Opt server, attempt 2 | not rerun | exit 130 after 2.219s |

The C++ probe registers an ordinary atexit handler before loading DXC. That
handler allocates and locks valid application-owned mutexes, exposing the original
library's use of freed memory. No debugger memory injection, writes through freed
pointers or forced successful exit are used. Original negative controls are killed
only after their timeout and are explicitly recorded as timeouts.

`original-lifecycle.json`, `candidate-lifecycle.json` and their SPIR-V files retain
the initial verification. `lifecycle-repeat-02/result.json` reproduces all nine
process outcomes with the checked-in Python runner and records exact commands.
`lifecycle-repeat-01` is retained as a harness setup failure: unversioned clang++
was absent, no compiler or probe ran. The runner now requires an explicit compiler.
This does not replace or discard a failed live CARLA/control case.

`smoke-01/result.json` and its logs record real SDK readiness, zero sensor actors,
the candidate library mapped in each actual process and normal SIGINT exits within
the unchanged 30s deadline. There was no camera, inference or native-control
session. A single byte-identical fixture does not establish all shader equivalence.
The empty-server checks do not reproduce the original loaded endurance workload.

## Artifact and reproduction

- Original DXC SHA256: `c10161c15629433d872ff70bb715a63ebb6046199a2b8405eb6186e7f07b2f46`.
- Candidate DXC SHA256: `3f3bf1e87a48577daa4dda8a9a1d0695ab1a784d8faed010312a932dc52fd83e`.
- Fixture SPIR-V SHA256: `4d2d7918c0eba8fa1c78da4eae98413f9db74fc4d292d0fc7fcf92f2321f9af2`.

`libdxcompiler.so` is the tested candidate, built with the UE bundled clang 10
SDK/sysroot/libc++. `manifest.json`, the host toolchain, configure and build logs
identify the build. `build-reproduction.tar.gz` preserves the actual CMake cache,
Ninja descriptions and the two tablegen executables reused from the same source
tree. Its separate inventory hashes every member. Licenses are retained alongside
the artifact. No second byte-identical full compiler rebuild is claimed.

The isolated build/install/restore tool is
`tools/carla/m7_nodrive/build_dxc_lifetime.py`. A fresh build requires the packaged
UE source/SDK, CMake 3 and Ninja. Its default same-host configuration builds its own
tablegen tools; the recorded artifact used the archived prebuilt tools. Install
and restore require stopped UE processes and verify both the current and target
library hashes before atomic replacement.

To reproduce the standalone check from the repository root with this workspace:

```sh
python3 tests/integration/perception/run_dxc_lifecycle_v1.py \
  --headers build/m10-dxc-lifetime-v1/source/External/DirectXShaderCompiler/include \
  --original build/m10-dxc-lifetime-v1/original-libdxcompiler.so \
  --candidate docs/test-plan/evidence/m10_dxc_lifetime_v1/libdxcompiler.so \
  --compiler /usr/bin/clang++-14 --output build/dxc-lifecycle-new
```

The output directory must be new. `check-evidence.py --work <new-directory>`
independently extracts the frozen source and reproduces 56 boundary tests; those
unit tests do not start CARLA or replace the lifecycle checks. The frozen engine
runner is `tests/integration/perception/run_dxc_shutdown_v1.py`; a new live run
requires a fresh manifest after deliberately installing its candidate.

[restoration.json](restoration.json) confirms that original CARLA, DXC, engine,
RenderCore, executable and INI identities were rechecked after testing, with no UE
process left. The candidate is retained for a declared subsequent test rather than
silently changing the shared runtime. No new camera frame or quality-evaluation
sample was produced; cumulative future exclusions remain 9774.
