#include "m4_async_runtime.hpp"
#include "m4_owner_network.hpp"

#include <gtest/gtest.h>
#include <cstdlib>
#include <cmath>
#include <limits>

namespace {
using namespace stratadrive::simulation;
M4Result run(M4Scenario scenario,bool wall=false) {
    M4Config c; c.scenario=scenario; c.wall_time=wall;
    c.transport_trace=std::getenv("STRATADRIVE_M4_TRANSPORT_TRACE")!=nullptr;
    if(scenario==M4Scenario::NormalStop) c.duration_ns=3000000000;
    if(scenario==M4Scenario::Rejoin) c.duration_ns=4200000000;
    if(scenario==M4Scenario::OldEpoch) c.first_epoch=3;
    const auto result=run_m4_async(c);
    if(const auto* directory=std::getenv("STRATADRIVE_M4_RESULTS")) write_m4_result(c,result,directory);
    EXPECT_TRUE(result.passed)<<result.reason;
    for(const auto& row:result.trace) {
        if(row.protected_all) { EXPECT_FALSE(row.run_gate)<<"elapsed="<<row.elapsed_ns<<" epoch="<<row.epoch; }
    }
    return result;
}
TEST(M4AsyncRuntime, NormalUsesRealBmsAndFeedbackBeforeActuation) {
    const auto r=run(M4Scenario::Normal); ASSERT_FALSE(r.trace.empty());
    const auto& end=r.trace.back(); EXPECT_TRUE(end.run_gate); EXPECT_TRUE(end.normal_armed); EXPECT_EQ(end.coordinator_fault,0);
    EXPECT_NEAR(end.angle_rad,std::atan(2.7*.02),.001); EXPECT_LT(end.pressure_pa,1); EXPECT_GT(end.torque_nm,50);
    EXPECT_GT(end.bus_v,395); EXPECT_LT(end.soc,.63); EXPECT_GT(end.soc,.6299);
    for(const auto& row:r.trace) if(!row.normal_armed && row.elapsed_ns<r.first_active_ns) {
        EXPECT_DOUBLE_EQ(row.angle_rad,.1); EXPECT_DOUBLE_EQ(row.pressure_pa,200000); EXPECT_DOUBLE_EQ(row.torque_nm,0);
    }
}
TEST(M4AsyncRuntime, NormalStopWaitsForLeafHandoffThenActualHvOff) {
    const auto r=run(M4Scenario::NormalStop); ASSERT_FALSE(r.trace.empty());
    EXPECT_LT(r.trace.back().bus_v,30); EXPECT_LT(std::abs(r.trace.back().torque_nm),.1); EXPECT_GE(r.trace.back().pressure_pa,100000);
}
TEST(M4AsyncRuntime, PartialFrontWritePreventsRearBatchAndProtectsAllDomains) {
    const auto r=run(M4Scenario::PartialFront);
    EXPECT_EQ(r.front_frames,2*r.rear_frames+1); EXPECT_EQ(r.completed_batches,r.rear_frames);
}
TEST(M4AsyncRuntime, FeedbackLossCannotBeHiddenByLiveZoneHeartbeat) {
    const auto r=run(M4Scenario::FeedbackLoss); ASSERT_FALSE(r.trace.empty());
    EXPECT_LT(std::abs(r.trace.back().torque_nm),.1); EXPECT_GE(r.trace.back().pressure_pa,1000000);
    for(const auto& row:r.trace) {
        if(row.elapsed_ns>=r.first_fault_ns) { EXPECT_FALSE(row.run_gate); }
    }
}
TEST(M4AsyncRuntime, LostVehicleRootDoesNotGetRenewedByPowerTraffic) { run(M4Scenario::CommandLoss); }
TEST(M4AsyncRuntime, PartialArmNeverEmitsNormalActuatorFrames) { run(M4Scenario::PartialArm); }
TEST(M4AsyncRuntime, ExplicitNewEpochRejoinKeepsPhysicalStateAndRestoresReadiness) {
    const auto r=run(M4Scenario::Rejoin); EXPECT_GT(r.rejoin_active_ns,2300000000U); ASSERT_FALSE(r.trace.empty());
    EXPECT_EQ(r.trace.back().epoch,2U); EXPECT_TRUE(r.trace.back().normal_armed); EXPECT_LT(r.trace.back().soc,.63);
}
TEST(M4AsyncRuntime, PreviousEpochWorkCannotDisturbCurrentNormalSession) { run(M4Scenario::OldEpoch); }
TEST(M4AsyncRuntime, PersistedGrantValueDoesNotChangePartialWriteProtection) {
    M4Config config; config.scenario=M4Scenario::PartialFront; config.first_epoch=17; config.rejoin_epoch=18;
    const auto result=run_m4_async(config); EXPECT_TRUE(result.passed)<<result.reason;
    EXPECT_GE(result.first_fault_ns,config.injection_ns); EXPECT_LE(result.all_protected_ns,config.injection_ns+100000000);
}
TEST(M4AsyncWall, IndependentOwnersRunActualNormalPath) {
    const auto r=run(M4Scenario::Normal,true); ASSERT_FALSE(r.trace.empty());
    EXPECT_NEAR(r.trace.back().angle_rad,std::atan(2.7*.02),.001); EXPECT_LT(r.trace.back().pressure_pa,1); EXPECT_GT(r.trace.back().torque_nm,50);
}
TEST(M4AsyncWall, IndependentFeedbackLossHasMeasuredProtectionResponse) { run(M4Scenario::FeedbackLoss,true); }
TEST(M4AsyncRuntime, TransportTraceCorrelatesOriginalAuthorityWithoutChangingPhysicalResponse) {
    M4Config c;const auto original=run_m4_async(c);c.transport_trace=true;const auto traced=run_m4_async(c);
    ASSERT_TRUE(original.passed);ASSERT_TRUE(traced.passed)<<traced.reason;EXPECT_FALSE(traced.event_overflow);
    ASSERT_EQ(original.trace.size(),traced.trace.size());
    for(std::size_t i=0;i<original.trace.size();++i) {
        const auto& a=original.trace[i];const auto& b=traced.trace[i];
        EXPECT_EQ(a.run_gate,b.run_gate);EXPECT_EQ(a.normal_armed,b.normal_armed);EXPECT_EQ(a.coordinator_fault,b.coordinator_fault);
        EXPECT_DOUBLE_EQ(a.angle_rad,b.angle_rad);EXPECT_DOUBLE_EQ(a.pressure_pa,b.pressure_pa);EXPECT_DOUBLE_EQ(a.torque_nm,b.torque_nm);
        EXPECT_DOUBLE_EQ(a.bus_v,b.bus_v);EXPECT_DOUBLE_EQ(a.soc,b.soc);EXPECT_EQ(a.model_sequence,b.model_sequence);
    }
    std::size_t checked=0;
    for(const auto& sent:traced.transport_events) {
        if(std::string(sent.stage)!="central-enqueued" || sent.operation!=3)continue;
        bool received=false,dispatched=false,completed=false,returned=false;
        for(const auto& e:traced.transport_events)if(e.epoch==sent.epoch && e.token==sent.token) {
            EXPECT_EQ(e.sent_ns,sent.sent_ns);EXPECT_EQ(e.original_source_ns,sent.original_source_ns);
            EXPECT_EQ(e.inner_deadline_ns,sent.inner_deadline_ns);EXPECT_EQ(e.deadline_ns,sent.deadline_ns);
            if(std::string(e.stage)=="zone-received")received=true;
            if(std::string(e.stage)=="zone-leaf-enqueued")dispatched=true;
            if(std::string(e.stage)=="leaf-completed") {completed=true;EXPECT_EQ(e.outcome,1);EXPECT_GT(e.payload_source_ns,0U);}
            if(std::string(e.stage)=="central-result-accepted") {returned=true;EXPECT_LT(e.time_ns,e.deadline_ns);EXPECT_LE(e.result_source_ns,e.time_ns);}
        }
        EXPECT_TRUE(received);EXPECT_TRUE(dispatched);EXPECT_TRUE(completed);EXPECT_TRUE(returned);++checked;
    }
    EXPECT_GT(checked,20U);
}
M4Result delayed_results(std::uint64_t front_delay,std::uint64_t rear_delay,const char* name,
    std::uint64_t delay_end=std::numeric_limits<std::uint64_t>::max(),M4Config config={}) {
    class ResultDelay final : public stratadrive::session::MailboxDelivery<stratadrive::transport::TxResult> {
    public:
        m4_detail::Network& network;std::uint64_t delay,end;
        ResultDelay(m4_detail::Network& n,std::uint64_t d,std::uint64_t e):network(n),delay(d),end(e) {}
        stratadrive::session::Delivery send(const stratadrive::transport::TxResult& r) noexcept override {
            const auto now=network.clock.now_ns();
            return {false,r.operation==stratadrive::transport::Operation::Commands && now>=network.start+1000000000 && now-network.start<end?now+delay:0};
        }
        bool blocked() noexcept override {return false;}
        std::uint64_t now_ns() const noexcept override {return network.clock.now_ns();}
        void delivered(const stratadrive::transport::TxResult&) noexcept override {}
        void overflow(const stratadrive::transport::TxResult&) noexcept override {}
    };
    config.transport_trace=true;
    auto network=std::make_unique<m4_detail::Network>(config);ResultDelay front(*network,front_delay,delay_end),rear(*network,rear_delay,delay_end);
    network->zones[0].results.delivery(&front);network->zones[1].results.delivery(&rear);
    m4_detail::execute_logical(*network);const auto result=network->finish();
    if(const auto* dir=std::getenv("STRATADRIVE_M4_RESULTS"))write_m4_result(config,result,std::string(dir)+"/delivery-causal/"+name);
    return result;
}
TEST(M4AsyncRuntime, DelayedFrontResultCannotOutlivePreviousRearCommandAuthority) {
    const auto control=delayed_results(0,0,"control");ASSERT_TRUE(control.passed);
    const auto result=delayed_results(12000000,12000000,"both-12ms");
    EXPECT_FALSE(result.passed);EXPECT_FALSE(result.event_overflow);
    EXPECT_NE(result.reason.find("core=12 "),std::string::npos); // Transport, not an assumed busy-submit cause
    const auto expired=std::find_if(result.events.begin(),result.events.end(),[](const auto& e){return e.owner==4 && std::string(e.kind)=="command-expired";});
    ASSERT_NE(expired,result.events.end());EXPECT_GE(expired->time_ns,expired->deadline_ns);EXPECT_LE(expired->time_ns-expired->deadline_ns,200000U);
    const auto blocked=std::find_if(result.transport_events.begin(),result.transport_events.end(),[](const auto& e){return std::string(e.stage)=="central-post-rejected" && e.peer==1;});
    ASSERT_NE(blocked,result.transport_events.end());EXPECT_EQ(blocked->outcome,2);EXPECT_GT(blocked->time_ns,expired->time_ns);
    EXPECT_LT(blocked->time_ns,blocked->inner_deadline_ns); // new command live; old applied authority already expired
    for(const auto& row:result.trace)if(row.elapsed_ns>=result.first_fault_ns) {EXPECT_FALSE(row.run_gate);}
}
TEST(M4AsyncRuntime, LivePendingBatchDefersAllocationUntilResultWithoutRenewingAuthority) {
    const auto result=delayed_results(200000,19600000,"live-pending",1020000000);
    EXPECT_TRUE(result.passed)<<result.reason;EXPECT_FALSE(result.event_overflow);
    const auto pending=std::find_if(result.transport_events.begin(),result.transport_events.end(),[](const auto& e){return std::string(e.stage)=="allocation-deferred";});
    ASSERT_NE(pending,result.transport_events.end());
    EXPECT_LT(pending->time_ns,pending->deadline_ns);EXPECT_LT(pending->time_ns,pending->inner_deadline_ns);
    const auto completed=std::find_if(pending,result.transport_events.end(),[&](const auto& e){
        return e.epoch==pending->epoch && e.token==pending->token && std::string(e.stage)=="central-result-accepted";
    });
    ASSERT_NE(completed,result.transport_events.end());EXPECT_LT(completed->time_ns,completed->deadline_ns);
    EXPECT_EQ(completed->deadline_ns,pending->deadline_ns);EXPECT_EQ(completed->sent_ns,pending->sent_ns);
    const auto output=std::find_if(result.transport_events.begin(),completed,[&](const auto& e){
        return e.epoch==pending->epoch && e.token==pending->token && e.owner==4 &&
            std::string(e.stage)=="leaf-output-published" && e.outcome==1;
    });
    ASSERT_NE(output,completed);EXPECT_LT(output->time_ns,output->inner_deadline_ns);
    const auto resumed=std::find_if(completed,result.transport_events.end(),[](const auto& e){
        return std::string(e.stage)=="central-enqueued" && e.operation==static_cast<int>(stratadrive::transport::Operation::Commands);
    });
    ASSERT_NE(resumed,result.transport_events.end());
    EXPECT_GE(resumed->time_ns,completed->time_ns);EXPECT_GT(resumed->payload_source_ns,pending->payload_source_ns);
    EXPECT_GT(resumed->original_source_ns,pending->original_source_ns);
    const auto next=std::find_if(std::next(resumed),result.transport_events.end(),[](const auto& e){
        return std::string(e.stage)=="central-enqueued" && e.peer==0 && e.operation==static_cast<int>(stratadrive::transport::Operation::Commands);
    });
    ASSERT_NE(next,result.transport_events.end());
    EXPECT_EQ(next->original_source_ns-resumed->original_source_ns,20000000U);
    EXPECT_LT(next->time_ns-resumed->time_ns,20000000U); // resume does not move the nominal release grid
    EXPECT_EQ(result.first_fault_ns,0U);
}
TEST(M4AsyncRuntime, SustainedPendingCannotHideEventualAuthorityExpiry) {
    const auto result=delayed_results(200000,19600000,"sustained-pending");
    EXPECT_FALSE(result.passed);EXPECT_FALSE(result.event_overflow);
    EXPECT_GT(result.first_fault_ns,1500000000U);
    EXPECT_NE(result.reason.find("core=12 "),std::string::npos);
    EXPECT_TRUE(std::any_of(result.transport_events.begin(),result.transport_events.end(),[](const auto& e){return std::string(e.stage)=="allocation-deferred";}));
    EXPECT_FALSE(std::any_of(result.transport_events.begin(),result.transport_events.end(),[](const auto& e){return std::string(e.stage)=="command-submit-rejected";}));
    const auto expired=std::find_if(result.events.begin(),result.events.end(),[](const auto& e){return e.owner==4 && std::string(e.kind)=="command-expired";});
    ASSERT_NE(expired,result.events.end());EXPECT_GE(expired->time_ns,expired->deadline_ns);
    EXPECT_LT(expired->time_ns-1000000000U,result.first_fault_ns); // local expiry precedes Central observation
    for(const auto& row:result.trace)if(row.elapsed_ns>=result.first_fault_ns) {EXPECT_FALSE(row.run_gate);}
}
TEST(M4AsyncRuntime, MissingPendingResultStillTimesOutAtOriginalEnvelope) {
    const auto result=delayed_results(0,21000000,"pending-timeout");
    EXPECT_FALSE(result.passed);EXPECT_FALSE(result.event_overflow);
    const auto timeout=std::find_if(result.transport_events.begin(),result.transport_events.end(),[](const auto& e){return std::string(e.stage)=="central-result-timeout";});
    ASSERT_NE(timeout,result.transport_events.end());EXPECT_EQ(timeout->time_ns,timeout->deadline_ns);
    EXPECT_LT(timeout->time_ns,timeout->inner_deadline_ns);
    EXPECT_GE(result.first_fault_ns,timeout->time_ns-1000000000U);
    EXPECT_LE(result.all_protected_ns-result.first_fault_ns,100000000U);
}
TEST(M4AsyncRuntime, DeferredBatchCompletesBeforeNormalStopHandoff) {
    M4Config config;config.scenario=M4Scenario::NormalStop;config.duration_ns=3000000000;config.injection_ns=1020000000;
    const auto result=delayed_results(200000,19600000,"pending-stop",1020000000,config);
    EXPECT_TRUE(result.passed)<<result.reason;EXPECT_FALSE(result.event_overflow);
    EXPECT_EQ(result.first_fault_ns,0U);EXPECT_GT(result.completed_batches,0U);
}
TEST(M4AsyncRuntime, PendingRearResultSelectsCommandDeliveryBeforeIndividualExpiry) {
    // Historical reproducer name retained. Pending alone no longer selects
    // CommandDelivery: this19.8ms delay arrives exactly at exclusive expiry.
    const auto result=delayed_results(0,19800000,"rear-19p8ms");
    EXPECT_FALSE(result.passed);EXPECT_FALSE(result.event_overflow);
    EXPECT_NE(result.reason.find("core=12 "),std::string::npos);
    EXPECT_GT(result.first_active_ns,0U);EXPECT_GE(result.first_fault_ns,1000000000U);
    const auto pending=std::find_if(result.transport_events.begin(),result.transport_events.end(),[](const auto& e){return std::string(e.stage)=="allocation-deferred";});
    ASSERT_NE(pending,result.transport_events.end());EXPECT_LT(pending->time_ns,pending->deadline_ns);EXPECT_LT(pending->time_ns,pending->inner_deadline_ns);
    EXPECT_FALSE(std::any_of(result.transport_events.begin(),pending,[](const auto& e){return std::string(e.stage)=="central-result-timeout" || std::string(e.stage)=="central-result-rejected" || std::string(e.stage)=="central-post-rejected";}));
    EXPECT_TRUE(std::any_of(result.transport_events.begin(),pending,[&](const auto& e){return e.epoch==pending->epoch && e.token==pending->token && std::string(e.stage)=="zone-result-enqueued" && e.outcome==1;}));
    const auto rejected=std::find_if(pending,result.transport_events.end(),[&](const auto& e){
        return e.epoch==pending->epoch && e.token==pending->token && std::string(e.stage)=="central-result-rejected";
    });
    ASSERT_NE(rejected,result.transport_events.end());
    EXPECT_EQ(rejected->time_ns,pending->deadline_ns);EXPECT_EQ(rejected->deadline_ns,pending->deadline_ns);
    EXPECT_GE(result.first_fault_ns,rejected->time_ns-1000000000U);
    EXPECT_FALSE(std::any_of(result.transport_events.begin(),rejected,[](const auto& e){return std::string(e.stage)=="command-submit-rejected";}));
    for(const auto& row:result.trace)if(row.elapsed_ns>=result.first_fault_ns) {EXPECT_FALSE(row.run_gate);}
    EXPECT_GT(result.all_protected_ns,result.first_fault_ns);EXPECT_LE(result.all_protected_ns-result.first_fault_ns,100000000U);
}

// Phase replay: genuine 500 us plant acquisitions (offset 430,396 ns).
// From 1 s, Front feedback becomes visible after 6 ms,
// still within the original 20 ms transport envelope. No payload restamping.
M4Result renewal_phase_replay(M4Config config,const char* name) {
    class FeedbackDelay final : public stratadrive::session::MailboxDelivery<stratadrive::transport::Feedback> {
    public:
        m4_detail::Network& n;
        explicit FeedbackDelay(m4_detail::Network& network):n(network) {}
        stratadrive::session::Delivery send(const stratadrive::transport::Feedback&) noexcept override {
            const auto now=n.clock.now_ns();
            return {false,now-n.start>=1000000000?now+6000000:0};
        }
        bool blocked() noexcept override {return false;}
        std::uint64_t now_ns() const noexcept override {return n.clock.now_ns();}
        void delivered(const stratadrive::transport::Feedback&) noexcept override {}
        void overflow(const stratadrive::transport::Feedback&) noexcept override {}
    };
    config.transport_trace=true;
    auto n=std::make_unique<m4_detail::Network>(config);FeedbackDelay feedback(*n);
    n->zones[0].feedback.delivery(&feedback);
    std::uint64_t plant=0,owner=0;
    while(std::min(plant,owner)<=config.duration_ns) {
        if(plant<=owner) {n->clock.logical=n->start+plant;n->step(8);plant=plant==0?430396:plant+500000;}
        else {n->clock.logical=n->start+owner;for(unsigned i=0;i<8;++i)n->step(i);owner+=200000;}
    }
    auto result=n->finish();
    if(const auto* dir=std::getenv("STRATADRIVE_M4_RESULTS"))write_m4_result(config,result,std::string(dir)+"/renewal/"+name);
    return result;
}
TEST(M4RefreshDelivery, ObservedPhaseMustRenewActualLeavesBeforeOriginalExpiry) {
    M4Config config;config.renewal=stratadrive::central::CommandRenewal::Host10ms;
    const auto result=renewal_phase_replay(config,"host10");
    EXPECT_TRUE(result.passed)<<result.reason;
    EXPECT_EQ(result.first_fault_ns,0U);
    ASSERT_FALSE(result.event_overflow);
    std::array<std::uint64_t,3> expiry{};std::array<unsigned,3> renewals{};
    for(const auto& e:result.events)if(e.owner>=2 && e.owner<=4 && std::string(e.kind)=="valid-input" && e.code==1) {
        const auto i=e.owner-2;
        if(expiry[i]) {EXPECT_LT(e.time_ns,expiry[i]);++renewals[i];}
        expiry[i]=e.deadline_ns;
    }
    for(auto count:renewals)EXPECT_GT(count,50U);
}

TEST(M4RefreshDelivery, LegacyPhaseReproducesShortSupportThenActualExpiry) {
    const auto r=renewal_phase_replay({},"legacy20");
    EXPECT_FALSE(r.passed);EXPECT_FALSE(r.event_overflow);
    const auto defer=std::find_if(r.transport_events.begin(),r.transport_events.end(),[](const auto& e){return std::string(e.stage)=="allocation-readiness" && e.outcome==3;});
    ASSERT_NE(defer,r.transport_events.end());
    EXPECT_EQ(defer->sent_ns+20000000-defer->inner_deadline_ns,169603U);
    EXPECT_GT(defer->deadline_ns,defer->time_ns); // old command still live at first short-support branch
    const auto limit=std::find_if(r.transport_events.begin(),r.transport_events.end(),[&](const auto& e){return std::string(e.stage)=="permission-limit" && e.inner_deadline_ns==defer->inner_deadline_ns;});
    ASSERT_NE(limit,r.transport_events.end());EXPECT_EQ(limit->outcome,static_cast<int>(stratadrive::central::PermissionLimit::SteeringActual));
    EXPECT_EQ(limit->inner_deadline_ns,limit->original_source_ns+30000001);
    for(unsigned owner=2;owner<=4;++owner) {
        const auto expired=std::find_if(r.events.begin(),r.events.end(),[&](const auto& e){return e.owner==owner && std::string(e.kind)=="command-expired";});
        ASSERT_NE(expired,r.events.end());EXPECT_EQ(expired->deadline_ns,defer->deadline_ns);EXPECT_GE(expired->time_ns,expired->deadline_ns);
    }
    EXPECT_GT(r.all_protected_ns,r.first_fault_ns);EXPECT_LE(r.all_protected_ns-r.first_fault_ns,100000000U);
}
TEST(M4RefreshDelivery, InterruptedHostRenewalStillExpiresOriginalAuthority) {
    M4Config c;c.renewal=stratadrive::central::CommandRenewal::Host10ms;c.scenario=M4Scenario::CommandLoss;
    const auto r=renewal_phase_replay(c,"host10-command-loss");
    EXPECT_TRUE(r.passed)<<r.reason;EXPECT_FALSE(r.event_overflow);
    EXPECT_GE(r.first_fault_ns,c.injection_ns);EXPECT_LE(r.all_protected_ns-r.first_fault_ns,100000000U);
    EXPECT_TRUE(std::any_of(r.events.begin(),r.events.end(),[](const auto& e){return std::string(e.kind)=="command-expired" && e.time_ns>=e.deadline_ns;}));
}
TEST(M4RefreshDelivery, Host10NormalStopUsesRealHandoffAndHvOff) {
    M4Config c;c.renewal=stratadrive::central::CommandRenewal::Host10ms;
    c.scenario=M4Scenario::NormalStop;c.duration_ns=3000000000;
    const auto r=run_m4_async(c);
    ASSERT_TRUE(r.passed)<<r.reason;EXPECT_EQ(r.first_fault_ns,0U);
    ASSERT_FALSE(r.trace.empty());EXPECT_LT(r.trace.back().bus_v,30);
    EXPECT_LT(std::abs(r.trace.back().torque_nm),.1);EXPECT_GE(r.trace.back().pressure_pa,100000);
}
}  // namespace
