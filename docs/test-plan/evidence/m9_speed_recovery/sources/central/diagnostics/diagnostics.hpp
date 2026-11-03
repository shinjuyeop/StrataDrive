#pragma once

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <variant>
#include <vector>

namespace stratadrive::diagnostics {
enum class Code : std::uint16_t {
    None=0, SpeedInput=0x1001, CentralControl=0x1002, BrakingTimeout=0x1101,
    Handoff=0x1102, StopEvidence=0x1103, ShutdownTimeout=0x1104, StopRequest=0x1105,
    CommandLoss=0x2001, FeedbackLoss=0x2002, Response=0x3001,
    Clock=0x4001, Deadline=0x4002, RecordingGap=0x5001
};
enum class Kind : std::uint8_t { Observation, Fault, ProtectionSelected, ProtectionAck, Actual, Passed, Session, Gap, Unavailable };
enum class Condition : std::uint8_t { Unknown, Failed, Passed };
enum class Latch : std::uint8_t { Unknown, Set, Clear };
enum class Domain : std::uint8_t { Unknown, Simulation, Monotonic };
enum class Proof : std::uint8_t { None, Input, Control, Stop, Handoff, Hold, Shutdown, Response, Recording };
enum class Time : std::size_t { Injection, Violation, Detected, Selected, Acknowledged, Actual, Observed, Recorded, Count };
struct Stamp { Domain domain{Domain::Unknown}; std::uint64_t instance{0}, ns{0}; bool present{false}, trusted{false}; };
struct EventId { std::uint64_t run{0}, producer{0}, sequence{0}; };
struct Session { std::uint64_t run{0}; std::uint32_t epoch{0}; };
struct Key { Code code{Code::None}; std::uint32_t component{0}, monitor{0}, subject{0}; };
struct Occurrence { std::uint64_t run{0}, producer{0}; std::uint32_t epoch{0}, monitor{0}; std::uint64_t sequence{0}; };
struct Identity { bool present{false}; std::uint64_t producer{0}, sequence{0}; std::uint32_t epoch{0}; Stamp source{}, expiry{}; };
// Numeric component/subject/profile/reason/requirement/interface dictionaries
// belong in the run manifest. No strings, allocation, IO or actuator authority.
struct Event {
    std::uint16_t schema{1}; EventId id{}, related{}, proof_event{};
    Session session{}; Key key{}; Occurrence occurrence{};
    Kind kind{Kind::Observation}; Latch latch{Latch::Unknown}; Proof proof{Proof::None};
    std::uint32_t native_reason{0}, severity{0}, model_epoch{0}, state_before{0}, state_after{0};
    std::uint64_t profile{0}, requirements{0}, interfaces{0}; Stamp session_enable{};
    Identity source{}, command{}, stop_lease{};
    std::array<Stamp, static_cast<std::size_t>(Time::Count)> times{};
    std::uint32_t expected_roles{0}, received_roles{0};
    bool cause_unknown{false}, unmapped{false};
    double measured{0}, expected_min{0}, expected_max{0};
};
bool operator==(const EventId&, const EventId&) noexcept;
bool operator==(const Session&, const Session&) noexcept;
bool operator==(const Key&, const Key&) noexcept;
bool operator==(const Occurrence&, const Occurrence&) noexcept;
bool comparable(const Stamp&, const Stamp&) noexcept;

struct Limits { std::uint32_t events{512}, records{64}, occurrences{128}, clears{64}; };
void validate(Limits);
struct Record {
    Key key{}; std::uint64_t generation{1}, revision{0}, count{0};
    Occurrence first{}, last{}; EventId first_event{}, last_event{}, pass_event{};
    Stamp first_detected{}, last_detected{}; Session state_session{};
    EventId state_event{}; Condition condition{Condition::Unknown}; Latch latch{Latch::Unknown};
    bool cleared{false};
};
struct ClearTarget { Key key{}; std::uint64_t revision{0}; };
// Trusted writer-side evidence, supplied by the real admission/monitor adapter.
// This component checks freshness/values but cannot authenticate their origin.
struct ServiceEvidence {
    Stamp now{}, enable{}, wheel{}, drive{}, brake{};
    double wheel_rad_s{0}, torque_nm{0}, pressure_pa{0};
    bool current_streams_valid{false}, normal_dispatch_inhibited{false};
};
struct Clear {
    EventId id{}; Session session{}; ServiceEvidence evidence{};
    bool all{false}; std::vector<ClearTarget> targets;
};
using Entry = std::variant<Event, Clear>;
enum class Result { Accepted, Duplicate, Invalid, Conflict, Capacity, NotReady, StorageFailure };

// Single non-RT consumer. Bounded history, no silent eviction. A loss is sticky:
// create/reconcile a complete store before allowing further clears.
class Ledger {
public:
    explicit Ledger(Limits limits = {});
    Result record(const Event&);
    Result clear(const Clear&);
    const Record* find(const Key&) const noexcept;
    const std::vector<Record>& records() const noexcept { return records_; }
    const std::vector<Event>& events() const noexcept { return events_; }
    Session session() const noexcept { return session_; }
    bool complete() const noexcept { return complete_; }
    bool unmapped() const noexcept { return unmapped_; }
    void recording_gap() noexcept;
    void restarted() noexcept;
private:
    struct Episode { Occurrence id; Key key; std::uint64_t generation; bool confirmed; };
    Result apply(const Event&);
    void project(const Event&);
    bool pass(const Event&);
    Record* mutable_record(const Key&) noexcept;
    Limits limits_; Session session_{}; Stamp enable_{}; std::uint64_t revision_{0};
    bool complete_{true}, unmapped_{false};
    std::vector<Event> events_; std::vector<Record> records_;
    std::vector<Episode> episodes_; std::vector<Clear> clears_;
};

// Single producer and single consumer, one immutable producer identity per queue.
// Lock-free indices are required; publishing cannot block on a diagnostic writer.
class EventQueue {
public:
    static constexpr std::size_t kCapacity=256;
    struct Health { std::uint64_t dropped, first_lost_sequence; bool identity_error; };
    EventQueue(std::uint64_t run, std::uint64_t producer);
    bool publish(const Event&) noexcept;
    bool pop(Event&) noexcept;
    Health health() const noexcept;
private:
    const std::uint64_t run_, producer_;
    std::array<Event,kCapacity+1> entries_{};
    std::atomic<std::size_t> read_{0}, write_{0};
    std::atomic<std::uint64_t> dropped_{0}, first_lost_{0};
    std::atomic<bool> identity_error_{false};
};

// Canonical, versioned storage encoding; never serialize C++ struct padding.
std::vector<std::uint8_t> encode(const Entry&);
Entry decode(const std::vector<std::uint8_t>&);

class Journal {
public:
    virtual ~Journal() = default;
    virtual Limits limits() const noexcept = 0;
    virtual const std::vector<Entry>& committed() const noexcept = 0;
    virtual bool writable() const noexcept = 0;
    virtual bool append(const Entry&) = 0;
    virtual void invalidate() noexcept = 0;
};
struct Receipt { Result result; bool durable; std::uint64_t watermark; };
// Writer-only orchestration. Call record/clear away from every RT owner.
class Recorder {
public:
    explicit Recorder(Journal&);
    Receipt record(const Event&);
    Receipt clear(const Clear&);
    std::size_t drain(EventQueue&,std::size_t budget=EventQueue::kCapacity);
    const Ledger& ledger() const noexcept { return ledger_; }
private:
    Journal& journal_; Ledger ledger_;
};
} // namespace stratadrive::diagnostics
