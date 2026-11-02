#include "functional_rig.hpp"
#include "native_admission.hpp"
#include <gtest/gtest.h>
namespace {
using namespace stratadrive;
using namespace m7_functional;
TEST(M8CarlaStop, SameOwnersSelectTerminalHoldOrProtectionWithOriginalProof) {
    for(auto mode:{SpeedTerminal::NormalStop,SpeedTerminal::SpeedInputLoss,SpeedTerminal::StopProtection,SpeedTerminal::NormalStop30}) {
        FunctionalRig rig({1,42,7},99,PlantMode::ExternalSolverWork,true,60000);
        const bool high=mode==SpeedTerminal::NormalStop30;
        if(high) {
            rig.route_profile({{0,0},{5,0}},RouteProfile::Straight30Stop);
            EXPECT_THROW(rig.route_profile({{0,0},{5,0}},RouteProfile::Straight30),std::runtime_error);
        } else rig.speed_profile(mode);
        EXPECT_THROW(rig.speed_profile(SpeedTerminal::None),std::runtime_error);
        EXPECT_THROW(rig.speed_profile(static_cast<SpeedTerminal>(99)),std::runtime_error);
        std::unique_ptr<m7_native::Admission> admission;
        m7_native::Output prior;m7_native::Input held_input;Time previous=0;bool held=false,protected_actual=false,complete=false,corrupted=false;
        for(unsigned i=0;i<=(high?4300U:2300U);++i) {
            const double seconds=3.997146773152053+i*.009999999776482582;
            const auto now=static_cast<Time>(std::llround(seconds*1e9));
            Observation o{{1,42,7},domain,100+i,seconds,.01};WheelSample wheel{99,100+i,now,{0,0,0,0}};
            if(high)rig.pose({42,100+i,now,0,0,0},99);
            m7_external::SolverWork work;work.frame=100+i;work.begin=previous;work.end=now;
            work.oldest=prior.empty?previous:prior.oldest_actuator;work.torque=prior.torque;
            work.dt=double(.01f*(1.f/320.f));work.wheel={0,{7,99+i,previous},previous};
            Report r;
            ASSERT_NO_THROW(r=i?rig.observe(o,wheel,work):rig.observe(o,wheel))<<"frame="<<i<<" mode="<<static_cast<int>(mode);
            EXPECT_EQ(r.terminal_mode,mode);
            EXPECT_EQ(r.stop_configuration.braking_timeout_ns,(high?10000:5000)*ms);
            if(r.trigger_ns && r.speed_control) {EXPECT_EQ(r.trigger_ns,r.speed_control->origin_ns+(high?35000:15000)*ms);}
            const auto& e=*r.native_export;m7_native::Input in;
            in.observed=e.observed;in.enable=e.enable;in.normal=e.normal;in.actual=e.actual;in.commands=e.commands;
            in.stop_requests=e.stop_requests;in.stop_results=e.stop_results;
            in.release=e.release;in.credit=e.credit;in.permission=e.permission;
            in.protection_since=e.protection_since;in.protection_selected_mask=e.protection_selected_mask;
            in.service_mask=r.service_mask;in.credit_mask=r.credit_mask;in.release_mask=r.release_mask;
            if(!admission)admission=std::make_unique<m7_native::Admission>(42,now);
            if(!in.normal && !in.protection_since && in.stop_requests[0] && !corrupted) {
                for(unsigned fault=0;fault<8;++fault) {
                    auto bad=in;m7_native::Output unused;
                    if(fault==0)bad.stop_results[1].reset();
                    if(fault==1)bad.stop_requests[2].reset();
                    if(fault==2)bad.credit_mask=0;
                    if(fault==3)bad.protection_since=now;
                    if(fault>=4 && fault<=6) {
                        auto m=remote::decode_owner_message(bad.stop_requests[0]->bytes.data(),bad.stop_requests[0]->size);
                        auto& q=std::get<transport::LeafRequest>(m->payload);
                        if(fault==4)q.lease->expires_at_ns=now+10*ms;
                        if(fault==5)q.lease->epoch=41;
                        if(fault==6)q.lease->sequence+=1;
                        bad.stop_requests[0]=remote::encode_owner_message(*m);
                    }
                    if(fault==7) {
                        auto m=remote::decode_owner_message(bad.stop_results[0]->bytes.data(),bad.stop_results[0]->size);
                        std::get<transport::LeafResult>(std::get<transport::LeafReport>(m->payload)).accepted=false;
                        bad.stop_results[0]=remote::encode_owner_message(*m);
                    }
                    EXPECT_FALSE(admission->eligible(bad,now,unused))<<"fault="<<fault;
                }
                corrupted=true;
            }
            if(mode==SpeedTerminal::StopProtection && in.protection_since) {
                EXPECT_EQ(r.detection_ns,r.handoff_ns+100*ms);EXPECT_GT(r.handoff_ns,r.trigger_ns);
                EXPECT_FALSE(r.power_off);
                for(unsigned fault=0;fault<4;++fault) {
                    auto bad=in;m7_native::Output unused;
                    if(fault==0)bad.protection_since=r.handoff_ns; // predates accepted hold
                    if(fault==1)bad.protection_selected_mask=127;
                    if(fault==2)bad.credit_mask=255;
                    if(fault==3)bad.release[0].reset();
                    EXPECT_FALSE(admission->eligible(bad,now,unused))<<"protection fault="<<fault;
                }
                if(protected_actual) {
                    auto reopen=in;m7_native::Output unused;std::string reason;
                    reopen.protection_since=0;reopen.protection_selected_mask=0;reopen.credit_mask=255;
                    // Replay the actual prior hold packets, even after the
                    // live export has aged them out of its capture buffers.
                    reopen.stop_requests=held_input.stop_requests;reopen.stop_results=held_input.stop_results;
                    EXPECT_FALSE(admission->eligible(reopen,now,unused,&reason));
                    EXPECT_EQ(reason,"native_protection_terminal");
                }
            }
            if(held) {auto resume=in;resume.normal=true;resume.stop_requests={};resume.stop_results={};m7_native::Output unused;
                EXPECT_FALSE(admission->eligible(resume,now,unused));}
            ASSERT_TRUE(admission->accept(in,now,prior))<<admission->error()<<" frame="<<i<<" stop="<<static_cast<int>(r.stop_state);
            if(prior.normal_stop)held_input=in;
            held|=prior.normal_stop;protected_actual|=prior.protection;
            complete|=r.stop_state==central::NormalStopState::Complete && r.power_off;
            previous=now;
        }
        EXPECT_EQ(held,mode!=SpeedTerminal::SpeedInputLoss);EXPECT_EQ(complete,mode==SpeedTerminal::NormalStop || high);
        EXPECT_EQ(protected_actual,mode==SpeedTerminal::SpeedInputLoss || mode==SpeedTerminal::StopProtection);
    }
}
}
