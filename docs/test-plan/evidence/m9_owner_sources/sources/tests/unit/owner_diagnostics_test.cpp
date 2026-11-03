#include "owner_diagnostics.hpp"
#include "diagnostics_fixture.hpp"
#include <gtest/gtest.h>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart=1000000000,kMs=1000000;
class Port final : public zone::GatewayPort {
public:
    std::uint64_t now{kStart}; unsigned selections{0};
    std::uint64_t now_ns() noexcept override { return now; }
    bool send(const zone::CommandFrame&,const central::CommandContext&) noexcept override { return true; }
    bool protect(zone::ZoneScope,zone::ProtectionCause,std::uint64_t) noexcept override { ++selections; return true; }
};
zone::ZoneFeedbackInputs inputs(std::uint64_t now,std::uint32_t epoch=1) {
    zone::ZoneFeedbackInputs in; in.steering.emplace(); in.brake.emplace();
    in.steering->kind=can::SteeringFrameKind::Actual; in.steering->epoch=epoch; in.steering->sequence=static_cast<unsigned>(now/kMs);
    in.steering->source_time_ns=now; in.steering->angle_rad=0;
    in.steering->local_state=can::SteeringLocalState::Normal; in.steering->origin=can::SteeringOrigin::NormalPath;
    in.brake->kind=can::BrakeFrameKind::Actual; in.brake->epoch=epoch; in.brake->sequence=static_cast<unsigned>(now/kMs);
    in.brake->source_time_ns=now; in.brake->pressure_pa=100000;
    in.brake->local_state=can::ActuatorLocalState::Normal; in.brake->origin=can::ActuatorOrigin::NormalPath; return in;
}
class OwnerDiagnosticsTest : public ::testing::Test {
protected:
    Port port; zone::CommandGateway commands{zone::ZoneScope::Front,port}; zone::ZoneFeedbackMonitor monitor{commands};
    diagnostics::EventQueue queue{3001,20};
    diagnostics::OwnerDiagnostics hook{queue,{3001,20,diagnostics::Domain::Simulation,3001,1},diagnostics::Component::Front};
    diagnostics::Ledger ledger;
    void session(unsigned epoch,std::uint64_t enable) {
        ASSERT_TRUE(commands.start_session(epoch,enable)); ASSERT_TRUE(monitor.start_session(epoch,enable)); ASSERT_TRUE(hook.start_session(epoch,enable));
        diagnostics::Event e; e.id={3001,7,epoch}; e.kind=diagnostics::Kind::Session; e.session={3001,epoch};
        e.session_enable={diagnostics::Domain::Simulation,3001,enable,true,true}; ASSERT_EQ(ledger.record(e),diagnostics::Result::Accepted);
    }
    void drain() { diagnostics::Event e; while(queue.pop(e)) { ASSERT_EQ(ledger.record(e),diagnostics::Result::Accepted); } }
    void tick(unsigned ms,zone::ZoneFeedbackInputs in,bool gate=true) {
        port.now=kStart+ms*kMs; ASSERT_TRUE(monitor.tick(in,port.now)); hook.zone(monitor,gate,std::nullopt,port.now); drain();
    }
};
TEST_F(OwnerDiagnosticsTest, RealZoneLossRetainsLastHealthySourceAndOnlyNewQualifiedSessionPasses) {
    session(1,kStart); tick(10,inputs(kStart+10*kMs));
    auto missing=inputs(kStart+20*kMs); missing.steering.reset(); tick(20,missing);
    ASSERT_TRUE(monitor.fault_observation()); EXPECT_EQ(monitor.fault_observation()->observed_ns,kStart+20*kMs);
    ASSERT_EQ(ledger.records().size(),1U); const auto key=ledger.records()[0].key;
    EXPECT_EQ(key.code,diagnostics::Code::FeedbackLoss); EXPECT_EQ(key.component,7U); EXPECT_EQ(key.subject,1U);
    EXPECT_EQ(port.selections,1U); EXPECT_EQ(ledger.find(key)->count,1U);
    ASSERT_TRUE(monitor.fault_observation()->last_healthy.steering);
    EXPECT_EQ(monitor.fault_observation()->last_healthy.steering->source_time_ns,kStart+10*kMs);
    tick(30,inputs(kStart+30*kMs)); EXPECT_EQ(ledger.find(key)->condition,diagnostics::Condition::Failed);
    const auto native_first=*monitor.fault_observation();
    port.now=kStart+29*kMs; EXPECT_FALSE(monitor.tick({},port.now));
    EXPECT_EQ(monitor.fault_observation()->observed_ns,native_first.observed_ns); EXPECT_EQ(monitor.fault_observation()->fault,native_first.fault);
    port.now=kStart+40*kMs; session(2,port.now); drain(); EXPECT_EQ(ledger.find(key)->condition,diagnostics::Condition::Unknown);
    hook.zone(monitor,true,std::nullopt,port.now); drain(); EXPECT_EQ(ledger.find(key)->condition,diagnostics::Condition::Unknown);
    tick(50,inputs(kStart+50*kMs,2),false); EXPECT_EQ(ledger.find(key)->condition,diagnostics::Condition::Unknown);
    hook.zone(monitor,true,std::nullopt,kStart+81*kMs); drain(); EXPECT_EQ(ledger.find(key)->condition,diagnostics::Condition::Unknown);
    tick(60,inputs(kStart+60*kMs,2)); EXPECT_EQ(ledger.find(key)->condition,diagnostics::Condition::Passed);
    EXPECT_FALSE(ledger.find(key)->cleared); EXPECT_EQ(ledger.find(key)->count,1U);
    const auto count=ledger.events().size(); hook.zone(monitor,true,std::nullopt,port.now); drain(); EXPECT_EQ(ledger.events().size(),count);
}
TEST_F(OwnerDiagnosticsTest, ProtectedChildAndGatewayPropagationNeverInventFeedbackLoss) {
    for(bool child:{false,true}) {
        Port p; zone::CommandGateway c{zone::ZoneScope::Front,p}; zone::ZoneFeedbackMonitor m{c};
        diagnostics::EventQueue q{3001,20}; diagnostics::OwnerDiagnostics h{q,{3001,20,diagnostics::Domain::Simulation,3001,1},diagnostics::Component::Front};
        ASSERT_TRUE(c.start_session(1,kStart)); ASSERT_TRUE(m.start_session(1,kStart)); ASSERT_TRUE(h.start_session(1,kStart));
        auto in=inputs(kStart+10*kMs); p.now=kStart+10*kMs;
        if(child) { in.brake->origin=can::ActuatorOrigin::LocalProtection; in.brake->local_state=can::ActuatorLocalState::FailSafe; }
        else c.request_protection();
        ASSERT_TRUE(m.tick(in,p.now)); h.zone(m,false,std::nullopt,p.now);
        diagnostics::Event e; ASSERT_TRUE(q.pop(e)); EXPECT_EQ(e.kind,diagnostics::Kind::Observation); EXPECT_EQ(e.key.code,diagnostics::Code::None);
        EXPECT_TRUE(e.cause_unknown); EXPECT_FALSE(e.unmapped); EXPECT_FALSE(q.pop(e));
    }
}
TEST_F(OwnerDiagnosticsTest, MissingStartupAndDeadlineAreDifferentNativeDetections) {
    session(1,kStart);
    for(unsigned ms=10;ms<=80;ms+=10) tick(ms,{},false);
    ASSERT_EQ(ledger.records().size(),1U); EXPECT_EQ(ledger.records()[0].key.code,diagnostics::Code::FeedbackLoss);
    EXPECT_EQ(ledger.records()[0].key.subject,3U); EXPECT_EQ(ledger.records()[0].first_detected.ns,kStart+80*kMs);
    port.now=kStart+90*kMs; session(2,port.now);
    tick(130,inputs(kStart+130*kMs,2),false);
    ASSERT_EQ(ledger.records().size(),2U); EXPECT_EQ(ledger.records()[1].key.code,diagnostics::Code::Deadline);
}
TEST_F(OwnerDiagnosticsTest, FullDiagnosticQueueCannotChangeNativeZoneProtection) {
    session(1,kStart); diagnostics::Event filler; filler.id={3001,20,1};
    for(unsigned ms=10;ms<80;ms+=10) {
        port.now=kStart+ms*kMs; ASSERT_TRUE(monitor.tick({},port.now));
    }
    for(std::size_t i=0;i<diagnostics::EventQueue::kCapacity;++i) { ++filler.id.sequence; ASSERT_TRUE(queue.publish(filler)); }
    port.now=kStart+80*kMs; ASSERT_TRUE(monitor.tick({},port.now)); hook.zone(monitor,false,std::nullopt,port.now);
    EXPECT_EQ(monitor.fault(),zone::ZoneFeedbackFault::InputsUnavailable); EXPECT_EQ(port.selections,1U);
    EXPECT_FALSE(hook.healthy()); EXPECT_GT(queue.health().dropped,0U);
}
TEST_F(OwnerDiagnosticsTest, LaterDifferentMonitorCannotEraseOlderPendingRecovery) {
    session(1,kStart); tick(10,inputs(kStart+10*kMs));
    auto missing=inputs(kStart+20*kMs); missing.steering.reset(); tick(20,missing);
    port.now=kStart+40*kMs; session(2,port.now);
    tick(80,inputs(kStart+80*kMs,2),false); // A distinct real deadline fault in INIT2.
    ASSERT_EQ(ledger.records().size(),2U);
    port.now=kStart+90*kMs; session(3,port.now); tick(100,inputs(kStart+100*kMs,3));
    for(const auto& d:ledger.records()) {
        EXPECT_EQ(d.condition,diagnostics::Condition::Passed); EXPECT_FALSE(d.cleared); EXPECT_EQ(d.count,1U);
    }
    EXPECT_TRUE(ledger.complete());
}
} // namespace
