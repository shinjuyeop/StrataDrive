#pragma once

#include "bms_controller.hpp"
#include "bms_receiver.hpp"

#include <array>
#include <optional>

namespace stratadrive::simulation::multirate_fixture {
// Trusted issuer history, transported separately from CAN. A wire frame cannot
// create a parent. Four recent exact envelopes suffice for this finite fixture;
// an older/changed frame has no matching context and must be rejected normally.
struct TrustedFrame {
    can::BmsFrame frame;
    std::optional<can::BmsParentContext> parent;
};
class TrustedHistory {
public:
    void issue(const can::BmsFrame& frame, std::optional<can::BmsParentContext> parent) {
        entries_[next_]=TrustedFrame{frame,parent}; next_=(next_+1)%entries_.size();
    }
    std::optional<TrustedFrame> find(const can::BmsFrame& frame) const {
        for(const auto& entry:entries_) {
            if(entry && entry->frame.can_id==frame.can_id && entry->frame.is_fd==frame.is_fd &&
                entry->frame.fd_flags==frame.fd_flags && entry->frame.payload_length==frame.payload_length &&
                entry->frame.payload==frame.payload) return entry;
        }
        return std::nullopt;
    }
private:
    std::array<std::optional<TrustedFrame>,4> entries_{};
    std::size_t next_{0};
};
inline vecu::BmsControllerConfig bms_config() {
    vecu::BmsControllerConfig c;
    c.charge_current_a=80; c.discharge_current_a=200; c.max_charge_power_w=30000; c.max_discharge_power_w=80000;
    c.charge_soc={.95,.8}; c.discharge_soc={.05,.1}; c.charge_cell_v={4.2,4.1}; c.discharge_cell_v={3,3.3};
    c.charge_temperature={0,10,40,45}; c.discharge_temperature={-20,0,45,55};
    c.cell_v={2.8,2.95,4.15,4.25}; c.pack_v={280,295,415,425}; c.temperature_c={-30,-15,50,60};
    c.current_a={-100,-80,200,250}; c.series_cells=100; c.pack_extrema_tolerance_v=2;
    c.period_ns=1000000; // call guard only; outer runnable releases every 20 ms
    return c;
}
} // namespace stratadrive::simulation::multirate_fixture
