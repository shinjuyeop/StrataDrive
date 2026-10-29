# Generate an M7-only owner from the unchanged shared transport implementation.
# Drive sensor ingress precedes IO/10ms control. An explicit M7-only HV
# dependency policy uses the generated controller; period/session/CAN stay original.
include(wall_drive.cmake)
set(base "${PROJECT_SOURCE_DIR}/simulation/runtime/async_leaf_owner")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${base}.hpp" "${base}.cpp")
file(READ "${base}.hpp" header)
string(FIND "${header}" "class AsyncLeafOwner final" begin)
if(begin LESS 0)
  message(FATAL_ERROR "M7 wall owner header anchor missing")
endif()
string(SUBSTRING "${header}" ${begin} -1 header)
string(REPLACE "AsyncLeafOwner" "WallLeafOwner" header "${header}")
wall_replace(header "BmsGateChannel& bms_gate);" "BmsGateChannel& bms_gate,std::uint64_t hv_dependency_ns=30000000);")
wall_replace(header "make_actor(transport::Leaf leaf);" "make_actor(transport::Leaf leaf,std::uint64_t hv_dependency_ns);")
string(REPLACE "vecu::DriveController" "vecu::WallDriveController" header "${header}")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/wall_leaf_owner.hpp" "#pragma once\n#include \"async_leaf_owner.hpp\"\n#include \"wall_drive_controller.hpp\"\nnamespace stratadrive::simulation {\n${header}")
file(READ "${base}.cpp" source)
foreach(anchor IN ITEMS
    "SessionResetEvidence reset_evidence(const OwnerSensors& s) { return {s.drive.wheel_speed,s.torque,s.power}; }"
    "    const auto ingress_now=now_ns();"
    "    const auto s=sensors_.read(); const auto now=now_ns();")
  string(FIND "${source}" "${anchor}" found)
  if(found LESS 0)
    message(FATAL_ERROR "M7 wall owner source anchor missing: ${anchor}")
  endif()
endforeach()
string(REPLACE "SessionResetEvidence reset_evidence(const OwnerSensors& s) { return {s.drive.wheel_speed,s.torque,s.power}; }" "" source "${source}")
string(REPLACE "    const auto ingress_now=now_ns();"
 "    const auto s=sensors_.read();\n    const auto ingress_now=now_ns();\n    if(started_ && leaf_==transport::Leaf::Drive && s)\n        std::get<vecu::DriveController>(actor_).observe_local(s->drive,ingress_now);" source "${source}")
string(REPLACE "    const auto s=sensors_.read(); const auto now=now_ns();" "    const auto now=now_ns();" source "${source}")
string(REPLACE "AsyncLeafOwner" "WallLeafOwner" source "${source}")
wall_replace(source "make_actor(transport::Leaf leaf)" "make_actor(transport::Leaf leaf,std::uint64_t hv_dependency_ns)")
wall_replace(source "BmsGateChannel& bms_gate)" "BmsGateChannel& bms_gate,std::uint64_t hv_dependency_ns)")
wall_replace(source "make_actor(leaf)" "make_actor(leaf,hv_dependency_ns)")
wall_replace(source "auto c=vecu::DriveControllerConfig{};" "auto c=vecu::DriveControllerConfig{}; c.hv_dependency_age_ns=hv_dependency_ns;")
string(REPLACE "vecu::DriveController" "vecu::WallDriveController" source "${source}")
string(REPLACE "#include \"async_leaf_owner.hpp\"" "#include \"wall_leaf_owner.hpp\"" source "${source}")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/wall_leaf_owner.cpp" "${source}")
