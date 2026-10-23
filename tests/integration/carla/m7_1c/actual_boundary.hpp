#pragma once
// Test-only M7 semantic prototype. No CARLA library, transport or authority issuer.
#include "steering_receiver.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <memory>
#include <thread>

namespace stratadrive::m7_test {
using Time = std::uint64_t;
constexpr Time ms = 1000000, age = 30*ms, skew = 10*ms;
enum class Code { Ok, Writer, Init, Clock, Source, Missing, Receiver, Time, Expired,
                  Stale, Skew, Frame, Pending, Ticket, Disabled, Coverage, ApplyRejected,
                  ApplyAmbiguous, TickAmbiguous };
enum class Role { Steering, Brake, Drive };
// Fixture-side measurement support, not a new CAN field or command permission.
// Supplied by the trusted launch/port binding; never synthesized from receipt time.
struct Support { Role role; Time oldest, exclusive_expiry; };
struct Provenance {
    std::uint64_t run, clock;
    std::uint32_t plant;
    std::array<Support,3> support;
};
struct Frames {
    std::optional<can::SteeringFrame> steering;
    std::optional<can::BrakeFrame> brake;
    std::optional<can::DriveFrame> drive;
};
struct ActualBundle {
    can::SteeringMessage steering;
    can::BrakeMessage brake;
    can::DriveMessage drive;
    Frames original_frames;
    Provenance provenance;
    Time received_at;
};
struct Interval { std::uint64_t frame; Time begin, end; };
enum class Mode { NonDriving, FakeProbe, CarlaDriving };
enum class ApplyResult { Applied, Rejected, Ambiguous };
class Boundary;
class Backend {
public:
    virtual ~Backend() = default;
private:
    friend class Boundary;
    std::atomic_flag claimed_=ATOMIC_FLAG_INIT;
    virtual ApplyResult apply(const ActualBundle&, const Interval&) = 0;
    virtual bool tick(const Interval&) = 0;
};
class Boundary {
public:
    class Writer {
        friend class Boundary;
        explicit Writer(const Boundary* b): boundary_(b) {}
        const Boundary* boundary_;
    public:
        Writer(const Writer&) = delete;
        Writer& operator=(const Writer&) = delete;
    };
    explicit Boundary(Backend& backend): backend_(backend), thread_(std::this_thread::get_id()), bound_(!backend.claimed_.test_and_set()) {}
    Boundary(const Boundary&) = delete;
    Boundary& operator=(const Boundary&) = delete;
    std::unique_ptr<Writer> claim() {
        if (std::this_thread::get_id()!=thread_ || !bound_ || claimed_) return {};
        claimed_=true; return std::unique_ptr<Writer>(new Writer(this));
    }
    // Explicit trusted INIT only; packets never initialize or learn these IDs.
    Code start(const Writer& w, std::uint32_t app, std::uint32_t plant,
               std::uint64_t run, std::uint64_t clock, Time now) {
        if (!owns(w)) return Code::Writer;
        if (dispatching_) return Code::Pending;
        if (!app || !plant || !run || !clock || (state_ &&
            (app<=app_ || plant<plant_ || now<last_))) return Code::Init;
        auto s=std::make_unique<State>();
        if (!s->steering.start_session(app,now) || !s->brake.start_session(app,now) ||
            !s->drive.start_session(app,now)) return Code::Init;
        state_=std::move(s); app_=app; plant_=plant; run_=run; domain_=clock; last_=enable_=now;
        fault_=Code::Ok; accepted_.reset(); pending_.reset(); applied_.reset(); next_frame_=1;
        // Ticket IDs never reset, so a prior-session ticket cannot bind a new step.
        return Code::Ok;
    }
    Code receive(const Writer& w, const Frames& frames, const Provenance& p, Time now) {
        if (!owns(w)) return Code::Writer;
        if (auto c=clock(now); c!=Code::Ok) return c;
        if (pending_ || applied_ || dispatching_) return fail(Code::Pending);
        if (p.run!=run_ || p.clock!=domain_ || p.plant!=plant_ ||
            p.support[0].role!=Role::Steering || p.support[1].role!=Role::Brake ||
            p.support[2].role!=Role::Drive) return fail(Code::Source);
        if (!frames.steering || !frames.brake || !frames.drive) return fail(Code::Missing);
        // Actual-configured native receivers enforce original CAN/P05/mode/epoch/age.
        if (state_->steering.receive(*frames.steering,now).decision!=can::ActuatorReceiveDecision::Accepted ||
            state_->brake.receive(*frames.brake,now).decision!=can::ActuatorReceiveDecision::Accepted ||
            state_->drive.receive(*frames.drive,now).decision!=can::ActuatorReceiveDecision::Accepted)
            return fail(Code::Receiver);
        auto s=state_->steering.current_sample(now);
        auto b=state_->brake.current_sample(now);
        auto d=state_->drive.current_sample(now);
        if (!s || !b || !d) return fail(Code::Receiver);
        ActualBundle candidate{*s,*b,*d,frames,p,now};
        if (auto c=valid(candidate,now,now); c!=Code::Ok) return fail(c);
        accepted_=std::move(candidate); return Code::Ok;
    }
    // Returned ticket is an index into a private immutable pending snapshot.
    // No caller-provided doubles or caller-modifiable prepared bundle are consumed.
    Code prepare(const Writer& w, Mode mode, Interval interval, Time now, std::uint64_t& ticket) {
        if (!owns(w)) return Code::Writer;
        if (auto c=clock(now); c!=Code::Ok) return c;
        if (mode!=Mode::FakeProbe) return fail(Code::Disabled);
        if (pending_ || applied_ || dispatching_) return fail(Code::Pending);
        if (interval.frame!=next_frame_ || interval.begin<now || interval.end<=interval.begin)
            return fail(Code::Frame);
        if (!accepted_ || !state_->steering.current_sample(now) || !state_->brake.current_sample(now) ||
            !state_->drive.current_sample(now)) return fail(Code::Missing);
        if (auto c=valid(*accepted_,now,interval.end); c!=Code::Ok) return fail(c);
        if (serial_==UINT64_MAX) return fail(Code::Ticket);
        ticket=++serial_; pending_=Prepared{ticket,*accepted_,interval}; return Code::Ok;
    }
    Code commit(const Writer& w, std::uint64_t ticket, Time now) {
        if (!owns(w)) return Code::Writer;
        if (auto c=clock(now); c!=Code::Ok) return c;
        if (!pending_ || pending_->ticket!=ticket) return fail(Code::Ticket);
        if (auto c=valid(pending_->actual,now,pending_->interval.end); c!=Code::Ok) return fail(c);
        if (now>pending_->interval.begin) return fail(Code::Time);
        const auto step=*pending_; pending_.reset(); // consume before any backend call
        ApplyResult result=ApplyResult::Ambiguous;
        dispatching_=true;
        try { result=backend_.apply(step.actual,step.interval); }
        catch (...) { dispatching_=false; return fail(Code::ApplyAmbiguous); }
        dispatching_=false;
        if (fault_!=Code::Ok) return fault_;
        if (result==ApplyResult::Rejected) return fail(Code::ApplyRejected);
        if (result==ApplyResult::Ambiguous) return fail(Code::ApplyAmbiguous);
        applied_=step; return Code::Ok;
    }
    // Tick-owner request has its own captured thread identity, expected frame,
    // and single-use applied ticket. No tick is granted after ambiguous apply.
    Code advance(const Writer& w, std::uint64_t ticket, std::uint64_t frame, Time now) {
        if (!owns(w)) return Code::Writer;
        if (auto c=clock(now); c!=Code::Ok) return c;
        if (!applied_ || applied_->ticket!=ticket || frame!=next_frame_ ||
            frame!=applied_->interval.frame) return fail(Code::Ticket);
        if (auto c=valid(applied_->actual,now,applied_->interval.end); c!=Code::Ok) return fail(c);
        if (now>applied_->interval.begin) return fail(Code::Time);
        const auto step=*applied_; applied_.reset();
        bool acknowledged=false;
        dispatching_=true;
        try { acknowledged=backend_.tick(step.interval); }
        catch (...) { dispatching_=false; return fail(Code::TickAmbiguous); }
        dispatching_=false;
        if (fault_!=Code::Ok) return fault_;
        if (!acknowledged) return fail(Code::TickAmbiguous);
        ++next_frame_; return Code::Ok;
    }
    Code fault() const { return fault_; }
private:
    struct State {
        // Existing M6 fixture ranges, not CARLA normalization/calibration.
        can::SteeringReceiver steering{{can::SteeringFrameKind::Actual,-.3,.3}};
        can::BrakeReceiver brake{{can::BrakeFrameKind::Actual,0,1500000}};
        can::DriveReceiver drive{{can::DriveFrameKind::Actual,{-200,300},100,200}};
    };
    struct Prepared { std::uint64_t ticket; ActualBundle actual; Interval interval; };
    bool owns(const Writer& w) const {
        return bound_ && w.boundary_==this && std::this_thread::get_id()==thread_;
    }
    Code fail(Code c) { if (fault_==Code::Ok) fault_=c; return fault_; }
    Code clock(Time now) {
        if (!state_) return Code::Init;
        if (now<last_) return fail(Code::Clock);
        last_=now; return fault_;
    }
    Code valid(const ActualBundle& a, Time now, Time end) const {
        const std::array<Time,3> sources{a.steering.source_time_ns,a.brake.source_time_ns,a.drive.source_time_ns};
        Time oldest=UINT64_MAX,newest=0;
        for (std::size_t i=0;i<sources.size();++i) {
            const auto& support=a.provenance.support[i];
            if (support.oldest<enable_ || support.oldest>sources[i] || sources[i]>now || support.exclusive_expiry<=sources[i]) return Code::Time;
            if (now>=support.exclusive_expiry || end>support.exclusive_expiry) return Code::Expired;
            if (now-support.oldest>age) return Code::Stale;
            // Pure interval check: never poll a native receiver at a future end time.
            if (end<now || end-support.oldest>age) return Code::Coverage;
            oldest=std::min(oldest,support.oldest); newest=std::max(newest,sources[i]);
        }
        if (newest-oldest>skew) return Code::Skew;
        return Code::Ok;
    }
    Backend& backend_;
    const std::thread::id thread_;
    const bool bound_;
    bool claimed_{false},dispatching_{false};
    std::unique_ptr<State> state_;
    std::uint32_t app_{0},plant_{0};
    std::uint64_t run_{0},domain_{0},serial_{0},next_frame_{1};
    Time last_{0},enable_{0};
    Code fault_{Code::Ok};
    std::optional<ActualBundle> accepted_;
    std::optional<Prepared> pending_,applied_;
};
} // namespace stratadrive::m7_test
