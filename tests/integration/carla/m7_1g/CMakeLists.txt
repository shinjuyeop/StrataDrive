add_executable(m7_wheel_shadow wheel_main.cpp)
target_link_libraries(m7_wheel_shadow PRIVATE m7_functional_fixture)
target_include_directories(m7_wheel_shadow PRIVATE ${PROJECT_SOURCE_DIR}/tools/carla/m7_nodrive)
stratadrive_quality(m7_wheel_shadow)
add_executable(m7_wheel_test wheel_test.cpp terminal_response_test.cpp)
target_link_libraries(m7_wheel_test PRIVATE m7_functional_fixture GTest::gtest_main)
stratadrive_quality(m7_wheel_test)
gtest_discover_tests(m7_wheel_test DISCOVERY_MODE PRE_TEST
    PROPERTIES LABELS "integration.logical;m7.functional;m7.wheel")
