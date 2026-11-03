#include "native_diagnostics.hpp"
#include "command_gateway.hpp"
#include "bms_controller.hpp"
#include "power_controller.hpp"
#include "power_model.hpp"
#include "multirate_fixture.hpp"
#include <gtest/gtest.h>

namespace {
using namespace stratadrive;
constexpr std::uint64_t ms=1000000,start=1000000000,run=4001;
class Capture {
public:
    diagnostics::EventQueue q{run,30};
    diagnostics::NativeDiagnostics hook;
    diagnostics::Ledger ledger;
    explicit Capture(diagnostics::Component c):hook(q,{run,30,diagnostics::Domain::Simulation,run,1},c) {}
    void session(unsigned epoch,std::uint64_t enable) {
        ASSERT_TRUE(hook.start_session(epoch,enable)); diagnostics::Event e;
        e.id={run,7,epoch}; e.session={run,epoch}; e.kind=diagnostics::Kind::Session;
        e.session_enable={diagnostics::Domain::Simulation,run,enable,true,true}; ASSERT_EQ(ledger.record(e),diagnostics::Result::Accepted);
    }
    void drain() { diagnostics::Event e; while(q.pop(e)) { ASSERT_EQ(ledger.record(e),diagnostics::Result::Accepted); } }
};
void reject_invalid_input_proofs(diagnostics::Component actor,diagnostics::NativeMonitor monitor,
    const NativeObservation& first,const NativeObservation& good,std::uint64_t now) {
    for(unsigned variant=0;variant<8;++variant) {
        Capture c(actor); c.session(first.epoch,first.enable_ns);
        c.hook.observe(monitor,first,std::nullopt,std::nullopt,false,false,first.observed_ns); c.drain();
        c.session(good.epoch,good.enable_ns); auto bad=good; bool healthy=true,gate=true; auto observed=now;
        switch(variant) {
        case 0:gate=false;break;
        case 1:healthy=false;break;
        case 2:bad.epoch=first.epoch;break;
        case 3:++bad.enable_ns;break;
        case 4:bad.samples[0].present=false;break;
        case 5:bad.samples[0].dependency_ns=now-71*ms;break;
        case 6:observed=bad.observed_ns+bad.timing[1]+1;break;
        case 7:bad.qualified=false;break;
        }
        c.hook.observe(monitor,std::nullopt,std::nullopt,bad,healthy,gate,observed); c.drain();
        ASSERT_EQ(c.ledger.records().size(),1U); EXPECT_EQ(c.ledger.records()[0].condition,diagnostics::Condition::Unknown)<<variant;
        c.hook.observe(monitor,std::nullopt,std::nullopt,good,true,true,now); c.drain();
        EXPECT_EQ(c.ledger.records()[0].condition,diagnostics::Condition::Passed)<<variant;
    }
}
class GatewayPort final : public zone::GatewayPort {
public:
    std::uint64_t now{start}; unsigned attempt{0},fail_at{2},protection{0};
    std::uint64_t now_ns() noexcept override { return now; }
    bool send(const zone::CommandFrame&,const central::CommandContext&) noexcept override { return ++attempt!=fail_at; }
    bool protect(zone::ZoneScope,zone::ProtectionCause,std::uint64_t) noexcept override { ++protection; return true; }
};
central::AllocatedCommands command(unsigned epoch,unsigned seq,std::uint64_t now) {
    central::AllocatedCommands c; c.parent={epoch,seq,now,now+60*ms}; c.oldest_input_time_ns=now; c.expires_at_ns=now+30*ms;
    c.steering.epoch=epoch; c.steering.sequence=seq; c.steering.source_time_ns=now; c.steering.causal_sequence=seq;
    c.steering.local_state=can::SteeringLocalState::Normal; c.steering.origin=can::SteeringOrigin::NormalPath; c.steering.angle_rad=0;
    static_cast<can::ActuatorMetadata&>(c.brake)={seq,epoch,now,seq,can::ActuatorLocalState::Normal,can::ActuatorOrigin::NormalPath}; c.brake.pressure_pa=0;
    return c;
}
TEST(NativeDiagnostics, PartialGatewayWriteRetainsFirstCauseAndRequiresNewActualCompleteDispatch) {
    GatewayPort port; zone::CommandGateway g{zone::ZoneScope::Front,port}; Capture capture(diagnostics::Component::Front);
    ASSERT_TRUE(g.start_session(1,start)); ASSERT_TRUE(g.arm()); capture.session(1,start);
    port.now+=20*ms; auto c=command(1,0,port.now);
    ASSERT_EQ(g.authorize_request(c.parent),zone::AdmissionResult::Accepted); ASSERT_EQ(g.enqueue(central::front_commands(c)),zone::AdmissionResult::Accepted);
    EXPECT_TRUE(g.dispatch().partial_front); ASSERT_TRUE(g.fault_observation()); const auto first=*g.fault_observation();
    EXPECT_EQ(first.reason,static_cast<unsigned>(zone::ProtectionCause::SendFailure)); EXPECT_EQ(first.writes,1U); ASSERT_TRUE(first.root);
    EXPECT_EQ(first.root->expiry_ns,c.expires_at_ns); EXPECT_EQ(port.protection,1U);
    capture.hook.observe(diagnostics::NativeMonitor::CommandGateway,g.fault_observation(),std::nullopt,g.success_observation(),false,false,port.now); capture.drain();
    ASSERT_EQ(capture.ledger.records().size(),1U); const auto key=capture.ledger.records()[0].key; EXPECT_EQ(key.code,diagnostics::Code::Gateway);
    port.fail_at=0; port.now+=10*ms; g.poll(); EXPECT_EQ(g.dispatch().frames_enqueued,0U);
    EXPECT_EQ(g.fault_observation()->observed_ns,first.observed_ns);
    port.now+=10*ms; ASSERT_TRUE(g.start_session(2,port.now)); ASSERT_TRUE(g.arm()); capture.session(2,port.now);
    capture.hook.observe(diagnostics::NativeMonitor::CommandGateway,g.fault_observation(),std::nullopt,g.success_observation(),true,true,port.now); capture.drain();
    EXPECT_EQ(capture.ledger.find(key)->condition,diagnostics::Condition::Unknown);
    port.now+=10*ms; c=command(2,0,port.now); ASSERT_EQ(g.authorize_request(c.parent),zone::AdmissionResult::Accepted);
    ASSERT_EQ(g.enqueue(central::front_commands(c)),zone::AdmissionResult::Accepted); EXPECT_EQ(g.dispatch().frames_enqueued,2U);
    // Mutate copies of real accepted evidence; each rejected proof is followed by the original.
    for(unsigned variant=0;variant<10;++variant) {
        Capture test(diagnostics::Component::Front); test.session(1,start);
        test.hook.observe(diagnostics::NativeMonitor::CommandGateway,first,std::nullopt,std::nullopt,false,false,first.observed_ns); test.drain();
        test.session(2,g.success_observation()->enable_ns);
        auto bad=g.success_observation(); bool healthy=true,gate=true; auto now=port.now;
        switch(variant) {
        case 0:gate=false;break;
        case 1:healthy=false;break;
        case 2:bad.reset();break;
        case 3:bad->epoch=1;break;
        case 4:++bad->enable_ns;break;
        case 5:bad->root->expiry_ns=now;break;
        case 6:bad->root->dependency_ns=now-71*ms;break;
        case 7:now=bad->observed_ns+31*ms;break;
        case 8:bad->qualified=false;break;
        case 9:bad->root.reset();break;
        }
        test.hook.observe(diagnostics::NativeMonitor::CommandGateway,std::nullopt,std::nullopt,bad,healthy,gate,now); test.drain();
        EXPECT_EQ(test.ledger.records()[0].condition,diagnostics::Condition::Unknown)<<variant;
        test.hook.observe(diagnostics::NativeMonitor::CommandGateway,std::nullopt,std::nullopt,g.success_observation(),true,true,port.now); test.drain();
        EXPECT_EQ(test.ledger.records()[0].condition,diagnostics::Condition::Passed)<<variant;
    }
    capture.hook.observe(diagnostics::NativeMonitor::CommandGateway,g.fault_observation(),std::nullopt,g.success_observation(),true,false,port.now); capture.drain();
    EXPECT_EQ(capture.ledger.find(key)->condition,diagnostics::Condition::Unknown);
    capture.hook.observe(diagnostics::NativeMonitor::CommandGateway,g.fault_observation(),std::nullopt,g.success_observation(),true,true,port.now); capture.drain();
    EXPECT_EQ(capture.ledger.find(key)->condition,diagnostics::Condition::Passed); EXPECT_FALSE(capture.ledger.find(key)->cleared);
}
battery::SensorSnapshot battery_sample(std::uint64_t now) {
    const battery::ModelIdentity id{7,static_cast<unsigned>((now-start)/ms),now};
    return {id,true,battery::ModelMeasurement<double>{.5,id,now},battery::ModelMeasurement<battery::ElectricalPair>{{400,0},id,now},
        battery::ModelMeasurement<double>{25,id,now},battery::ModelMeasurement<battery::CellExtrema>{{3.99,4.01},id,now},
        battery::ModelMeasurement<battery::CellExtrema>{{24,26},id,now}};
}
TEST(NativeDiagnostics, ActualBmsTripRetainsRawThresholdDwellAndRecoveryReadyNeverClearsLatch) {
    vecu::BmsController b{simulation::multirate_fixture::bms_config()}; Capture c(diagnostics::Component::Bms);
    ASSERT_TRUE(b.start_session(1,7,start)); c.session(1,start);
    for(unsigned t=0;t<=100;t+=20) ASSERT_TRUE(b.tick(battery_sample(start+t*ms),start+t*ms));
    ASSERT_EQ(b.decision().state,vecu::BmsControlState::Active);
    for(unsigned t=120;t<=160;t+=20) { auto s=battery_sample(start+t*ms); s.cell_voltage->value.maximum=4.3; ASSERT_TRUE(b.tick(s,start+t*ms)); }
    ASSERT_TRUE(b.fault_observation()); const auto first=*b.fault_observation();
    EXPECT_EQ(first.detail,vecu::CellOverVoltage); EXPECT_EQ(first.violation_ns,start+120*ms); EXPECT_EQ(first.observed_ns,start+160*ms);
    EXPECT_EQ(first.trip[1],4.25); EXPECT_EQ(first.timing[4],40*ms); EXPECT_EQ(first.samples[3].values[1],4.3);
    c.hook.observe(diagnostics::NativeMonitor::Bms,b.fault_observation(),b.propagation_observation(),b.success_observation(),false,true,start+160*ms); c.drain();
    ASSERT_EQ(c.ledger.records().size(),1U); const auto key=c.ledger.records()[0].key; EXPECT_EQ(key.code,diagnostics::Code::BmsLocal);
    for(unsigned t=180;t<=300;t+=20) ASSERT_TRUE(b.tick(battery_sample(start+t*ms),start+t*ms));
    EXPECT_TRUE(b.decision().recovery_ready); EXPECT_EQ(b.decision().state,vecu::BmsControlState::Latched);
    c.hook.observe(diagnostics::NativeMonitor::Bms,b.fault_observation(),b.propagation_observation(),b.success_observation(),false,true,start+300*ms); c.drain();
    EXPECT_EQ(c.ledger.find(key)->condition,diagnostics::Condition::Failed);
    ASSERT_TRUE(b.start_session(2,7,start+320*ms)); c.session(2,start+320*ms);
    for(unsigned t=320;t<=420;t+=20) {
        ASSERT_TRUE(b.tick(battery_sample(start+t*ms),start+t*ms));
        c.hook.observe(diagnostics::NativeMonitor::Bms,b.fault_observation(),b.propagation_observation(),b.success_observation(),b.decision().state==vecu::BmsControlState::Active,true,start+t*ms); c.drain();
        if(t<420) { EXPECT_EQ(c.ledger.find(key)->condition,diagnostics::Condition::Unknown); }
    }
    EXPECT_EQ(c.ledger.find(key)->condition,diagnostics::Condition::Passed); EXPECT_EQ(c.ledger.find(key)->count,1U);
    ASSERT_TRUE(b.success_observation()); reject_invalid_input_proofs(diagnostics::Component::Bms,diagnostics::NativeMonitor::Bms,first,*b.success_observation(),start+420*ms);
}
TEST(NativeDiagnostics, PropagatedBmsProtectionDoesNotMaskLaterRealTrip) {
    vecu::BmsController b{simulation::multirate_fixture::bms_config()}; Capture c(diagnostics::Component::Bms);
    ASSERT_TRUE(b.start_session(1,7,start)); c.session(1,start);
    for(unsigned t=0;t<=100;t+=20) ASSERT_TRUE(b.tick(battery_sample(start+t*ms),start+t*ms));
    b.request_local_protection(start+110*ms);
    c.hook.observe(diagnostics::NativeMonitor::Bms,b.fault_observation(),b.propagation_observation(),b.success_observation(),false,false,start+110*ms); c.drain();
    EXPECT_TRUE(c.ledger.records().empty()); ASSERT_TRUE(b.propagation_observation()); EXPECT_FALSE(b.fault_observation());
    for(unsigned t=120;t<=160;t+=20) { auto s=battery_sample(start+t*ms); s.cell_voltage->value.maximum=4.3; ASSERT_TRUE(b.tick(s,start+t*ms)); }
    c.hook.observe(diagnostics::NativeMonitor::Bms,b.fault_observation(),b.propagation_observation(),b.success_observation(),false,false,start+160*ms); c.drain();
    ASSERT_EQ(c.ledger.records().size(),1U); EXPECT_EQ(c.ledger.records()[0].key.code,diagnostics::Code::BmsLocal);
    EXPECT_EQ(b.propagation_observation()->observed_ns,start+110*ms); EXPECT_EQ(b.fault_observation()->observed_ns,start+160*ms);
}
class NativePower : public ::testing::Test {
protected:
    simulation::PowerModel plant{{.002,50,.02,100,1000,500}};
    vecu::PowerController p{{}}; Capture capture{diagnostics::Component::Power};
    can::BmsTxState tx{can::BmsFrameKind::PowerRequest}; unsigned epoch=1,sequence=0,index=0; bool missing=false;
    void SetUp() override { ASSERT_TRUE(plant.initialize({7,0,start},0)); ASSERT_TRUE(p.start_session(1,7,start)); capture.session(1,start); }
    void step() {
        const auto begin=start+index*10*ms,now=begin+10*ms;
        const simulation::PowerEnvironment env{400,0,true,true,true,false,false};
        ASSERT_EQ(plant.step({begin,now,{env,{7,index,begin},begin},p.output().coils.value_or(power::CoilCommand{})}),simulation::PowerModelFault::None);
        can::BmsMessage r; r.kind=can::BmsFrameKind::PowerRequest; r.epoch=epoch; r.sequence=sequence++; r.source_time_ns=now; r.causal_sequence=r.sequence; r.origin=can::ActuatorOrigin::NormalPath;
        r.content=can::BmsPowerRequest{can::BmsPowerAction::Enable,now+60*ms,now};
        const can::BmsParentContext parent{epoch,r.sequence,now,now+60*ms}; const auto f=can::encode_bms_frame(r,tx); ASSERT_TRUE(f);
        p.receive(*f,now,&parent); auto sensor=plant.observation(); if(missing && sensor) sensor->pack_current_a.reset();
        ASSERT_TRUE(p.tick(sensor,power::BmsSafetyGate{epoch,index,now,now,false},now));
        capture.hook.observe(diagnostics::NativeMonitor::Power,p.fault_observation(),p.propagation_observation(),p.success_observation(),p.output().fault==vecu::PowerControlFault::None && p.output().phase==vecu::PowerPhase::Ready,true,now);
        capture.drain(); ++index;
    }
};
TEST_F(NativePower, RealRcReadyAndNewSequenceAreRequiredAfterInputFailure) {
    while(p.output().phase!=vecu::PowerPhase::Ready && index<200) { ASSERT_NO_FATAL_FAILURE(step()); }
    ASSERT_EQ(p.output().phase,vecu::PowerPhase::Ready);
    const auto sequence_before=plant.diagnostic_state().identity.sequence;
    missing=true; step(); ASSERT_TRUE(p.fault_observation()); const auto first=*p.fault_observation();
    EXPECT_EQ(first.reason,static_cast<unsigned>(vecu::PowerControlFault::InputsUnavailable)); EXPECT_EQ(first.state,static_cast<unsigned>(vecu::PowerPhase::Ready));
    EXPECT_FALSE(first.samples[0].values[2]); ASSERT_EQ(capture.ledger.records().size(),1U); const auto key=capture.ledger.records()[0].key;
    missing=false; while(p.output().phase!=vecu::PowerPhase::Off && index<400) { ASSERT_NO_FATAL_FAILURE(step()); }
    ASSERT_EQ(p.output().phase,vecu::PowerPhase::Off);
    EXPECT_EQ(capture.ledger.find(key)->condition,diagnostics::Condition::Failed);
    epoch=2; sequence=0; e2e::p05_protect_init(tx.protection); const auto enable=start+index*10*ms;
    ASSERT_TRUE(p.start_session(epoch,7,enable)); capture.session(epoch,enable); EXPECT_FALSE(p.success_observation());
    step(); EXPECT_EQ(capture.ledger.find(key)->condition,diagnostics::Condition::Unknown);
    while(p.output().phase!=vecu::PowerPhase::Ready && index<600) { ASSERT_NO_FATAL_FAILURE(step()); }
    ASSERT_EQ(p.output().phase,vecu::PowerPhase::Ready);
    EXPECT_EQ(capture.ledger.find(key)->condition,diagnostics::Condition::Passed); EXPECT_FALSE(capture.ledger.find(key)->cleared);
    ASSERT_TRUE(p.success_observation()); reject_invalid_input_proofs(diagnostics::Component::Power,diagnostics::NativeMonitor::Power,first,*p.success_observation(),start+index*10*ms);
    EXPECT_GT(plant.diagnostic_state().identity.sequence,sequence_before); EXPECT_EQ(plant.diagnostic_state().identity.epoch,7U);
}
} // namespace
