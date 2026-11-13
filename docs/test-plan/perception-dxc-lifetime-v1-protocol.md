# M10 DXC shutdown lifetime verification

The V3 renderer hang reached libdxcompiler MutexImpl::acquire from llvm_shutdown
and DllShutdown. A standalone shader compile/release plus ordinary application
exit-time mutex allocations reproduces the hang in two original-library negative
controls. GDB observes destruction/free of ManagedStaticMutex before the final
llvm_shutdown acquires it. The initial ctypes prototype had a Linux vtable-index
error and is retained separately, not presented as a DXC failure.

Rebuild the same packaged ShaderConductor/DXC sources with the bundled LLVM10
SDK and libc++. The source copy changes only the function-static mutex to an
intentionally retained allocation and normalizes config.guess CRLF for Linux.
The one small mutex per library load survives exit; other ManagedStatic objects
still receive their original cleanup. This is a bounded intentional retention
for the engine's one library load, not a general repeated-dlopen memory claim.
The original engine library is backed up and exact hashes gate install/restore.

The candidate must compile the standalone shader, preserve its original SPIR-V
bytes, and exit without a timeout in five independently started churn processes.
No forced exit may be called a pass. Then run two dedicated empty Epic/Vulkan
Town03_Opt servers, capped at20 viewport ticks/s solely to bound this smoke test.
Require real SDK readiness, zero sensor actors, a mapped candidate DXC inode,
and normal130 exit within the original30s SIGINT deadline. Capture shutdown
stacks on any delay with the existing bounded tracer. No preload or patching of
live processes is used. All runtime/source hashes are frozen before smoke tests.

No real sensor camera is created, no inference or native-control session runs,
and no new image enters quality evaluation. This verifies the isolated shutdown
fix and engine loading only; it cannot turn V4–V8 thermal/physical failures into
passes. Original CARLA/engine libraries and INI are restored after testing.
