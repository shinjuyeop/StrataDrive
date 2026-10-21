#include "m4_async_runtime.hpp"
#include "m4_owner_network.hpp"
#include "session_coordinator.hpp"
#include <gtest/gtest.h>
#include <algorithm>
#include <cstdlib>
#include <cmath>
#include <string_view>

namespace {
using namespace stratadrive::simulation;
bool kind(const M4Event& event,const char* name) { return std::string_view(event.kind)==name; }
class FaultClock final : public stratadrive::transport::Clock {
public: std::uint64_t now{1000000000}; std::uint64_t now_ns() noexcept override { return now; }
};
TEST(M4FaultContract, DelayedOldAckCannotContaminateNewerSessionEvenWhileItsSourceIsFresh) {
    using namespace stratadrive;
    struct Port final : session::CoordinatorPort {
        FaultClock clock;
        std::uint64_t now_ns() noexcept override { return clock.now; }
        bool quiesce_central() noexcept override { return true; }
        bool send(const session::Control&) noexcept override { return true; }
        bool commit_central(central::CoordinatorSession) noexcept override { return true; }
        void protect_central() noexcept override {}
    } port;
    session::SessionCoordinator owner{port}; ASSERT_TRUE(owner.begin(1,port.clock.now)); const auto old_plan=owner.plan();
    std::vector<M4Fault> faults{parse_m4_fault("session-ack:delay:drive:0:0:20")};
    FaultDelivery<session::Ack> adapter{port.clock,port.clock.now,faults,FaultPath::SessionAck,M4Owner::Drive};
    session::SessionMailbox<session::Ack,8> mailbox; mailbox.delivery(&adapter);
    port.clock.now+=1000000; const session::Ack old{session::Role::Drive,session::Phase::Prepare,old_plan,port.clock.now,true};
    ASSERT_TRUE(mailbox.push(old)); EXPECT_FALSE(mailbox.pop());
    port.clock.now+=1000000; owner.cancel(port.clock.now); port.clock.now+=1000000; ASSERT_TRUE(owner.begin(2,port.clock.now));
    port.clock.now=old.source_ns+20000000; const auto delivered=mailbox.pop(); ASSERT_TRUE(delivered);
    EXPECT_EQ(delivered->source_ns,old.source_ns); EXPECT_EQ(delivered->plan.epoch,1U);
    EXPECT_EQ(owner.receive(*delivered,port.clock.now),session::AckResult::Rejected);
    EXPECT_EQ(owner.plan().epoch,2U); EXPECT_EQ(owner.state(),session::State::Preparing); EXPECT_EQ(owner.fault(),session::Fault::None);
}
TEST(M4FaultContract, RealOverflowDoesNotRecoverWhenReceiveBlockingEnds) {
    using namespace stratadrive;
    FaultClock clock; std::vector<M4Fault> faults{parse_m4_fault("central-zone:overflow:front:0:10:0")};
    FaultDelivery<transport::ZoneRequest> adapter{clock,clock.now,faults,FaultPath::CentralToZone,M4Owner::Front};
    session::SessionMailbox<transport::ZoneRequest,8> mailbox; mailbox.delivery(&adapter);
    for(std::size_t i=0;i<8;++i) ASSERT_TRUE(mailbox.push({1,i,clock.now,clock.now+20000000,transport::Arm{}}));
    EXPECT_FALSE(mailbox.pop()); EXPECT_FALSE(mailbox.push({})); EXPECT_TRUE(mailbox.failed());
    clock.now+=20000000; EXPECT_FALSE(mailbox.pop()); EXPECT_FALSE(mailbox.push({2,99,clock.now,clock.now+20000000,transport::Arm{}}));
}
M4Result run(const std::string& recipe,const std::string& name,bool recover=false,bool wall=false) {
    M4Config c; c.scenario=M4Scenario::Fault; c.wall_time=wall; c.faults={parse_m4_fault(recipe)};
    if(recover) { c.recovery_ns=2300000000; c.duration_ns=4200000000; c.replace_links=true; }
    if(c.faults[0].phase==FaultPhase::Prepare) c.duration_ns=2400000000;
    if(c.faults[0].phase==FaultPhase::Stop) c.duration_ns=3000000000;
    const auto r=run_m4_async(c);
    if(const auto* base=std::getenv("STRATADRIVE_M4_RESULTS")) write_m4_result(c,r,std::string(base)+"/faults/"+name);
    EXPECT_TRUE(r.passed)<<recipe<<": "<<r.reason;
    EXPECT_EQ(r.stopped_ack_violations,0U); EXPECT_TRUE(r.gate_latched);
    return r;
}
TEST(M4FaultContract, StrictRecipeRejectsUnknownEndpointsAndAmbiguousTimes) {
    EXPECT_THROW(parse_m4_fault("owner:drop:central:1200:100:0"),std::invalid_argument);
    EXPECT_THROW(parse_m4_fault("central-zone:drop:drive:1200:100:0"),std::invalid_argument);
    EXPECT_THROW(parse_m4_fault("owner:pause:central:-1:100:0"),std::invalid_argument);
    EXPECT_THROW(parse_m4_fault("owner:pause:central:1.2:100:0"),std::invalid_argument);
}
TEST(M4FaultRuntime, CentralStopExpiresAuthorityWithoutCentralProtectionAck) {
    const auto r=run("owner:pause:central:1200:200:0","central-stop");
    EXPECT_TRUE(std::any_of(r.events.begin(),r.events.end(),[](const auto& e){return kind(e,"fault-observed") && e.owner<7;}));
    EXPECT_FALSE(r.trace.back().run_gate);
}
class M4OwnerStop : public ::testing::TestWithParam<const char*> {};
TEST_P(M4OwnerStop, SessionControlAndSelfMonitoringStopTogether) {
    const std::string target=GetParam(); const auto r=run("owner:pause:"+target+":1200:200:0",target+"-stop");
    EXPECT_GT(r.first_active_ns,0U); EXPECT_FALSE(r.trace.back().run_gate);
    bool stopped=false,resumed=false;
    for(const auto& e:r.events) { stopped=stopped || kind(e,"owner-stopped"); resumed=resumed || kind(e,"owner-resumed"); }
    EXPECT_TRUE(stopped); EXPECT_TRUE(resumed); EXPECT_LT(std::abs(r.trace.back().torque_nm),.1);
}
INSTANTIATE_TEST_SUITE_P(AllDomains,M4OwnerStop,::testing::Values("front","rear","steering","brake","drive","bms","power"));
class M4Direction : public ::testing::TestWithParam<const char*> {};
TEST_P(M4Direction, LostTransportDoesNotStopOwnerOrRefreshAuthority) {
    const std::string recipe=GetParam(); auto name=recipe; std::replace(name.begin(),name.end(),':','_');
    const auto r=run(recipe,name);
    EXPECT_FALSE(std::any_of(r.events.begin(),r.events.end(),[](const auto& e){return kind(e,"owner-stopped");}));
    EXPECT_TRUE(std::any_of(r.events.begin(),r.events.end(),[](const auto& e){return kind(e,"dropped");}));
    EXPECT_FALSE(r.trace.back().run_gate);
}
INSTANTIATE_TEST_SUITE_P(Directed,M4Direction,::testing::Values(
 "central-zone:drop:front:1200:200:0","central-zone:drop:rear:1200:200:0",
 "zone-central:drop:front:1200:200:0","zone-central:drop:rear:1200:200:0",
 "zone-leaf:drop:steering:1200:200:0","zone-leaf:drop:drive:1200:200:0",
 "leaf-zone:drop:steering:1200:200:0","leaf-zone:drop:drive:1200:200:0"));
TEST(M4FaultRuntime, DelayedPacketsKeepOriginalExclusiveDeadline) {
    const auto r=run("zone-leaf:delay:brake:1200:100:40","delay-expiry");
    EXPECT_TRUE(std::any_of(r.events.begin(),r.events.end(),[](const auto& e){return kind(e,"input-rejected") && e.deadline_ns && e.time_ns>=e.deadline_ns;}));
}
TEST(M4FaultRuntime, AcceptedCommandExpiresAtItsOriginalContextDeadline) {
    const auto r=run("zone-leaf:drop:steering:1200:200:0","command-expiry");
    const auto expired=std::find_if(r.events.begin(),r.events.end(),[](const auto& e){return kind(e,"command-expired") && e.owner==2;});
    ASSERT_NE(expired,r.events.end()); EXPECT_GE(expired->time_ns,expired->deadline_ns); EXPECT_LE(expired->time_ns-expired->deadline_ns,200000U);
    EXPECT_TRUE(std::any_of(r.events.begin(),expired,[&](const auto& e){return kind(e,"valid-input") && e.owner==2 && e.deadline_ns==expired->deadline_ns;}));
}
TEST(M4FaultWall, JoinedOverflowRecoveryPreservesPhysicalHistory) {
    const auto r=run("zone-central:overflow:rear:1200:200:0","wall-overflow-rejoin",true,true);
    EXPECT_EQ(r.replaced_links,1U); EXPECT_TRUE(r.model_preserved); EXPECT_GT(r.rejoin_active_ns,2300000000U);
}
TEST(M4FaultRuntime, OverflowCannotHealUntilAllOwnersJoinAndLinksAreReplaced) {
    const auto r=run("zone-central:overflow:rear:1200:200:0","overflow-rejoin",true);
    EXPECT_EQ(r.replaced_links,1U); EXPECT_GT(r.rejoin_active_ns,2300000000U); EXPECT_EQ(r.trace.back().epoch,2U);
    EXPECT_TRUE(std::any_of(r.events.begin(),r.events.end(),[](const auto& e){return kind(e,"overflow");}));
    EXPECT_LT(r.trace.back().soc,.63);
}
TEST(M4FaultRuntime, ResumedOwnerStillNeedsNewDurableGrantAndFullSession) {
    const auto r=run("owner:pause:drive:1200:200:0","owner-rejoin",true);
    EXPECT_GT(r.rejoin_active_ns,2300000000U); EXPECT_TRUE(r.trace.back().normal_armed);
    for(const auto& row:r.trace) { if(row.elapsed_ns>1400000000 && row.elapsed_ns<2300000000) { EXPECT_FALSE(row.run_gate); } }
}
class M4SessionBoundary : public ::testing::TestWithParam<const char*> {};
TEST_P(M4SessionBoundary, MissingPhaseAckNeverReleasesNormalGate) {
    const std::string phase=GetParam(); const auto r=run("session-ack:drop:drive:0:0:0:"+phase,"missing-"+phase);
    EXPECT_EQ(r.first_active_ns,0U); EXPECT_EQ(r.completed_batches,0U); EXPECT_FALSE(r.trace.back().run_gate);
}
INSTANTIATE_TEST_SUITE_P(Handshake,M4SessionBoundary,::testing::Values("prepare","init","release"));
TEST(M4FaultRuntime, LostArmResultCannotCreatePartialNormalOperation) {
    const auto r=run("zone-central:drop:front:0:0:0:arm","lost-arm-ack");
    EXPECT_EQ(r.first_active_ns,0U); EXPECT_EQ(r.front_frames,0U); EXPECT_EQ(r.rear_frames,0U);
}
TEST(M4FaultRuntime, MissingTerminalAckProtectsInsteadOfReportingCleanStop) {
    const auto r=run("leaf-zone:drop:brake:1200:0:0:stop","lost-stop-ack");
    EXPECT_GT(r.first_fault_ns,1200000000U); EXPECT_FALSE(r.trace.back().run_gate);
}
TEST(M4FaultWall, PausedLeafCannotAcknowledgePhysicalWatchdogAction) {
    const auto r=run("owner:pause:drive:1200:200:0","wall-drive-stop",false,true);
    EXPECT_TRUE(std::any_of(r.events.begin(),r.events.end(),[](const auto& e){return kind(e,"output-watchdog") && e.owner==8 && e.code==4;}));
}
TEST(M4ExecutionWatch, LaterCompletionCannotFillAnEarlierMissedOpportunity) {
    M4ExecutionWatch watch{1000000000,1100000000};
    const auto first=watch.begin(4,1000000000,true); ASSERT_TRUE(first);
    const auto next=watch.begin(4,1002000000,true); ASSERT_TRUE(next);
    watch.finish(4,next,1002200000,10000);
    const auto faults=watch.poll(9,1004000000); ASSERT_TRUE(faults[4]);
    EXPECT_EQ(faults[4]->timing.deadline_ns,1004000000U);
    watch.finish(4,first,1006000000,10000); watch.poll(9,1008000000);
    const auto rows=watch.rows(); const auto row=std::find_if(rows.begin(),rows.end(),[](const auto& value){return value.owner==4 && value.slot==0;}); ASSERT_NE(row,rows.end()); EXPECT_EQ(row->detected_ns,1004000000U);
}
TEST(M4ReleaseGrid, SharedOriginAlignsEveryOwnerPeriodAndSkipsCatchup) {
    for(const auto period:{200000ULL,1000000ULL,2000000ULL}) {
        const M4ReleaseGrid grid{1000000000,period};
        EXPECT_EQ(grid.after(1001528864),1000000000+((1528864/period)+1)*period);
        const auto target=grid.after(1000000000+20*period+722310);
        EXPECT_EQ((target-grid.origin_ns)%period,0U);
        EXPECT_GT(target,1000000000+20*period+722310);
    }
}
TEST(M4ReleaseGrid, InvalidClockOrOverflowIsRejected) {
    EXPECT_THROW((M4ReleaseGrid{10,0}.after(10)),std::invalid_argument);
    EXPECT_THROW((M4ReleaseGrid{10,2}.after(9)),std::invalid_argument);
    EXPECT_THROW((M4ReleaseGrid{0,2}.after(UINT64_MAX)),std::overflow_error);
}
TEST(M4ReleaseGrid, ReplaysOriginalMonitorPhaseCrossingWithoutChangingMissPolicy) {
    constexpr std::uint64_t enable=1000000000;
    M4ExecutionWatch old{enable,enable+700000000},aligned{enable,enable+700000000};
    for(std::size_t i=0;i<=318;++i) {
        const auto release=enable+i*2000000;
        // Original slots315..318: private phase1.528864ms plus one
        // extra0.722310ms wake delay crosses a guard boundary before deadline.
        const auto private_start=release+1528864+(i==316?722310:0);
        const auto previous=old.begin(9,private_start,true,release+1528864);
        old.finish(9,previous,private_start+5000,1000);
        const auto common_start=release+(i==316?722310:5000);
        const auto current=aligned.begin(9,common_start,true,release);
        ASSERT_TRUE(current); aligned.finish(9,current,common_start+5000,1000);
    }
    const auto fault=old.poll(8,enable+638000000); ASSERT_TRUE(fault[9]);
    EXPECT_EQ(fault[9]->timing.job,316U);
    EXPECT_FALSE(aligned.poll(8,enable+638000000)[9]);
    EXPECT_EQ(old.rows()[9*341+316].end_ns,0U); // 700ms minus20ms tail:341 slots
}
M4Result run_guard(const std::string& recipe,const std::string& name,bool wall=false) {
    M4Config c; c.scenario=M4Scenario::Fault; c.execution_guards=true; c.wall_time=wall; c.faults={parse_m4_fault(recipe)};
    const auto r=run_m4_async(c);
    if(const auto* base=std::getenv("STRATADRIVE_M4_RESULTS")) write_m4_result(c,r,std::string(base)+"/faults/"+name);
    EXPECT_TRUE(r.passed)<<r.reason; EXPECT_GT(r.deadline_misses,0U);
    const auto target=static_cast<int>(c.faults[0].target);
    const auto found=std::find_if(r.events.begin(),r.events.end(),[&](const auto& e){return kind(e,"deadline-detected") && e.code==target;});
    EXPECT_NE(found,r.events.end());
    if(found!=r.events.end()) { EXPECT_GE(found->time_ns,found->deadline_ns); EXPECT_LE(found->time_ns-found->deadline_ns,10000000U); }
    return r;
}
TEST(M4GuardRuntime, OneSkippedSlotIsDetectedAfterOwnerResumes) {
    const auto r=run_guard("owner:pause:drive:1200:2:0","guard-single-skip");
    EXPECT_GT(r.skipped_opportunities,0U); EXPECT_TRUE(r.model_preserved);
}
TEST(M4GuardRuntime, PhysicalPeerProtectsWhileMonitorIsStopped) {
    const auto r=run_guard("owner:pause:monitor:1200:200:0","guard-monitor-stop");
    EXPECT_TRUE(std::any_of(r.events.begin(),r.events.end(),[](const auto& e){return kind(e,"deadline-detected") && e.owner==8 && e.code==9;}));
    EXPECT_TRUE(std::any_of(r.events.begin(),r.events.end(),[](const auto& e){return kind(e,"override-applied") && e.time_ns<2400000000ULL;}));
}
TEST(M4GuardRuntime, JoinedRecoveryKeepsCommonReleasePhaseAndPhysicalIdentity) {
    M4Config c; c.scenario=M4Scenario::Fault; c.execution_guards=true;
    c.faults={parse_m4_fault("owner:pause:drive:1200:2:0")};
    c.recovery_ns=2300000000; c.duration_ns=4200000000; c.replace_links=true;
    const auto r=run_m4_async(c);
    if(const auto* base=std::getenv("STRATADRIVE_M4_RESULTS")) write_m4_result(c,r,std::string(base)+"/faults/guard-rejoin");
    ASSERT_TRUE(r.passed)<<r.reason; EXPECT_TRUE(r.model_preserved); EXPECT_GT(r.rejoin_active_ns,c.recovery_ns);
    ASSERT_FALSE(r.trace.empty()); const auto origin=r.trace.front().source_ns-r.trace.front().elapsed_ns;
    for(const auto& row:r.execution) EXPECT_EQ((row.release_ns-origin)%2000000,0U);
}
class M4GuardWall : public ::testing::TestWithParam<const char*> {};
TEST_P(M4GuardWall, DeadlineIsDetectedBeforeBlockedOwnerReturns) {
    const std::string target=GetParam(); const auto r=run_guard("owner:overrun:"+target+":1200:6:0","guard-"+target+"-overrun",true);
    const auto detected=std::find_if(r.events.begin(),r.events.end(),[](const auto& e){return kind(e,"deadline-detected");});
    const auto returned=std::find_if(r.events.begin(),r.events.end(),[](const auto& e){return kind(e,"overrun-ended");});
    ASSERT_NE(detected,r.events.end()); ASSERT_NE(returned,r.events.end()); EXPECT_LT(detected->time_ns,returned->time_ns);
    const auto applied=std::find_if(r.events.begin(),r.events.end(),[](const auto& e){return kind(e,"override-applied");});
    ASSERT_NE(applied,r.events.end()); EXPECT_LE(applied->time_ns-detected->time_ns,10000000U);
    for(const auto& t:r.timing) EXPECT_EQ(t.audit_buffer_growths,0U)<<t.owner;
    for(const auto& j:r.execution) if(j.start_ns) {
        const auto origin=j.release_ns-j.slot*2000000-100000000;
        const auto period=j.owner==9?2000000U:j.owner==8?1000000U:200000U;
        EXPECT_LE(j.requested_wake_ns,j.start_ns);
        EXPECT_EQ((j.requested_wake_ns-origin)%period,0U);
    }
}
INSTANTIATE_TEST_SUITE_P(Independent,M4GuardWall,::testing::Values("drive","monitor","physical"));
} // namespace

TEST(M4ExecutionWatch, DelayedWakeCompletesOriginalRequestedSlotOnly) {
    M4ExecutionWatch watch{1000000000,1100000000,static_cast<std::uint16_t>((1U<<4)|(1U<<9))};
    const auto job=watch.begin_requested(4,1006500000,true,1000000000);
    ASSERT_TRUE(job);EXPECT_EQ(*job,0U);watch.finish(4,job,1006600000,10000);
    const auto fault=watch.poll(9,1007000000);ASSERT_TRUE(fault[4]);
    EXPECT_EQ(fault[4]->timing.job,0U);EXPECT_EQ(fault[4]->timing.deadline_ns,1004000000U);
    const auto rows=watch.rows();EXPECT_EQ(rows[0].requested_wake_ns,1000000000U);
    EXPECT_EQ(rows[0].end_ns,1006600000U);EXPECT_EQ(rows[1].end_ns,0U);EXPECT_EQ(rows[3].end_ns,0U);
    EXPECT_FALSE(fault[0]);EXPECT_FALSE(fault[1]);
}
TEST(M4ExecutionWatch, RequestedTargetRejectsFutureAndZero) {
    M4ExecutionWatch watch{1000000000,1100000000};
    EXPECT_THROW(watch.begin_requested(0,1000000000,true,1000000001),std::invalid_argument);
    EXPECT_THROW(watch.begin_requested(0,1000000000,true,0),std::invalid_argument);
}

// Observation must identify the first actual failed submodel without changing its
// original step interval or attempting to heal/re-timestamp the physical state.
TEST(M4PhysicalObservation, LongOriginalStepRetainsFirstFailureContext) {
    using namespace stratadrive;
    simulation::m4_detail::Clock clock{false};transport::RunGate gate;
    std::array<runtime::LatestSnapshot<simulation::OwnerSensors>,8> sensors;
    std::array<runtime::LatestSnapshot<simulation::OwnerActuation>,5> outputs;
    std::vector<simulation::M4Event> events;transport::Protection protection;
    simulation::m4_detail::PhysicalOwner model{clock,gate,sensors,outputs,clock.now_ns(),events,protection,1};
    model.step();ASSERT_TRUE(model.ok());const auto success=clock.now_ns();
    clock.logical+=61000000;model.step();ASSERT_FALSE(model.ok());
    const auto first=model.failure();EXPECT_STREQ(first.model,"energy");EXPECT_STREQ(first.site,"step");
    EXPECT_EQ(first.call_ns,success+61000000);EXPECT_EQ(first.previous_call_ns,success);
    EXPECT_EQ(first.last_success_ns,success);EXPECT_EQ(first.input_ns,success);EXPECT_EQ(first.dt_ns,61000000U);
    clock.logical+=1000000;model.step();EXPECT_EQ(model.failure().call_ns,first.call_ns);
    EXPECT_EQ(model.failure().input_ns,success);EXPECT_EQ(events.size(),1U);
}
TEST(M4PhysicalObservation, IndependentOverrideRejectsFreshNominalOutputInSameEpoch) {
    using namespace stratadrive;
    simulation::m4_detail::Clock clock{false};transport::RunGate gate;gate.release(1);
    std::array<runtime::LatestSnapshot<simulation::OwnerSensors>,8> sensors;
    std::array<runtime::LatestSnapshot<simulation::OwnerActuation>,5> outputs;
    std::vector<simulation::M4Event> events;transport::Protection protection;
    simulation::m4_detail::PhysicalOwner model{clock,gate,sensors,outputs,clock.now_ns(),events,protection,1};
    model.step();clock.logical+=1000000;
    simulation::OwnerActuation command;command.epoch=1;command.source_ns=clock.now_ns();command.brake=brake::Actuation{brake::ActuationMode::Target,0,command.source_ns};outputs[1].publish(command);
    model.step();ASSERT_TRUE(model.ok());protection.request(1);clock.logical+=1000000;model.step();ASSERT_TRUE(model.ok());ASSERT_TRUE(protection.acknowledged(1));
    clock.logical+=1000000;command.source_ns=clock.now_ns();command.brake->issued_time_ns=clock.now_ns();outputs[1].publish(command);
    model.step();EXPECT_TRUE(model.ok());EXPECT_TRUE(protection.acknowledged(1));EXPECT_EQ(model.failure().call_ns,0U);
    // A subsequent genuine higher release can recover; the same-Epoch output cannot.
    gate.release(2);clock.logical+=1000000;command.epoch=2;command.source_ns=clock.now_ns();command.brake->issued_time_ns=clock.now_ns();outputs[1].publish(command);
    model.step();EXPECT_TRUE(model.ok());EXPECT_FALSE(protection.pending(2));
}

TEST(M4ExecutionWatch, RequestedAfterFiniteWindowDoesNotCompleteLastSlot) {
    M4ExecutionWatch watch{1000000000,1100000000,1U};
    EXPECT_FALSE(watch.begin_requested(0,1100000000,true,1082000000));
    const auto rows=watch.rows();ASSERT_EQ(rows.size(),41U);
    EXPECT_EQ(rows.back().release_ns,1080000000U);EXPECT_EQ(rows.back().start_ns,0U);
    const auto fault=watch.poll(9,1100000000);ASSERT_TRUE(fault[0]);
}
