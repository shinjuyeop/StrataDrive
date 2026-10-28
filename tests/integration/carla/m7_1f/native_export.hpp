#pragma once
// M7-only read-only taps on the existing mailbox delivery hooks. Never pop,
// rewrite, acknowledge or re-enqueue traffic on behalf of a native participant.
#include "owner_wire.hpp"
#include "mailbox_delivery.hpp"
#include <array>
#include <optional>

namespace stratadrive::m7_functional {
template<class T> class DeliveredCapture final:public session::MailboxDelivery<T> {
public:
    session::Delivery send(const T&) noexcept override {return {};}
    bool blocked() noexcept override {return false;}
    std::uint64_t now_ns() const noexcept override {return 0;}
    void overflow(const T&) noexcept override {}
    void delivered(const T& value) noexcept override {values[next]=value;next=(next+1)%values.size();}
    template<class Predicate> std::optional<T> find(Predicate predicate) const {
        for(unsigned n=0;n<values.size();++n) {
            const auto& v=values[(next+values.size()-1-n)%values.size()];
            if(v && predicate(*v))return v;
        }
        return {};
    }
private:
    std::array<std::optional<T>,32> values{};unsigned next=0;
};
struct NativeExport {
    std::uint64_t observed=0,enable=0;
    bool normal=false;
    std::uint64_t protection_since=0;
    unsigned protection_selected_mask=0;
    std::array<std::optional<remote::OwnerPacket>,3> actual,commands;
    std::array<std::optional<remote::OwnerPacket>,8> release;
    std::array<std::optional<remote::OwnerPacket>,7> credit;
    std::optional<remote::OwnerPacket> permission;
};
} // namespace stratadrive::m7_functional
