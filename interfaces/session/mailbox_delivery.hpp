#pragma once
#include <cstdint>

namespace stratadrive::session {
struct Delivery { bool discard{false}; std::uint64_t available_ns{0}; };
// Optional transport adapter, installed before either owner starts. Methods
// send()/overflow() have one producer; delivered()/blocked() one consumer.
// An adapter may lose a packet without making its enqueue result an ACK.
template<class T> class MailboxDelivery {
public:
    virtual ~MailboxDelivery() = default;
    virtual Delivery send(const T&) noexcept = 0;
    virtual bool blocked() noexcept = 0;
    virtual std::uint64_t now_ns() const noexcept = 0;
    virtual void delivered(const T&) noexcept = 0;
    virtual void overflow(const T&) noexcept = 0;
};
} // namespace stratadrive::session
