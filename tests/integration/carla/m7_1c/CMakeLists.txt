add_executable(m7_plant_contract_test contract_test.cpp)
target_link_libraries(m7_plant_contract_test PRIVATE steering_receiver brake_receiver drive_receiver
    steering_actuator brake_actuator drive_actuator drive_controller Threads::Threads GTest::gtest_main)
stratadrive_quality(m7_plant_contract_test)
gtest_discover_tests(m7_plant_contract_test DISCOVERY_MODE PRE_TEST
    PROPERTIES LABELS "integration.logical;m7.contract")
