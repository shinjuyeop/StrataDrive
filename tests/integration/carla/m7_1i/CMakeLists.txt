add_executable(m7_effort_contract_test effort_test.cpp)
target_include_directories(m7_effort_contract_test PRIVATE ../m7_1c)
target_link_libraries(m7_effort_contract_test PRIVATE steering_receiver brake_receiver
    drive_receiver Threads::Threads GTest::gtest_main)
stratadrive_quality(m7_effort_contract_test)
gtest_discover_tests(m7_effort_contract_test DISCOVERY_MODE PRE_TEST
    PROPERTIES LABELS "integration.logical;m7.contract;m7.effort")
