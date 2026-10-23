set(STRATADRIVE_M7_PHYSX_SOURCE "" CACHE PATH "Pinned public PhysX-3.4 checkout (SDK probe only)")
set(px "${STRATADRIVE_M7_PHYSX_SOURCE}/PhysX_3.4")
set(shared "${STRATADRIVE_M7_PHYSX_SOURCE}/PxShared")
set(common "${px}/Snippets/SnippetVehicleCommon")
set(sdk_libraries
    "${px}/Lib/linux64/libPhysX3VehicleCHECKED.a"
    "${px}/Lib/linux64/libPhysX3ExtensionsCHECKED.a"
    "${px}/Bin/linux64/libPhysX3CHECKED_x64.so"
    "${px}/Bin/linux64/libPhysX3CookingCHECKED_x64.so"
    "${px}/Bin/linux64/libPhysX3CommonCHECKED_x64.so"
    "${shared}/bin/linux64/libPxPvdSDKCHECKED_x64.so"
    "${shared}/bin/linux64/libPxFoundationCHECKED_x64.so")
foreach(lib IN LISTS sdk_libraries)
    if(NOT EXISTS "${lib}")
        message(FATAL_ERROR "Build pinned public SDK with m7_1j/build_physx.py first: ${lib}")
    endif()
endforeach()

# Compile upstream fixture helpers separately; do not copy or alter their physics.
add_library(m7_physx_fixture STATIC
    "${common}/SnippetVehicleCreate.cpp" "${common}/SnippetVehicleNoDriveCreate.cpp"
    "${common}/SnippetVehicleSceneQuery.cpp" "${common}/SnippetVehicleFilterShader.cpp"
    "${common}/SnippetVehicleTireFriction.cpp")
target_include_directories(m7_physx_fixture SYSTEM PUBLIC "${px}/Include" "${shared}/include" "${common}")
target_compile_definitions(m7_physx_fixture PUBLIC NDEBUG PX_CHECKED=1)
target_link_libraries(m7_physx_fixture PUBLIC ${sdk_libraries} Threads::Threads ${CMAKE_DL_LIBS})

add_executable(m7_nodrive_test nodrive_test.cpp)
target_include_directories(m7_nodrive_test PRIVATE ../m7_1c ../m7_1i ../m7_1h)
target_link_libraries(m7_nodrive_test PRIVATE m7_physx_fixture steering_receiver brake_receiver
    drive_receiver GTest::gtest_main)
stratadrive_quality(m7_nodrive_test)
# Upstream CHECKED SDK is built with -fno-rtti. Its classes have no typeinfo
# symbols for UBSan's vptr check; retain ASan and every other UBSan check here.
# SDK binaries and upstream fixture helpers themselves are not instrumented.
if(STRATADRIVE_SANITIZERS AND CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(m7_nodrive_test PRIVATE -fno-sanitize=vptr)
endif()
gtest_discover_tests(m7_nodrive_test DISCOVERY_MODE PRE_TEST
    PROPERTIES LABELS "integration.logical;m7.nodrive;standalone.physx"
    ENVIRONMENT "M7_NODRIVE_SUBSTEPS=20")
