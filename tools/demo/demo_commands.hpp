#pragma once

#include "bms_value_codec.hpp"
#include <iosfwd>
#include <string>

namespace stratadrive::demo {
struct M4DemoOptions { std::string clock,scenario,store,output; };
void demo_m4_async(const M4DemoOptions& options);
void demo_angle(const std::string& input);
void demo_frame(const std::string& kind, const std::string& input);
void demo_e2e();
void demo_receiver();
void demo_steering_model(const std::string& scenario);
void demo_brake_pressure(const std::string& input);
void demo_brake_frame(const std::string& kind, const std::string& input);
void demo_brake_receiver();
void demo_brake_model(const std::string& scenario);
void demo_drive_frame(const std::string& kind, const std::string& input);
void demo_drive_feedback();
void demo_drive_gated(const std::string& scenario);
void demo_drive_energy(const std::string& scenario);
void demo_drive_model();
void demo_bms_value(can::BmsValueKind kind, double value);
void demo_bms_frame(const std::string& kind, const std::string& variant);
void demo_bms_receiver();
void demo_battery_model();
void demo_bms_control();
void demo_power_model(const std::string& scenario);
void demo_ev_power(const std::string& scenario);
can::BmsValueKind parse_bms_value_kind(const std::string& field);
void usage(std::ostream& output);
} // namespace stratadrive::demo
