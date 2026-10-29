# Core unit/logical/runtime categories retain their original test names.
include(GoogleTest)
include(${CMAKE_CURRENT_LIST_DIR}/TestCategories.cmake)
function(stratadrive_unit_test target)
    cmake_parse_arguments(TEST "" "" "SOURCES;LIBRARIES" ${ARGN})
    if(TEST_UNPARSED_ARGUMENTS OR NOT TEST_SOURCES OR NOT TEST_LIBRARIES)
        message(FATAL_ERROR "Invalid test declaration: ${target}")
    endif()
    add_executable(${target} ${TEST_SOURCES})
    target_link_libraries(${target} PRIVATE ${TEST_LIBRARIES} GTest::gtest_main)
    stratadrive_quality(${target})
    stratadrive_discover_tests(${target})
endfunction()

# 현재 Host에 설치된 버전 사용. 자동 다운로드/설치하지 않는다.
find_package(GTest 1.11.0 EXACT CONFIG REQUIRED)
add_executable(steering_angle_codec_test tests/unit/steering_angle_codec_test.cpp)
target_link_libraries(steering_angle_codec_test PRIVATE steering_angle_codec GTest::gtest_main)
stratadrive_quality(steering_angle_codec_test)
stratadrive_unit_test(m6_physical_response_test
    SOURCES tests/unit/m6_physical_response_test.cpp
    LIBRARIES m4_async_runtime)
stratadrive_unit_test(vehicle_energy_test
    SOURCES tests/unit/vehicle_energy_test.cpp
    LIBRARIES vehicle_ev_model)
stratadrive_unit_test(simple_vehicle_test
    SOURCES tests/unit/simple_vehicle_test.cpp
    LIBRARIES simple_vehicle torque_response brake_pressure_response)
stratadrive_unit_test(remote_leaf_test
    SOURCES tests/unit/remote_leaf_test.cpp tests/unit/remote_zone_integration_test.cpp
    LIBRARIES remote_leaf_endpoint)
stratadrive_unit_test(remote_contract_test
    SOURCES tests/unit/remote_contract_test.cpp
    LIBRARIES run_lease_issuer command_admission)
add_library(owner_contract_boundary OBJECT tests/unit/owner_contract_boundary.cpp)
target_link_libraries(owner_contract_boundary PRIVATE owner_messages session_reset)
stratadrive_quality(owner_contract_boundary)
stratadrive_unit_test(normal_drive_readiness_test
    SOURCES tests/unit/normal_drive_readiness_test.cpp
    LIBRARIES normal_drive_readiness)
stratadrive_unit_test(vehicle_management_test
    SOURCES tests/unit/vehicle_management_test.cpp
    LIBRARIES vehicle_management power_controller power_model)
stratadrive_unit_test(normal_stop_test
    SOURCES tests/unit/normal_stop_test.cpp
    LIBRARIES normal_stop)
stratadrive_unit_test(control_allocation_test
    SOURCES tests/unit/control_allocation_test.cpp
    LIBRARIES control_allocation command_admission torque_response brake_pressure_response steering_receiver brake_receiver drive_receiver)
stratadrive_unit_test(command_admission_test
    SOURCES tests/unit/command_admission_test.cpp
    LIBRARIES command_admission)
stratadrive_unit_test(command_gateway_test
    SOURCES tests/unit/command_gateway_test.cpp
    LIBRARIES command_gateway zone_leaf_protection front_startup_control steering_response brake_pressure_response torque_response)
stratadrive_unit_test(rear_power_gateway_test
    SOURCES tests/unit/rear_power_gateway_test.cpp
    LIBRARIES rear_power_gateway rear_power_control front_startup_control normal_stop_control vehicle_session_init zone_feedback_monitor power_model torque_response steering_response brake_pressure_response)
stratadrive_unit_test(vehicle_coordinator_test
    SOURCES tests/unit/vehicle_coordinator_test.cpp
    LIBRARIES vehicle_coordinator)
stratadrive_unit_test(async_owner_test
    SOURCES tests/unit/async_owner_test.cpp
    LIBRARIES async_coordinator_port async_zone_owner)
stratadrive_unit_test(m4_async_runtime_test
    SOURCES tests/unit/m4_async_runtime_test.cpp
    LIBRARIES m4_async_runtime)
stratadrive_unit_test(m4_fault_test
    SOURCES tests/unit/m4_fault_test.cpp
    LIBRARIES m4_async_runtime)
stratadrive_unit_test(zone_feedback_monitor_test
    SOURCES tests/unit/zone_feedback_monitor_test.cpp
    LIBRARIES zone_feedback_monitor)
add_executable(periodic_task_test tests/unit/periodic_task_test.cpp)
find_package(Threads REQUIRED)
stratadrive_unit_test(session_coordinator_test
    SOURCES tests/unit/session_coordinator_test.cpp
    LIBRARIES vehicle_session_init Threads::Threads)
target_link_libraries(periodic_task_test PRIVATE periodic_task Threads::Threads GTest::gtest_main)
stratadrive_quality(periodic_task_test)
stratadrive_discover_tests(periodic_task_test)
add_executable(runtime_trust_test tests/unit/runtime_trust_test.cpp)
target_include_directories(runtime_trust_test PRIVATE simulation/runtime)
target_link_libraries(runtime_trust_test PRIVATE bms_controller bms_receiver GTest::gtest_main)
if(TARGET multirate_runtime)
    target_link_libraries(runtime_trust_test PRIVATE multirate_runtime)
endif()
stratadrive_quality(runtime_trust_test)
stratadrive_discover_tests(runtime_trust_test)
# Core boundary test intentionally has no simulation include/link dependency.
stratadrive_unit_test(ecu_boundary_test
    SOURCES tests/unit/ecu_boundary_test.cpp
    LIBRARIES steering_actuator brake_actuator drive_actuator drive_controller)
stratadrive_unit_test(steering_response_test
    SOURCES tests/unit/steering_response_test.cpp
    LIBRARIES steering_response)
stratadrive_unit_test(steering_response_monitor_test
    SOURCES tests/unit/steering_response_monitor_test.cpp
    LIBRARIES steering_response_monitor)
stratadrive_unit_test(steering_actuator_test
    SOURCES tests/unit/steering_actuator_test.cpp
    LIBRARIES steering_sil)
stratadrive_unit_test(brake_pressure_response_test
    SOURCES tests/unit/brake_pressure_response_test.cpp
    LIBRARIES brake_pressure_response)
stratadrive_unit_test(brake_response_monitor_test
    SOURCES tests/unit/brake_response_monitor_test.cpp
    LIBRARIES brake_response_monitor)
stratadrive_unit_test(brake_actuator_test
    SOURCES tests/unit/brake_actuator_test.cpp
    LIBRARIES brake_sil)
stratadrive_unit_test(drive_actuator_test
    SOURCES tests/unit/drive_actuator_test.cpp
    LIBRARIES drive_sil)
stratadrive_unit_test(drive_controller_test
    SOURCES tests/unit/drive_controller_test.cpp
    LIBRARIES drive_sil)
stratadrive_unit_test(drive_energy_model_test
    SOURCES tests/unit/drive_energy_model_test.cpp
    LIBRARIES drive_energy_model drive_sil bms_controller)
stratadrive_unit_test(ev_power_model_test
    SOURCES tests/unit/ev_power_model_test.cpp
    LIBRARIES ev_power_model)
stratadrive_unit_test(battery_model_test
    SOURCES tests/unit/battery_model_test.cpp
    LIBRARIES battery_model)
stratadrive_unit_test(bms_controller_test
    SOURCES tests/unit/bms_controller_test.cpp
    LIBRARIES bms_controller battery_model bms_receiver)
stratadrive_unit_test(power_lifecycle_test
    SOURCES tests/unit/power_lifecycle_test.cpp
    LIBRARIES power_model power_controller bms_controller)
stratadrive_discover_tests(steering_angle_codec_test)
stratadrive_unit_test(steering_frame_codec_test
    SOURCES tests/unit/steering_frame_codec_test.cpp
    LIBRARIES steering_frame_codec)
stratadrive_unit_test(e2e_profile5_test
    SOURCES tests/unit/e2e_profile5_test.cpp
    LIBRARIES e2e_profile5)
stratadrive_unit_test(steering_receiver_test
    SOURCES tests/unit/steering_receiver_test.cpp
    LIBRARIES steering_receiver)
stratadrive_unit_test(brake_codec_test
    SOURCES tests/unit/brake_codec_test.cpp
    LIBRARIES brake_codec steering_frame_codec)
stratadrive_unit_test(brake_receiver_test
    SOURCES tests/unit/brake_receiver_test.cpp
    LIBRARIES brake_receiver)
stratadrive_unit_test(drive_test
    SOURCES tests/unit/drive_test.cpp
    LIBRARIES drive_receiver)
stratadrive_unit_test(bms_test
    SOURCES tests/unit/bms_test.cpp
    LIBRARIES bms_receiver)
if(TARGET actuator_socketcan)
    stratadrive_unit_test(session_test
        SOURCES tests/unit/session_test.cpp
        LIBRARIES epoch_store session_coordinator steering_receiver brake_receiver drive_receiver bms_receiver)
    stratadrive_unit_test(actuator_socketcan_test
        SOURCES tests/unit/actuator_socketcan_test.cpp
        LIBRARIES actuator_socketcan steering_receiver)
    # Requires two caller-created isolated vCAN buses; not a regular unit test.
    add_executable(zone_gateway_vcan_test tests/integration/can/zone_gateway_test.cpp)
    target_link_libraries(zone_gateway_vcan_test PRIVATE zone_socketcan_gateway rear_power_control front_startup_control steering_receiver brake_receiver drive_receiver GTest::gtest_main)
    stratadrive_quality(zone_gateway_vcan_test)
endif()
