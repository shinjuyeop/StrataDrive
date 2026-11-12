find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
execute_process(COMMAND ${Python3_EXECUTABLE} -c "import numpy, cv2"
    RESULT_VARIABLE perception_python_dependencies OUTPUT_QUIET ERROR_QUIET)
if(NOT perception_python_dependencies EQUAL 0)
    message(FATAL_ERROR "M10 tests require numpy/OpenCV. Set Python3_EXECUTABLE to the environment from physical_ai/requirements-host.txt")
endif()
add_executable(perception_replay perception_replay.cpp)
target_link_libraries(perception_replay PRIVATE perception_receiver)
stratadrive_quality(perception_replay)
add_executable(perception_2k_replay perception_2k_replay.cpp)
target_link_libraries(perception_2k_replay PRIVATE perception_2k_receiver)
stratadrive_quality(perception_2k_replay)
add_test(NAME perception_2k_boundary_replay
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/check_boundary_2k_v1.py $<TARGET_FILE:perception_2k_replay>)
set_tests_properties(perception_2k_boundary_replay PROPERTIES WORKING_DIRECTORY ${PROJECT_SOURCE_DIR}
    LABELS "integration.logical" TIMEOUT 30)
add_test(NAME perception_python
    COMMAND ${Python3_EXECUTABLE} -m unittest discover -s tests/integration/perception -p test_*.py)
set_tests_properties(perception_python PROPERTIES WORKING_DIRECTORY ${PROJECT_SOURCE_DIR}
    LABELS "integration.logical" TIMEOUT 90)
add_test(NAME perception_boundary_replay
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/check_boundary.py $<TARGET_FILE:perception_replay>)
set_tests_properties(perception_boundary_replay PROPERTIES WORKING_DIRECTORY ${PROJECT_SOURCE_DIR}
    LABELS "integration.logical" TIMEOUT 30)
