#pragma once
#include "continuity_review.hpp"
#include <memory>

namespace stratadrive::diagnostics {
// Local Linux service protocol, separate from Event-only diagnostic delivery.
// Provision a fresh service producer and nonzero boot capability per lifetime.
enum class ServiceOperation : std::uint8_t { Review=1, Clear=2 };
struct ServiceRequest {
    std::array<std::uint8_t,16> capability{};
    std::uint64_t number{0}; Session session{}; EventId incident{};
    std::uint64_t revision{0}; ServiceOperation operation{ServiceOperation::Review};
    ContinuityDisposition disposition{ContinuityDisposition::None};
};
struct ServicePermit {
    std::uint32_t uid{0};std::int32_t pid{0};
    std::array<std::uint8_t,16> capability{};
    ControlContext actor{};Session session{};EventId incident{};
};
enum class ServiceStatus : std::uint8_t {
    Accepted, Unauthorized, Malformed, Scope, Revision, Freeze, Inspection,
    Physical, Storage, Capacity, Conflict, NotReady, NoData, Transport
};
struct ServiceReply {
    std::uint64_t number{0},watermark{0},revision{0};
    ServiceStatus status{ServiceStatus::Malformed};std::uint8_t stage{0};
    ReviewBlock blocked{ReviewBlock::None};
};
std::vector<std::uint8_t> encode_service_request(const ServiceRequest&);
ServiceRequest decode_service_request(const std::vector<std::uint8_t>&);
std::vector<std::uint8_t> encode_service_reply(const ServiceReply&);
ServiceReply decode_service_reply(const std::vector<std::uint8_t>&);

// Trusted adapter: acquire stops and drains every producer/transport writer;
// this guard owns the same cut until destruction, including durable commits.
// sample must query current validated Actuals, preserving acquisition times.
// Normal dispatch remains inhibited independently of this diagnostic lifetime.
class FrozenContinuity {
public:
    virtual ~FrozenContinuity()=default;
    virtual const Event& global() const noexcept=0;
    virtual const std::vector<StreamState>& streams() const noexcept=0;
    virtual ServiceEvidence sample()=0;
};
class ContinuityCapture {
public:
    virtual ~ContinuityCapture()=default;
    virtual std::unique_ptr<FrozenContinuity> acquire()=0;
};
// One non-RT owner, one fixed incident/session/authorized kernel peer. No
// INIT, actuator, repair, restart or normal-dispatch authority. Socket lifetime,
// private listener provisioning and bounded accept scheduling belong to caller.
class ContinuityService {
public:
    static constexpr std::size_t request_budget=32;
    ContinuityService(Recorder&,std::vector<StreamBinding>,ServicePermit,ContinuityCapture&);
    // Connected AF_UNIX/SOCK_SEQPACKET only. Nonblocking receive/send; duplicate
    // exact requests return the original reply even when its first send failed.
    ServiceReply serve(int connected_socket);
private:
    ServiceReply apply(const ServiceRequest&);
    Recorder& writer_;ContinuityInspector inspector_;ServicePermit permit_;ContinuityCapture& capture_;
    struct Cached {std::vector<std::uint8_t> bytes;ServiceReply reply;};
    std::vector<Cached> replies_;std::vector<StreamCut> approved_;EventId approved_pass_{};
    std::uint64_t highest_{0};bool failed_{false};
};
} // namespace stratadrive::diagnostics
