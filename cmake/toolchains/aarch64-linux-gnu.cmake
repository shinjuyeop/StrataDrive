# Cross-build Linux userspace artifacts. This does not select a JetPack release,
# provide its sysroot, or demonstrate execution on a Jetson.
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)
set(CMAKE_C_COMPILER aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)
