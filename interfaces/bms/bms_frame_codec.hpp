#pragma once

#include "actuator_payload_codec.hpp"

#include <variant>

namespace stratadrive::can {
enum class BmsFrameKind : std::uint16_t {
    PowerRequest = 0x183, PowerStatus = 0x283, PowerLimits = 0x284, BatteryState = 0x285,
    DriveBatteryLimits = 0x193, DrivePermission = 0x194
};
enum class BmsPowerAction : std::uint16_t { KeepOff, Enable, Shutdown };
enum class BmsPowerState : std::uint16_t { Off, Checks, Precharge, HvReady, Shutdown };
enum class BmsDrivePermission : std::uint16_t { Inhibit, AllowNormal };
enum class BmsLimitReason : std::uint8_t {
    Nominal, SocLimited, TemperatureLimited, ElectricalLimited, Disabled, InputsInvalid
};
inline constexpr std::uint64_t kBmsMaxLifetimeNs = 80000000ULL;
struct BmsPowerRequest {
    std::optional<BmsPowerAction> action;
    std::uint64_t expires_at_ns{0};
    std::uint64_t parent_source_time_ns{0};
};
struct BmsPowerLimits {
    std::optional<double> charge_power_w;
    std::optional<double> discharge_power_w;
    BmsLimitReason charge_reason{BmsLimitReason::InputsInvalid};
    BmsLimitReason discharge_reason{BmsLimitReason::InputsInvalid};
    std::uint64_t input_time_ns{0};
};
struct BmsSocSample { double fraction; std::uint64_t source_time_ns; };
struct BmsElectricalSample { double voltage_v; double current_a; std::uint64_t source_time_ns; };
struct BmsTemperatureSample { double celsius; std::uint64_t source_time_ns; };
struct BmsBatteryState {
    std::optional<BmsSocSample> soc;
    std::optional<BmsElectricalSample> electrical;
    std::optional<BmsTemperatureSample> temperature;
};
struct BmsPowerStatus {
    std::optional<BmsPowerState> state;
    std::optional<bool> positive_contactor_closed;
    std::optional<bool> negative_contactor_closed;
    std::optional<bool> precharge_contactor_closed;
    std::uint8_t condition_bits{0};
    std::uint8_t condition_validity{0};
    std::optional<double> hv_bus_voltage_v;
    std::uint64_t input_time_ns{0};
    std::uint64_t accepted_request_source_time_ns{0};
    std::uint32_t input_sequence{0};
};
struct BmsDriveGrant {
    std::optional<BmsDrivePermission> permission;
    std::uint32_t power_status_sequence{0};
    std::uint64_t power_status_source_time_ns{0};
    std::uint64_t input_time_ns{0};
    std::uint64_t expires_at_ns{0};
};
using BmsContent = std::variant<BmsPowerRequest, BmsPowerLimits, BmsBatteryState, BmsPowerStatus, BmsDriveGrant>;
struct BmsMessage : ActuatorMetadata {
    BmsFrameKind kind{BmsFrameKind::PowerRequest};
    BmsContent content{BmsPowerRequest{}};
};
struct BmsFrame {
    std::uint32_t can_id{0};
    bool is_fd{true};
    std::uint8_t fd_flags{0};
    std::uint8_t payload_length{48};
    std::array<std::uint8_t, 64> payload{};
};
struct BmsTxState { const BmsFrameKind kind; e2e::P05ProtectState protection{}; };
struct BmsRxState { const BmsFrameKind kind; e2e::P05CheckState check{}; };
std::optional<e2e::P05Config> bms_e2e_config(BmsFrameKind kind);
std::optional<std::uint16_t> bms_frame_crc(const BmsFrame& frame);
std::optional<BmsFrame> encode_bms_frame(const BmsMessage& message, BmsTxState& state);
std::optional<BmsMessage> decode_bms_frame(const BmsFrame& frame);
e2e::P05Return check_bms_e2e(const BmsFrame* frame, BmsRxState& state);
// Preserve BMS logical sample; only the downstream protection state/ID changes.
std::optional<BmsFrame> forward_bms_limits(const BmsMessage& source, BmsTxState& downstream);
}  // namespace stratadrive::can
