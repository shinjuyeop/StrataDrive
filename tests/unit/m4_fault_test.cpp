#include "m4_async_runtime.hpp"
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
} // namespace
