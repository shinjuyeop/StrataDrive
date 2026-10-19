#include "session_loop.hpp"
#include "vehicle_session_init.hpp"

#include <gtest/gtest.h>
#include <algorithm>
#include <condition_variable>
#include <limits>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>

namespace {
using namespace stratadrive;
using namespace stratadrive::session;
constexpr std::uint64_t kMs=1000000,kStart=1000000000;
class CentralPort : public session::CoordinatorPort {
public:
    explicit CentralPort(std::uint64_t& n):now(n) {}
    std::uint64_t& now;
    std::vector<Control> sent;
    bool quiesce_ok{true},commit_ok{true}; std::size_t fail_send{0},commits{0},protections{0};
    std::uint64_t callback_delay{0};
    std::uint64_t now_ns() noexcept override { return now; }
    bool quiesce_central() noexcept override { return quiesce_ok; }
    bool send(const Control& c) noexcept override { sent.push_back(c); return sent.size()!=fail_send; }
    bool commit_central(central::CoordinatorSession) noexcept override { ++commits; now+=callback_delay; return commit_ok; }
    void protect_central() noexcept override { ++protections; }
};
class OwnerPort : public ParticipantPort {
public:
    explicit OwnerPort(std::uint64_t& n):now(n) {}
    std::uint64_t& now; Preparation preparation{Preparation::Ready}; bool init_ok{true};
    std::size_t prepares{0},inits{0},protections{0},services{0}; std::uint64_t delay{0};
    std::thread::id owner{}; bool wrong_owner{false};
    void record() { if(owner==std::thread::id{}) owner=std::this_thread::get_id(); else wrong_owner=wrong_owner || owner!=std::this_thread::get_id(); }
    std::uint64_t now_ns() noexcept override { return now; }
    Preparation prepare(const Plan&) noexcept override { record(); ++prepares; return preparation; }
    bool initialize(const Plan&) noexcept override { record(); ++inits; if(delay!=0) now+=delay; return init_ok; }
    void protect() noexcept override { record(); ++protections; }
    void service() noexcept override { record(); ++services; }
};
struct Scenario {
    std::uint64_t now{kStart}; CentralPort port{now}; SessionLinks links;
    simulation::SessionCentralLoop central{port,links};
    std::vector<std::unique_ptr<OwnerPort>> ports;
    std::vector<std::unique_ptr<simulation::SessionOwnerLoop>> owners;
    Scenario() {
        for(std::size_t i=0;i<kRoleCount;++i) {
            ports.push_back(std::make_unique<OwnerPort>(now));
            owners.push_back(std::make_unique<simulation::SessionOwnerLoop>(static_cast<Role>(i),*ports.back(),links[i]));
        }
    }
    void turn() { for(auto& owner:owners) owner->step(); central.step(); }
    void finish() { for(unsigned i=0;i<60 && central.state()!=State::Running && central.state()!=State::Failed;++i) { turn(); now+=kMs; } }
};
struct ManagerTest : ::testing::Test {
    std::uint64_t now{kStart}; CentralPort port{now}; SessionCoordinator manager{port};
    Ack ack(Role role,Phase phase) { return {role,phase,manager.plan(),now,true}; }
    void all(Phase phase) { for(std::size_t i=0;i<kRoleCount;++i) manager.receive(ack(static_cast<Role>(i),phase),now); }
    void initialized() { ASSERT_TRUE(manager.begin(1,now)); all(Phase::Prepare); now=manager.plan().enable_ns; all(Phase::Initialize); }
};
TEST_F(ManagerTest, EveryInitAndReleaseAckIsRequired) {
    ASSERT_TRUE(manager.begin(1,now)); all(Phase::Prepare); EXPECT_EQ(manager.state(),State::Initializing);
    EXPECT_EQ(port.commits,0U); now=manager.plan().enable_ns;
    for(std::size_t i=0;i<kRoleCount-1;++i) manager.receive(ack(static_cast<Role>(i),Phase::Initialize),now);
    EXPECT_EQ(port.commits,0U); EXPECT_FALSE(manager.run_enabled());
    manager.receive(ack(Role::CentralIngress,Phase::Initialize),now); EXPECT_EQ(port.commits,1U);
    for(std::size_t i=0;i<kRoleCount-1;++i) manager.receive(ack(static_cast<Role>(i),Phase::Release),now);
    EXPECT_FALSE(manager.run_enabled()); manager.receive(ack(Role::CentralIngress,Phase::Release),now);
    EXPECT_TRUE(manager.run_enabled()); EXPECT_EQ(port.commits,1U);
}
TEST_F(ManagerTest, WrongScopePhasePlanAndTimestampsNeverCompletePreparation) {
    ASSERT_TRUE(manager.begin(1,now)); const auto valid=ack(Role::FrontZone,Phase::Prepare);
    for(unsigned i=0;i<8;++i) {
        auto invalid=valid;
        switch(i) {
        case 0: invalid.role=Role::Count; break;
        case 1: invalid.phase=Phase::Release; break;
        case 2: ++invalid.plan.epoch; break;
        case 3: ++invalid.plan.requested_ns; break;
        case 4: ++invalid.plan.prepare_deadline_ns; break;
        case 5: ++invalid.plan.enable_ns; break;
        case 6: ++invalid.source_ns; break;
        default: invalid.source_ns-=kMessageAgeNs+1; break;
        }
        EXPECT_EQ(manager.receive(invalid,now),AckResult::Rejected);
    }
    EXPECT_EQ(manager.state(),State::Preparing); EXPECT_EQ(port.commits,0U);
}
TEST_F(ManagerTest, DuplicateAckIsImmutableAndDoesNotExtendDeadline) {
    ASSERT_TRUE(manager.begin(1,now)); const auto original=ack(Role::FrontZone,Phase::Prepare);
    EXPECT_EQ(manager.receive(original,now),AckResult::Accepted); now+=kMs;
    EXPECT_EQ(manager.receive(original,now),AckResult::Unchanged);
    auto mutation=original; ++mutation.source_ns;
    EXPECT_EQ(manager.receive(mutation,now),AckResult::Rejected);
    const auto deadline=manager.plan().prepare_deadline_ns;
    while(now<deadline) { now+=std::min(kMs,deadline-now); manager.poll(now); }
    EXPECT_EQ(manager.fault(),Fault::Timeout); EXPECT_EQ(port.commits,0U);
}
TEST_F(ManagerTest, LateFinalAckCannotWinAgainstTimeout) {
    ASSERT_TRUE(manager.begin(1,now)); all(Phase::Prepare); now=manager.plan().enable_ns; all(Phase::Initialize);
    now=manager.plan().commit_deadline_ns;
    EXPECT_EQ(manager.receive(ack(Role::FrontZone,Phase::Release),now),AckResult::Latched);
    EXPECT_EQ(manager.fault(),Fault::Timeout); EXPECT_FALSE(manager.run_enabled());
}
TEST_F(ManagerTest, NegativeInitAckProtectsAllAndBurnsEpoch) {
    ASSERT_TRUE(manager.begin(1,now)); all(Phase::Prepare); now=manager.plan().enable_ns;
    auto no=ack(Role::Brake,Phase::Initialize); no.accepted=false;
    EXPECT_EQ(manager.receive(no,now),AckResult::Latched); EXPECT_EQ(manager.fault(),Fault::Participant);
    EXPECT_EQ(port.protections,1U); EXPECT_EQ(port.sent.back().phase,Phase::Abort);
    EXPECT_FALSE(manager.begin(1,now)); EXPECT_TRUE(manager.begin(2,now)); EXPECT_FALSE(manager.run_enabled());
}
TEST_F(ManagerTest, QuiesceSendCommitAndDelayedCallbackFailClosed) {
    port.quiesce_ok=false; EXPECT_FALSE(manager.begin(1,now)); EXPECT_EQ(manager.fault(),Fault::Quiesce);
    port.quiesce_ok=true; port.fail_send=port.sent.size()+2;
    EXPECT_FALSE(manager.begin(2,now)); EXPECT_EQ(manager.fault(),Fault::Send);
    port.fail_send=0; ASSERT_TRUE(manager.begin(3,now)); all(Phase::Prepare); now=manager.plan().enable_ns;
    port.commit_ok=false; all(Phase::Initialize); EXPECT_EQ(manager.fault(),Fault::CentralCommit);
    port.commit_ok=true; ASSERT_TRUE(manager.begin(4,now)); all(Phase::Prepare); now=manager.plan().enable_ns;
    port.callback_delay=kInitWindowNs; all(Phase::Initialize); EXPECT_EQ(manager.fault(),Fault::Timeout);
    EXPECT_FALSE(manager.run_enabled());
}
TEST_F(ManagerTest, GapAndRollbackLatchEvenDuringBootstrap) {
    ASSERT_TRUE(manager.begin(1,now)); now+=kOwnerGapNs+1; manager.poll(now); EXPECT_EQ(manager.fault(),Fault::OwnerGap);
    ASSERT_TRUE(manager.begin(2,now)); manager.poll(now-1); EXPECT_EQ(manager.fault(),Fault::Clock);
}
TEST_F(ManagerTest, NearMaximumClockCannotWrapEnableOrDeadline) {
    now=std::numeric_limits<std::uint64_t>::max()-kPrepareBudgetNs;
    ASSERT_TRUE(manager.begin(1,now));
    const auto end=manager.plan().prepare_deadline_ns-kInitLeadNs;
    while(now<end) { now+=std::min(kMs,end-now); manager.poll(now); }
    all(Phase::Prepare); EXPECT_EQ(manager.fault(),Fault::Timeout); EXPECT_EQ(port.commits,0U);
}
TEST_F(ManagerTest, RunningNeedsExplicitCancellationBeforeNewGrant) {
    initialized(); all(Phase::Release); ASSERT_TRUE(manager.run_enabled()); EXPECT_FALSE(manager.begin(2,now));
    const auto old=ack(Role::FrontZone,Phase::Release); manager.cancel(now); ASSERT_TRUE(manager.begin(2,now));
    EXPECT_EQ(manager.receive(old,now),AckResult::Rejected); EXPECT_FALSE(manager.run_enabled());
}

TEST(SessionLoops, AllEightOwnersInitializeOnceBeforeCentralRunGate) {
    Scenario s; ASSERT_TRUE(s.central.begin(3,s.now)); s.finish(); ASSERT_TRUE(s.central.run_enabled());
    EXPECT_EQ(s.port.commits,1U);
    for(std::size_t i=0;i<kRoleCount;++i) { EXPECT_TRUE(s.owners[i]->run_enabled()); EXPECT_EQ(s.ports[i]->inits,1U); EXPECT_GT(s.ports[i]->services,0U); }
}
TEST(SessionLoops, CallbackClockProgressIsResampledForFollowingOwnerMessages) {
    Scenario s; s.ports[0]->delay=kMs; ASSERT_TRUE(s.central.begin(1,s.now)); s.finish();
    EXPECT_TRUE(s.central.run_enabled()); EXPECT_EQ(s.port.commits,1U); EXPECT_EQ(s.ports[0]->inits,1U);
}
TEST(SessionLoops, LostReleaseCannotOpenGlobalGateEvenAfterCentralCommit) {
    Scenario s; ASSERT_TRUE(s.central.begin(1,s.now));
    for(unsigned i=0;i<30 && s.central.state()!=State::Releasing;++i) { s.turn(); s.now+=kMs; }
    ASSERT_EQ(s.central.state(),State::Releasing); ASSERT_EQ(s.port.commits,1U);
    const auto lost=s.links[3].controls.pop(); ASSERT_TRUE(lost); ASSERT_EQ(lost->phase,Phase::Release);
    for(unsigned i=0;i<30;++i) { s.turn(); s.now+=kMs; }
    EXPECT_FALSE(s.central.run_enabled()); EXPECT_EQ(s.central.fault(),Fault::Timeout);
    EXPECT_FALSE(s.owners[3]->run_enabled()); EXPECT_EQ(s.owners[3]->fault(),ParticipantFault::Timeout);
    EXPECT_EQ(s.port.protections,1U);
}
TEST(SessionLoops, LostOwnerAckAndLostAbortStillCloseItsLocalDeadline) {
    Scenario s; ASSERT_TRUE(s.central.begin(1,s.now));
    auto prepare=s.links[0].controls.pop(); ASSERT_TRUE(prepare); // lose one prepare
    for(unsigned i=0;i<2010;++i) { s.turn(); s.now+=kMs; }
    EXPECT_EQ(s.central.fault(),Fault::Timeout); EXPECT_FALSE(s.central.run_enabled());
    for(std::size_t i=1;i<kRoleCount;++i) EXPECT_FALSE(s.owners[i]->run_enabled());
    // Independent participant with no Abort delivered at all.
    std::uint64_t now=kStart; OwnerPort port{now}; SessionParticipant owner{Role::FrontZone,port};
    ASSERT_TRUE(owner.receive(*prepare,now));
    for(unsigned i=0;i<2000;++i) { now+=kMs; owner.poll(now); }
    EXPECT_EQ(owner.fault(),ParticipantFault::Timeout); EXPECT_EQ(port.protections,1U); EXPECT_GT(port.services,1000U);
}
TEST(SessionLoops, PartialInitializationNeverOpensCentralAndNeedsNewEpoch) {
    Scenario s; s.ports[3]->init_ok=false; ASSERT_TRUE(s.central.begin(1,s.now)); s.finish();
    EXPECT_EQ(s.central.fault(),Fault::Participant); EXPECT_FALSE(s.central.run_enabled()); EXPECT_GT(s.ports[0]->inits,0U);
    EXPECT_FALSE(s.central.begin(1,s.now)); s.ports[3]->init_ok=true;
    ASSERT_TRUE(s.central.begin(2,s.now)); s.finish(); EXPECT_TRUE(s.central.run_enabled()); EXPECT_EQ(s.port.commits,1U);
}
TEST(SessionLoops, PreparationWaitServicesProtectionWithoutInitializing) {
    Scenario s; s.ports[5]->preparation=Preparation::Pending; ASSERT_TRUE(s.central.begin(1,s.now));
    for(unsigned i=0;i<100;++i) { s.turn(); s.now+=kMs; }
    EXPECT_EQ(s.central.state(),State::Preparing); EXPECT_EQ(s.ports[0]->inits,0U); EXPECT_GT(s.ports[5]->services,90U);
    s.ports[5]->preparation=Preparation::Ready; s.finish(); EXPECT_TRUE(s.central.run_enabled());
    EXPECT_GT(s.central.plan().enable_ns,kStart+100*kMs);
}
TEST(SessionLoops, OverflowInvalidatesBacklogAndCannotBeClearedByNewEpoch) {
    Scenario s; ASSERT_TRUE(s.central.begin(1,s.now)); const auto control=s.links[0].controls.pop(); ASSERT_TRUE(control);
    for(std::size_t i=0;i<kSessionQueueCapacity;++i) ASSERT_TRUE(s.links[0].controls.push(*control));
    EXPECT_FALSE(s.links[0].controls.push(*control)); EXPECT_FALSE(s.links[0].controls.pop()); s.turn();
    EXPECT_EQ(s.central.fault(),Fault::Continuity); EXPECT_EQ(s.owners[0]->fault(),ParticipantFault::Continuity);
    EXPECT_FALSE(s.central.begin(2,s.now)); EXPECT_FALSE(s.central.run_enabled());
}
TEST(SessionLoops, AckOverflowAndCrossedRoleLinkFailClosed) {
    Scenario s; ASSERT_TRUE(s.central.begin(1,s.now)); const Ack ack{Role::RearZone,Phase::Prepare,s.central.plan(),s.now,true};
    ASSERT_TRUE(s.links[0].acks.push(ack)); s.central.step(); EXPECT_EQ(s.central.fault(),Fault::Continuity);
    Scenario t; ASSERT_TRUE(t.central.begin(1,t.now));
    for(std::size_t i=0;i<kSessionQueueCapacity;++i) ASSERT_TRUE(t.links[1].acks.push(ack));
    EXPECT_FALSE(t.links[1].acks.push(ack)); t.turn(); EXPECT_EQ(t.central.fault(),Fault::Continuity);
}
TEST(SessionLoops, RunningGateObservesLinkFailureBeforeNextCentralStep) {
    Scenario s; ASSERT_TRUE(s.central.begin(1,s.now)); s.finish(); ASSERT_TRUE(s.central.run_enabled());
    const Ack duplicate{Role::Power,Phase::Release,s.central.plan(),s.now,true};
    for(std::size_t i=0;i<kSessionQueueCapacity;++i) ASSERT_TRUE(s.links[6].acks.push(duplicate));
    EXPECT_FALSE(s.links[6].acks.push(duplicate)); EXPECT_FALSE(s.central.run_enabled());
    s.central.step(); EXPECT_EQ(s.central.fault(),Fault::Continuity); EXPECT_EQ(s.port.protections,1U);
}
TEST(SessionParticipant, FrozenDuplicateMutationAndLateInitAreRejected) {
    std::uint64_t now=kStart; OwnerPort port{now}; SessionParticipant owner{Role::FrontZone,port};
    const Plan initial{1,now,now+kPrepareBudgetNs,0,0}; const Control prepare{Role::FrontZone,Phase::Prepare,initial,now};
    const auto first=owner.receive(prepare,now); ASSERT_TRUE(first);
    now+=kMs; const auto duplicate=owner.receive(prepare,now); ASSERT_TRUE(duplicate); EXPECT_TRUE(same_ack(*first,*duplicate));
    auto changed=prepare; ++changed.source_ns; EXPECT_FALSE(owner.receive(changed,now)); EXPECT_EQ(port.prepares,1U);
    auto plan=initial; plan.enable_ns=now+kInitLeadNs; plan.commit_deadline_ns=plan.enable_ns+kInitWindowNs;
    const Control init{Role::FrontZone,Phase::Initialize,plan,now}; EXPECT_FALSE(owner.receive(init,now));
    now=plan.commit_deadline_ns; EXPECT_FALSE(owner.receive(init,now)); EXPECT_FALSE(owner.run_enabled()); EXPECT_EQ(port.inits,0U);
}
TEST(SessionParticipant, CallbackOverrunAndClockRollbackNeverAckSuccess) {
    std::uint64_t now=kStart; OwnerPort port{now}; SessionParticipant owner{Role::Drive,port};
    Plan plan{1,now,now+kPrepareBudgetNs,0,0}; ASSERT_TRUE(owner.receive({Role::Drive,Phase::Prepare,plan,now},now));
    plan.enable_ns=now+kInitLeadNs; plan.commit_deadline_ns=plan.enable_ns+kInitWindowNs;
    EXPECT_FALSE(owner.receive({Role::Drive,Phase::Initialize,plan,now},now)); now=plan.enable_ns; port.delay=kInitWindowNs;
    EXPECT_FALSE(owner.poll(now)); EXPECT_EQ(owner.fault(),ParticipantFault::Timeout); EXPECT_FALSE(owner.run_enabled());
    owner.poll(now-1); EXPECT_EQ(owner.fault(),ParticipantFault::Clock);
}
TEST(SessionParticipant, ScheduledInitPrecedesOldActorServiceWhenWakeIsSlightlyLate) {
    class BoundaryPort final : public ParticipantPort {
    public:
        std::uint64_t now{kStart},serviced{kStart};
        std::uint64_t now_ns() noexcept override { return now; }
        Preparation prepare(const Plan&) noexcept override { return Preparation::Ready; }
        bool initialize(const Plan& plan) noexcept override { return plan.enable_ns>=serviced; }
        void protect() noexcept override {}
        void service() noexcept override { serviced=now; }
    } port;
    SessionParticipant owner{Role::Drive,port}; Plan plan{1,kStart,kStart+kPrepareBudgetNs,0,0};
    ASSERT_TRUE(owner.receive({Role::Drive,Phase::Prepare,plan,kStart},port.now));
    plan.enable_ns=kStart+kInitLeadNs; plan.commit_deadline_ns=plan.enable_ns+kInitWindowNs;
    EXPECT_FALSE(owner.receive({Role::Drive,Phase::Initialize,plan,kStart},port.now));
    port.now=plan.enable_ns+kMs; const auto initialized=owner.poll(port.now); ASSERT_TRUE(initialized);
    EXPECT_TRUE(initialized->accepted); EXPECT_EQ(initialized->phase,Phase::Initialize); EXPECT_EQ(port.serviced,port.now);
    EXPECT_EQ(owner.fault(),ParticipantFault::None);
}
TEST(SessionMailbox, WraparoundPreservesOrderAndFullCapacity) {
    SessionMailbox<Ack,3> queue;
    for(std::uint32_t epoch=1;epoch<200;++epoch) {
        for(unsigned i=0;i<3;++i) ASSERT_TRUE(queue.push({Role::Power,Phase::Initialize,{epoch,i,0,0,0},i,true}));
        for(unsigned i=0;i<3;++i) { const auto ack=queue.pop(); ASSERT_TRUE(ack); EXPECT_EQ(ack->plan.epoch,epoch); EXPECT_EQ(ack->source_ns,i); }
        EXPECT_FALSE(queue.pop());
    }
}
TEST(SessionLoops, EightIndependentOwnerThreadsExchangeOnlyTypedMailboxes) {
    Scenario s; std::mutex mutex; std::condition_variable cv;
    unsigned generation=0,completed=0; bool stopping=false; std::vector<std::thread> threads;
    for(std::size_t i=0;i<kRoleCount;++i) threads.emplace_back([&,i] {
        unsigned seen=0;
        for(;;) {
            std::unique_lock<std::mutex> lock(mutex); cv.wait(lock,[&] { return stopping || generation!=seen; });
            if(stopping) break;
            seen=generation; lock.unlock(); s.owners[i]->step(); lock.lock(); ++completed; cv.notify_all();
        }
    });
    const bool started=s.central.begin(1,s.now);
    for(unsigned cycle=0;cycle<60 && !s.central.run_enabled();++cycle) {
        { std::lock_guard<std::mutex> lock(mutex); completed=0; ++generation; }
        cv.notify_all();
        { std::unique_lock<std::mutex> lock(mutex); cv.wait(lock,[&] { return completed==kRoleCount; }); }
        s.central.step(); s.now+=kMs;
    }
    { std::lock_guard<std::mutex> lock(mutex); stopping=true; } cv.notify_all();
    std::vector<std::thread::id> ids;
    for(auto& thread:threads) { ids.push_back(thread.get_id()); thread.join(); }
    ASSERT_TRUE(started); EXPECT_TRUE(s.central.run_enabled());
    for(std::size_t i=0;i<kRoleCount;++i) {
        EXPECT_FALSE(s.ports[i]->wrong_owner); EXPECT_EQ(s.ports[i]->owner,ids[i]);
    }
}
simulation::SessionResetEvidence evidence(std::uint64_t now) {
    simulation::SessionResetEvidence e;
    e.wheel_speed_rad_s=battery::ModelMeasurement<double>{0,{7,10,now},now};
    e.torque=drive::TorqueMeasurement{7,10,now,0};
    power::SensorSnapshot p; p.identity={7,10,now}; p.input_time_ns=now; p.bus_voltage_v=0; p.contactors=power::ContactorPositions{};
    e.power=p; return e;
}
TEST(SessionReset, RequiresKnownFreshMatchingPhysicalEvidence) {
    const auto good=evidence(kStart); EXPECT_TRUE(simulation::session_reset_safe(good,7,kStart));
    for(unsigned i=0;i<12;++i) {
        auto e=good;
        switch(i) {
        case 0: e.wheel_speed_rad_s.reset(); break;
        case 1: e.wheel_speed_rad_s->value=.011; break;
        case 2: e.torque->torque_nm=-.101; break;
        case 3: e.power->bus_voltage_v=30.01; break;
        case 4: e.power->contactors->positive=true; break;
        case 5: e.power->contactors.reset(); break;
        case 6: e.wheel_speed_rad_s->input_time_ns-=20000001; break;
        case 7: ++e.power->identity.source_time_ns; break;
        case 8: ++e.torque->model_epoch; break;
        case 9: e.power->bus_voltage_v=std::numeric_limits<double>::quiet_NaN(); break;
        case 10: e.wheel_speed_rad_s->value=-.1; break;
        default: e.power->bus_voltage_v.reset(); break;
        }
        EXPECT_FALSE(simulation::session_reset_safe(e,7,kStart))<<i;
    }
    EXPECT_FALSE(simulation::session_reset_safe(good,0,kStart));
    EXPECT_FALSE(simulation::session_reset_safe(good,7,kStart+20000001));
}
}  // namespace
