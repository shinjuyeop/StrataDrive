add_executable(m7_native_admission_test admission_test.cpp)
target_link_libraries(m7_native_admission_test PRIVATE m7_functional_fixture GTest::gtest_main)
target_include_directories(m7_native_admission_test PRIVATE ${PROJECT_SOURCE_DIR}/tools/carla/m7_nodrive)
stratadrive_quality(m7_native_admission_test)
gtest_discover_tests(m7_native_admission_test DISCOVERY_MODE PRE_TEST
    PROPERTIES LABELS "integration.logical;m7.native-admission")
