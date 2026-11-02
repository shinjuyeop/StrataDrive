#include "functional_rig.hpp"
#include "native_admission.hpp"
#include <gtest/gtest.h>

namespace {
using namespace stratadrive;
using namespace m7_functional;
constexpr Scope scope{1,42,7};
TEST(M8CarlaSpeed, ExplicitSolverProfileCannotMixFixedRequestsOrLegacyScope) {
    FunctionalRig old(scope,99,PlantMode::ExternalSolverWork,true);
    EXPECT_THROW(old.speed_profile(),std::runtime_error);
    FunctionalRig rig(scope,99,PlantMode::ExternalSolverWork,true,60000);
    rig.speed_profile();
    EXPECT_THROW(rig.speed_profile(),std::runtime_error);
    EXPECT_THROW(rig.request_profile({{60000,0,0,0,true}}),std::runtime_error);
}
TEST(M8CarlaSpeed, OriginalFractionalSourcesSupportWholeIntervalsAndCreditLossBlocksResume) {
    // Synthetic stationary sensor/work exercises authority/clock mapping only.
    // Vehicle tracking is assessed separately on real CARLA receipts.
    for(bool fractional:{false,true}) {
        FunctionalRig rig(scope,99,PlantMode::ExternalSolverWork,true,60000);rig.speed_profile();
        std::unique_ptr<m7_native::Admission> admission;
        m7_native::Output prior;Time previous=0;unsigned steps=0;
        std::optional<SpeedControlAudit> last;
        bool credit_rejected=false;
        for(unsigned i=0;i<410;++i) {
            const auto seconds=fractional?3.997146773152053+i*.009999999776482582:1+i*.01;
            const auto now=static_cast<Time>(std::llround(seconds*1e9));
            const Observation o{scope,domain,100+i,seconds,.01};const WheelSample wheel{99,100+i,now,{0,0,0,0}};
            Report r;
            if(i==400)rig.stop_credit(true);
            try {
                if(!i)r=rig.observe(o,wheel);
                else {
                    m7_external::SolverWork w;
                    w.frame=100+i;w.begin=previous;w.end=now;w.oldest=prior.empty?previous:prior.oldest_actuator;
                    w.torque=prior.torque;w.dt=double(.01f*(1.f/320.f));w.wheel={0,{7,99+i,previous},previous};
                    r=rig.observe(o,wheel,w);
                }
            } catch(const std::runtime_error& e) {
                ASSERT_GE(i,400U)<<e.what();credit_rejected=true;break;
            }
            if(!admission)admission=std::make_unique<m7_native::Admission>(42,now);
            const auto& e=*r.native_export;m7_native::Input in;
            in.observed=e.observed;in.enable=e.enable;in.normal=e.normal;
            in.actual=e.actual;in.commands=e.commands;in.release=e.release;in.credit=e.credit;in.permission=e.permission;
            in.service_mask=r.service_mask;in.credit_mask=r.credit_mask;in.release_mask=r.release_mask;
            const bool accepted=admission->accept(in,now,prior);
            if(!accepted) {
                for(unsigned role=0;role<3;++role) {
                    if(!e.commands[role])continue;
                    const auto decoded=remote::decode_owner_message(e.commands[role]->bytes.data(),e.commands[role]->size);
                    const auto& q=std::get<transport::LeafRequest>(decoded->payload);
                    if(q.command)std::cerr<<"role="<<role<<" now="<<now<<" parent="<<q.command->parent.source_time_ns
                        <<" expiry="<<q.command->expires_at_ns<<" oldest="<<q.command->oldest_input_time_ns<<'\n';
                }
                if(r.speed_control)std::cerr<<"speed release="<<r.speed_control->release_ns<<" source="<<r.speed_control->source_ns<<'\n';
            }
            ASSERT_TRUE(accepted)<<admission->error()<<" frame="<<i;
            if(r.speed_control && (!last || last->sequence!=r.speed_control->sequence)) {
                const auto& s=*r.speed_control;
                if(last) {EXPECT_EQ(s.release_ns-last->release_ns,20*ms);EXPECT_GT(s.source_ns,last->source_ns);}
                EXPECT_EQ(s.expiry_ns,s.release_ns+30*ms+1);
                EXPECT_EQ(s.input_expiry_ns,s.source_ns+60*ms+1);
                EXPECT_EQ(s.sequence,steps++);EXPECT_DOUBLE_EQ(s.speed_mps,0);last=s;
            }
            previous=now;
        }
        EXPECT_GT(steps,100U);EXPECT_TRUE(credit_rejected);
    }
}
} // namespace
