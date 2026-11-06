#include "functional_rig.hpp"
#include "native_admission.hpp"
#include "diagnostics_journal.hpp"
#include <gtest/gtest.h>
#include <filesystem>
#include <cstdlib>
#include <fstream>
#include <iomanip>

namespace {
using namespace stratadrive;
using namespace m7_functional;
TEST(M10NativeSpeed, LiveBmsReferenceProtectionAndDurableDtc) {
    // Native owners, wire codecs, gates, actuator/electrical model and journal.
    // Wheel/work are stationary synthetic inputs, not CARLA driving evidence.
    for(bool loss:{false,true}) {
        constexpr Scope scope{8401,42,7};
        FunctionalRig rig(scope,99,PlantMode::ExternalSolverWork,true,60000);
        rig.speed_profile();rig.supervise_speed({0,200});
        std::unique_ptr<m7_native::Admission> admission;
        m7_native::Output prior;Time previous=0,first_fault=0;
        std::vector<diagnostics::Event> events;
        std::optional<SpeedControlAudit> last;
        unsigned steps=0;Report final;
        for(unsigned i=0;i<600;++i) {
            const double seconds=1+i*.01;const Time now=static_cast<Time>(std::llround(seconds*1e9));
            if(loss && i==400)rig.omit_force_input(true);
            if(loss && i==450)rig.omit_force_input(false);
            const Observation o{scope,domain,100+i,seconds,.01};const WheelSample wheel{99,100+i,now,{0,0,0,0}};
            Report r;
            if(!i)r=rig.observe(o,wheel);
            else {
                m7_external::SolverWork w;
                w.frame=100+i;w.begin=previous;w.end=now;w.oldest=prior.empty?previous:prior.oldest_actuator;
                w.torque=prior.torque;w.dt=double(.01f*(1.f/320.f));w.wheel={0,{7,99+i,previous},previous};
                r=rig.observe(o,wheel,w);
            }
            if(r.diagnostic_events)events.insert(events.end(),r.diagnostic_events->begin(),r.diagnostic_events->end());
            ASSERT_TRUE(r.supervised_speed);const auto& supervised=*r.supervised_speed;
            if(supervised.fault) {
                ASSERT_TRUE(loss)<<" frame="<<i<<" reason="<<static_cast<unsigned>(supervised.fault->reason)<<" reference="<<static_cast<unsigned>(supervised.fault->reference_fault)<<" force_source="<<(supervised.force?supervised.force->source_ns:0)<<" detected="<<supervised.fault->detected_ns;if(!first_fault)first_fault=supervised.fault->detected_ns;
                EXPECT_EQ(supervised.fault->detected_ns,first_fault);
                EXPECT_EQ(supervised.decision.source,central::ProposalSource::Protection);
                EXPECT_EQ(supervised.decision.reason,central::ProposalReason::CapacityInput);
            } else if(r.speed_control) {
                EXPECT_EQ(supervised.decision.source,central::ProposalSource::Classical);
                ASSERT_TRUE(supervised.force);ASSERT_TRUE(supervised.reference);
                EXPECT_GT(supervised.force->propulsion_n,0);EXPECT_LT(supervised.force->propulsion_n,1000);
                EXPECT_LE(supervised.force->source_ns,r.speed_control->release_ns);
                EXPECT_LE(r.speed_control->expiry_ns,supervised.force->expires_ns);
                EXPECT_LE(r.speed_control->input_expiry_ns,supervised.force->expires_ns);
                if(!last || last->sequence!=r.speed_control->sequence) {
                    if(last) {EXPECT_EQ(r.speed_control->release_ns-last->release_ns,20*ms);}
                    last=r.speed_control;++steps;
                }
            }
            if(!admission)admission=std::make_unique<m7_native::Admission>(42,now);
            const auto& e=*r.native_export;m7_native::Input in;
            in.observed=e.observed;in.enable=e.enable;in.normal=e.normal;in.actual=e.actual;in.commands=e.commands;
            in.release=e.release;in.credit=e.credit;in.permission=e.permission;
            in.protection_since=e.protection_since;in.protection_selected_mask=e.protection_selected_mask;
            in.service_mask=r.service_mask;in.credit_mask=r.credit_mask;in.release_mask=r.release_mask;
            ASSERT_TRUE(admission->accept(in,now,prior))<<admission->error()<<" frame="<<i;
            if(first_fault) {EXPECT_FALSE(e.normal);EXPECT_FALSE(prior.normal);EXPECT_TRUE(prior.protection);}
            previous=now;final=r;
        }
        EXPECT_GT(steps,100U);
        char name[]="/tmp/stratadrive-supervised-XXXXXX";const auto* directory=mkdtemp(name);ASSERT_NE(directory,nullptr);
        const auto path=std::filesystem::path(directory)/"store";
        struct Cleanup {std::filesystem::path p;~Cleanup(){std::filesystem::remove_all(p);}} cleanup{directory};
        diagnostics::FileJournal::initialize(path.string(),8401,{},4);
        const diagnostics::Key key{diagnostics::Code::CentralControl,1,4,4};
        {
            diagnostics::FileJournal journal(path.string());diagnostics::Recorder recorder(journal);
            for(const auto& event:events)ASSERT_TRUE(recorder.record(event).durable);
            ASSERT_TRUE(recorder.ledger().complete());
            const auto* dtc=recorder.ledger().find(key);
            if(loss) {
                ASSERT_NE(dtc,nullptr);EXPECT_EQ(dtc->count,1U);EXPECT_FALSE(dtc->cleared);
                EXPECT_EQ(dtc->first_detected.ns,first_fault);
                EXPECT_EQ(final.native_export->protection_selected_mask,255U);
                EXPECT_EQ(final.credit_mask,0U);EXPECT_FALSE(final.armed);
                ASSERT_TRUE(final.returned_torque);EXPECT_LE(std::abs(*final.returned_torque),1);
                unsigned actuals=0;
                for(const auto& event:events)if(event.kind==diagnostics::Kind::Actual && event.related==dtc->first_event)++actuals;
                EXPECT_GE(actuals,2U);
            } else {EXPECT_EQ(dtc,nullptr);EXPECT_TRUE(recorder.ledger().records().empty());}
        }
        diagnostics::FileJournal journal(path.string());diagnostics::Recorder reopened(journal);
        EXPECT_TRUE(reopened.ledger().complete());
        if(loss) {const auto* dtc=reopened.ledger().find(key);ASSERT_NE(dtc,nullptr);EXPECT_EQ(dtc->count,1U);EXPECT_FALSE(dtc->cleared);}
        if(const auto* evidence=std::getenv("STRATADRIVE_NATIVE_SPEED_EVIDENCE")) {
            const auto out=std::filesystem::path(evidence)/(loss?"force-loss":"nominal");
            ASSERT_FALSE(std::filesystem::exists(out));std::filesystem::create_directories(out);
            std::filesystem::copy(path,out/"store",std::filesystem::copy_options::recursive);
            std::ofstream raw(out/"events.hex");
            for(const auto& event:events) {
                for(const auto byte:diagnostics::encode(event))raw<<std::hex<<std::setw(2)<<std::setfill('0')<<static_cast<unsigned>(byte);
                raw<<'\n';
            }
            std::ofstream result(out/"result.json");
            result<<"{\"input\":\"synthetic_stationary_wheel_work\",\"observations\":600,\"control_steps\":"<<steps
                <<",\"events\":"<<events.size()<<",\"first_fault_ns\":"<<first_fault
                <<",\"selected_mask\":"<<final.native_export->protection_selected_mask<<",\"credit_mask\":"<<final.credit_mask
                <<",\"complete\":"<<(reopened.ledger().complete()?"true":"false")<<"}\n";
            ASSERT_TRUE(raw.good());ASSERT_TRUE(result.good());
        }
    }
}
} // namespace
