#pragma once

#include "bms_controller.hpp"
#include "bms_frame_codec.hpp"
#include <string>

namespace stratadrive::demo {
can::BmsMessage bms_fixture(can::BmsFrameKind kind, const std::string& variant);
vecu::BmsControllerConfig bms_fixture_config();
} // namespace stratadrive::demo
