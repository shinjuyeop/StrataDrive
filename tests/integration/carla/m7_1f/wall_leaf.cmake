# Generate an M7-only owner from the unchanged shared transport implementation.
# The only behavior change is Drive sensor ingress before IO/10ms control. The
# controller, period grid, session, watchdog and CAN/P05 source code stay original.
set(base "${PROJECT_SOURCE_DIR}/simulation/runtime/async_leaf_owner")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${base}.hpp" "${base}.cpp")
file(READ "${base}.hpp" header)
string(FIND "${header}" "class AsyncLeafOwner final" begin)
if(begin LESS 0)
  message(FATAL_ERROR "M7 wall owner header anchor missing")
endif()
string(SUBSTRING "${header}" ${begin} -1 header)
string(REPLACE "AsyncLeafOwner" "WallLeafOwner" header "${header}")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/wall_leaf_owner.hpp" "#pragma once\n#include \"async_leaf_owner.hpp\"\nnamespace stratadrive::simulation {\n${header}")
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
string(REPLACE "#include \"async_leaf_owner.hpp\"" "#include \"wall_leaf_owner.hpp\"" source "${source}")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/wall_leaf_owner.cpp" "${source}")
