#include "m4_owner_network.hpp"
#include "perception_2k_control.hpp"
#include <gtest/gtest.h>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>

namespace {
using namespace stratadrive;
using namespace simulation::m4_detail;
constexpr std::uint64_t wall_origin=9000000000000ULL;
enum class Case { ShadowLoss, RequiredHealthy, CameraLoss, Invalid, ReceiptLate, Identity,
                  ExplicitUnavailable, Recovery, TransientInvalid };
class Native2kControlSil:public ::testing::TestWithParam<Case> {};
TEST_P(Native2kControlSil, IndependentOwnersProtectionActualAndExplicitRecovery) {
    const auto scenario=GetParam();
    const bool shadow=scenario==Case::ShadowLoss, healthy=scenario==Case::RequiredHealthy;
    const bool recovery=scenario==Case::Recovery;
    simulation::M4Config config;config.speed_loop=true;config.supervised_speed=true;
    config.diagnostics_run=9710;config.renewal=central::CommandRenewal::Host10ms;
    config.duration_ns=9000*kMs;
    if(recovery)config.recovery_ns=6500*kMs;
    Network n(config);
    central::Native2kControl perception(shadow?central::PerceptionUse::Shadow:central::PerceptionUse::Required);
    std::uint32_t bound_epoch=0;std::uint64_t frame=0, first_loss=0, first_actual=0, releases=0;
    bool had_drive=false, restored_but_latched=false, recovered=false;
    std::ostringstream evidence;
    evidence<<std::setprecision(17)<<"source_ns,wall_ns,epoch,available,latched,reason,frame,run_gate,coordinator_fault,torque_nm,brake_pa,drive_source_ns,brake_source_ns,wheel_rad_s\n";
    for(std::uint64_t elapsed=0;elapsed<=config.duration_ns;elapsed+=kIoPoll) {
        n.clock.logical=kLogicalStart+elapsed;const auto now=n.clock.logical;
        if(elapsed%kMs==0)n.step(8);
        for(std::size_t owner=0;owner<7;++owner)n.step(owner);
        // Continue observing after protection closes RunLease. Only a different
        // pending global INIT pauses the old-session adapter until release.
        if(n.active_epoch==n.startup.plan().epoch && n.active_epoch) {
            const central::Native2kNow time{now,wall_origin+elapsed,wall_origin+elapsed};
            const bool new_session=bound_epoch!=n.active_epoch;
            if(new_session) {
                bound_epoch=n.active_epoch;frame=0;
                const auto enable=n.startup.plan().enable_ns;
                ASSERT_TRUE(perception.start_session({bound_epoch,77,88,enable,wall_origin+enable-kLogicalStart}));
            }
            const bool injected=elapsed>=3000*kMs && elapsed<4000*kMs && !healthy;
            const bool stopped=injected && (shadow || scenario==Case::CameraLoss || recovery);
            if((new_session || elapsed%(50*kMs)==0) && !stopped) {
                central::Native2kFrame f;f.epoch=bound_epoch;f.source_clock=77;f.wall_clock=88;f.frame=++frame;
                f.source_ns=now;f.expires_ns=now+central::kPerceptionLifetimeNs;
                f.received_wall_ns=time.wall_ns;f.wall_expires_ns=time.wall_ns+central::kPerceptionLifetimeNs;
                f.valid=true; // Synthetic valid empty detections; not a clear-road claim.
                if(injected && scenario==Case::Invalid)f.width=640;
                if(injected && scenario==Case::ReceiptLate) { f.received_wall_ns-=100*kMs;f.wall_expires_ns=time.wall_ns; }
                if(injected && scenario==Case::Identity)++f.epoch;
                if(injected && scenario==Case::ExplicitUnavailable)perception.unavailable(time);
                else {
                    if(injected && scenario==Case::TransientInvalid) {
                        auto bad=f;bad.valid=false;EXPECT_FALSE(perception.receive(bad,time));
                    }
                    const bool accepted=perception.receive(f,time);
                    EXPECT_EQ(accepted,!injected || scenario==Case::TransientInvalid)<<static_cast<int>(scenario);
                }
            }
            if(elapsed%(20*kMs)==0) {
                const auto decision=perception.release(time,n.core);++releases;
                if(decision.protection_requested) {
                    EXPECT_FALSE(n.gate.allows(bound_epoch));
                    EXPECT_NE(n.core.decision().fault,central::CoordinatorFault::None);
                }
                if(perception.first_loss() && !first_loss)first_loss=perception.first_loss()->detected.source_ns;
                if(first_loss && bound_epoch==1) { EXPECT_EQ(perception.first_loss()->detected.source_ns,first_loss); }
                const auto input=n.port.feedback();const auto& drive=input.rear.drive_actual;const auto& brake=input.front.brake_actual;
                if(elapsed==2500*kMs) {
                    EXPECT_TRUE(n.gate.allows(1));EXPECT_TRUE(n.core.decision().normal_armed);
                    ASSERT_TRUE(drive && drive->wheel_speed && drive->torque_nm);
                    EXPECT_GT(drive->wheel_speed->value_rad_s,.01);had_drive=true;
                }
                if(first_loss && !shadow && elapsed>=4000*kMs && elapsed<6500*kMs) {
                    EXPECT_TRUE(decision.available);EXPECT_TRUE(decision.latched);EXPECT_TRUE(decision.protection_requested);
                    EXPECT_FALSE(n.gate.allows(1));EXPECT_FALSE(n.core.decision().normal_armed);restored_but_latched=true;
                    EXPECT_FALSE(perception.start_session({1,77,88,now,time.wall_ns}));
                }
                if(first_loss && !shadow && bound_epoch==1 && drive && brake && drive->torque_nm && brake->pressure_pa &&
                   drive->source_time_ns>=first_loss && brake->source_time_ns>=first_loss &&
                   now-drive->source_time_ns<=30*kMs && now-brake->source_time_ns<=30*kMs &&
                   std::abs(*drive->torque_nm)<=.1 && *brake->pressure_pa>=900000) {
                    if(!first_actual)first_actual=now;
                }
                if(elapsed==8000*kMs && recovery) {
                    EXPECT_EQ(bound_epoch,2U);EXPECT_TRUE(n.gate.allows(2));EXPECT_TRUE(n.core.decision().normal_armed);
                    EXPECT_FALSE(decision.latched);EXPECT_FALSE(perception.first_loss());
                    ASSERT_TRUE(drive && drive->wheel_speed);EXPECT_GT(drive->wheel_speed->value_rad_s,.01);recovered=true;
                }
                evidence<<now<<','<<time.wall_ns<<','<<bound_epoch<<','<<decision.available<<','<<decision.latched<<','
                    <<static_cast<unsigned>(decision.reason)<<','<<decision.frame<<','<<n.gate.allows(bound_epoch)<<','
                    <<static_cast<unsigned>(n.core.decision().fault)<<','<<(drive&&drive->torque_nm?*drive->torque_nm:0)<<','
                    <<(brake&&brake->pressure_pa?*brake->pressure_pa:0)<<','<<(drive?drive->source_time_ns:0)<<','
                    <<(brake?brake->source_time_ns:0)<<','<<(drive&&drive->wheel_speed?drive->wheel_speed->value_rad_s:0)<<'\n';
            }
        }
        n.step(7);
    }
    EXPECT_TRUE(had_drive);EXPECT_GT(releases,400U);EXPECT_TRUE(n.physical.ok());
    EXPECT_EQ(n.startup.run_enabled(),shadow || healthy || recovery);EXPECT_GT(n.port.completed_batches(),0U);
    if(shadow || healthy) {
        EXPECT_TRUE(n.gate.allows(1));EXPECT_TRUE(n.core.decision().normal_armed);
        EXPECT_EQ(n.core.decision().fault,central::CoordinatorFault::None);EXPECT_EQ(first_actual,0U);
        if(shadow) { EXPECT_NE(first_loss,0U); } else { EXPECT_EQ(first_loss,0U); }
    } else {
        ASSERT_NE(first_loss,0U);ASSERT_NE(first_actual,0U);
        ASSERT_NE(n.result.all_protected_ns,0U);
        EXPECT_GE(kLogicalStart+n.result.all_protected_ns,first_loss);
        EXPECT_LE(kLogicalStart+n.result.all_protected_ns-first_loss,100*kMs);
        EXPECT_GE(first_loss,kLogicalStart+3000*kMs);EXPECT_LE(first_loss,kLogicalStart+3100*kMs);
        EXPECT_GE(first_actual,first_loss);EXPECT_LE(first_actual-first_loss,500*kMs);
        EXPECT_TRUE(restored_but_latched);EXPECT_EQ(recovered,recovery);
    }
    if(shadow) {
        Network baseline(config);
        for(std::uint64_t elapsed=0;elapsed<=config.duration_ns;elapsed+=kIoPoll) {
            baseline.clock.logical=kLogicalStart+elapsed;
            if(elapsed%kMs==0)baseline.step(8);
            for(std::size_t owner=0;owner<8;++owner)baseline.step(owner);
        }
        ASSERT_EQ(n.physical.trace.size(),baseline.physical.trace.size());
        for(std::size_t i=0;i<n.physical.trace.size();++i) {
            const auto& a=n.physical.trace[i];const auto& b=baseline.physical.trace[i];
            EXPECT_EQ(a.source_ns,b.source_ns);EXPECT_EQ(a.model_sequence,b.model_sequence);
            EXPECT_DOUBLE_EQ(a.torque_nm,b.torque_nm);EXPECT_DOUBLE_EQ(a.pressure_pa,b.pressure_pa);
            EXPECT_DOUBLE_EQ(a.speed_mps,b.speed_mps);EXPECT_DOUBLE_EQ(a.energy_j,b.energy_j);
        }
        ASSERT_EQ(n.result.speed_trace.size(),baseline.result.speed_trace.size());
        for(std::size_t i=0;i<n.result.speed_trace.size();++i) {
            const auto& a=n.result.speed_trace[i];const auto& b=baseline.result.speed_trace[i];
            EXPECT_EQ(a.now_ns,b.now_ns);EXPECT_EQ(a.speed_source_ns,b.speed_source_ns);
            EXPECT_EQ(a.request_expiry_ns,b.request_expiry_ns);EXPECT_DOUBLE_EQ(a.acceleration_mps2,b.acceleration_mps2);
        }
    }
    for(const auto& trace:n.physical.trace)EXPECT_LE(std::abs(trace.vehicle_balance_j),1e-5);
    if(const auto* output=std::getenv("STRATADRIVE_2K_CONTROL_EVIDENCE")) {
        const std::filesystem::path directory(output);std::filesystem::create_directories(directory);
        const auto name=std::to_string(static_cast<int>(scenario));
        std::ofstream(directory/(name+".csv"))<<evidence.str();
        std::ofstream(directory/(name+".json"))<<"{\"case\":"<<name<<",\"releases\":"<<releases
            <<",\"first_loss_ns\":"<<first_loss<<",\"first_protective_actual_ns\":"<<first_actual
            <<",\"zone_protection_ack_ns\":"<<(n.result.all_protected_ns?kLogicalStart+n.result.all_protected_ns:0)
            <<",\"final_epoch\":"<<bound_epoch<<",\"logical_time_only\":true}\n";
    }
}
INSTANTIATE_TEST_SUITE_P(Policy,Native2kControlSil,::testing::Values(
    Case::ShadowLoss,Case::RequiredHealthy,Case::CameraLoss,Case::Invalid,Case::ReceiptLate,
    Case::Identity,Case::ExplicitUnavailable,Case::Recovery,Case::TransientInvalid));
} // namespace
