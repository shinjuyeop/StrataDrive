#include "functional_rig.hpp"
#include "native_admission.hpp"
#include <gtest/gtest.h>
#include <functional>
namespace {
namespace native=stratadrive::m7_native;
using namespace stratadrive;
using namespace m7_functional;
constexpr Scope scope{1,42,7};
struct Trace {
    std::vector<native::Input> inputs;
    explicit Trace(bool fractional=false,bool protect=false) {
        FunctionalRig rig(scope,99,PlantMode::ExternalWheelZoh,true);
        for(unsigned i=0;i<400;++i) {
            if(protect && i==200)rig.request_protection();
            const double time=fractional?3.997146773152053+i*.009999999776482582:1+i*.01;
            const auto ns=static_cast<Time>(std::llround(time*1e9));
            const auto r=rig.observe({scope,domain,100+i,time,.01},{99,100+i,ns,{0,0,0,0}});
            const auto& e=*r.native_export;
            native::Input in;
            in.observed=e.observed;in.enable=e.enable;in.normal=e.normal;
            in.protection_since=e.protection_since;in.protection_selected_mask=e.protection_selected_mask;
            in.actual=e.actual;in.commands=e.commands;in.release=e.release;in.credit=e.credit;in.permission=e.permission;
            in.service_mask=r.service_mask;in.release_mask=r.release_mask;in.credit_mask=r.credit_mask;
            inputs.push_back(in);
        }
    }
};
void mutate(native::Packet& packet,const std::function<void(remote::OwnerMessage&)>& action) {
    auto m=remote::decode_owner_message(packet->bytes.data(),packet->size);
    ASSERT_TRUE(m);action(*m);packet=remote::encode_owner_message(*m);ASSERT_TRUE(packet);
}
TEST(M7NativeAdmission, RealEightOwnersWholeIntervalsAndFractionalOriginalClock) {
    for(bool fractional:{false,true}) {
        Trace trace(fractional);native::Admission gate(42,trace.inputs.front().observed);
        unsigned normal=0,empty=0;
        for(const auto& in:trace.inputs) {
            native::Output out;ASSERT_TRUE(gate.accept(in,in.observed,out))<<gate.error()<<" at "<<in.observed;
            if(out.empty)++empty;
            if(out.normal) {
                ++normal;
                EXPECT_LE(in.observed+native::step-out.oldest_actuator,30*ms);
                EXPECT_GT(out.exclusive_expiry,in.observed+native::step);
                EXPECT_LE(out.torque,60);
            }
        }
        EXPECT_GT(normal,300U);EXPECT_EQ(empty,4U);
    }
}
TEST(M7NativeAdmission, OriginalAuthorityAndCausalityCorruptionsLatch) {
    Trace trace;
    const std::vector<std::function<void(native::Input&)>> faults={
        [](auto& x){x.service_mask&=~1U;},
        [](auto& x){x.credit_mask&=~1U;},
        [](auto& x){x.release_mask&=~1U;},
        [](auto& x){x.release[0].reset();},
        [](auto& x){x.credit[3].reset();},
        [](auto& x){x.actual[2].reset();},
        [](auto& x){x.commands[0].reset();},
        [](auto& x){x.permission.reset();},
        [](auto& x){x.normal=false;},
        [](auto& x){++x.observed;},
        [](auto& x){x.actual[0]->bytes[40]^=1;}, // outer wire CRC
        [](auto& x){ // valid original Command/P05 must never stand in for Actual
            const auto q=remote::decode_owner_message(x.commands[0]->bytes.data(),x.commands[0]->size);
            const auto f=std::get<transport::LeafRequest>(q->payload).frame;
            mutate(x.actual[0],[&](auto& m){m.payload=f;});
        },
        [](auto& x){mutate(x.actual[0],[](auto& m){std::get<can::SteeringFrame>(std::get<transport::Feedback>(m.payload)).payload[0]^=1;});}, // inner P05, valid outer CRC
        [](auto& x){mutate(x.release[0],[](auto& m){std::get<session::Ack>(m.payload).accepted=false;});},
        [](auto& x){mutate(x.credit[0],[](auto& m){--std::get<remote::RunLease>(m.payload).expires_at_ns;});},
        [](auto& x){mutate(x.commands[0],[](auto& m){++std::get<transport::LeafRequest>(m.payload).command->parent.sequence;});},
        [](auto& x){mutate(x.commands[1],[&](auto& m){std::get<transport::LeafRequest>(m.payload).command->expires_at_ns=x.observed+native::step;});},
        [](auto& x){mutate(x.commands[2],[](auto& m){std::get<transport::LeafRequest>(m.payload).command->parent.source_time_ns-=20*ms;});},
        [](auto& x){mutate(x.permission,[](auto& m){std::get<transport::LeafRequest>(m.payload).parent.reset();});},
        [](auto& x){x.actual={};}
    };
    for(unsigned f=0;f<faults.size();++f) {
        native::Admission gate(42,trace.inputs.front().observed);native::Output out;
        for(unsigned i=0;i<100;++i)ASSERT_TRUE(gate.accept(trace.inputs[i],trace.inputs[i].observed,out))<<gate.error();
        auto bad=trace.inputs[100];faults[f](bad);
        EXPECT_FALSE(gate.accept(bad,trace.inputs[100].observed,out))<<"fault "<<f;
        EXPECT_FALSE(gate.error().empty())<<"fault "<<f;
        EXPECT_FALSE(gate.accept(trace.inputs[100],trace.inputs[100].observed,out))<<"healed "<<f;
    }
}
TEST(M7NativeAdmission, BootstrapCannotHideNormalActualOrSkipObservation) {
    Trace trace;
    for(unsigned kind=0;kind<3;++kind) {
        native::Admission gate(42,trace.inputs.front().observed);native::Output out;
        if(kind==2) {
            ASSERT_TRUE(gate.accept(trace.inputs[0],trace.inputs[0].observed,out));
            EXPECT_FALSE(gate.accept(trace.inputs[2],trace.inputs[2].observed,out));
        } else {
            unsigned i=0;
            while(!trace.inputs[i].normal) {
                ASSERT_TRUE(gate.accept(trace.inputs[i],trace.inputs[i].observed,out))<<gate.error();++i;
            }
            auto bad=trace.inputs[i];
            if(kind==0)bad.normal=false;else bad.actual={};
            EXPECT_FALSE(gate.accept(bad,bad.observed,out));
        }
    }
}
TEST(M7NativeAdmission, ReleaseAckAtExclusiveCommitDeadlineIsRejected) {
    Trace trace;native::Admission gate(42,trace.inputs.front().observed);native::Output out;
    for(unsigned i=0;i<5;++i) {
        auto in=trace.inputs[i];in.actual={}; // delivery withheld during bounded INIT only
        ASSERT_TRUE(gate.accept(in,in.observed,out))<<gate.error();
    }
    auto bad=trace.inputs[5];
    mutate(bad.release[0],[](auto& m){auto& ack=std::get<session::Ack>(m.payload);ack.source_ns=ack.plan.commit_deadline_ns;});
    EXPECT_FALSE(gate.accept(bad,bad.observed,out));EXPECT_EQ(gate.error(),"native_release_ack");
}
TEST(M7NativeAdmission, TerminalProtectionUsesOriginalActualAfterNormalCreditsClose) {
    Trace trace(false,true);native::Admission gate(42,trace.inputs.front().observed);native::Output out;
    for(unsigned i=0;i<trace.inputs.size();++i) {
        const auto& in=trace.inputs[i];ASSERT_TRUE(gate.accept(in,in.observed,out))<<gate.error()<<" index="<<i;
        if(i>=200) {
            EXPECT_TRUE(out.protection);EXPECT_FALSE(out.normal);EXPECT_EQ(in.credit_mask,0U);
            EXPECT_LE(in.observed+native::step-out.oldest_actuator,30*ms);
            if(i>220){EXPECT_EQ(out.torque,0);EXPECT_GE(out.pressure,1000000);}
        }
    }
}
TEST(M7NativeAdmission, ProtectionCannotHideMissingOriginSessionOrReopenNormal) {
    Trace trace(false,true),normal;
    std::vector<std::function<void(native::Input&)>> faults={
        [](auto& x){x.protection_selected_mask=127;},
        [](auto& x){x.credit_mask=255;},
        [](auto& x){x.protection_since=x.observed+1;},
        [](auto& x){x.protection_since=1;},
        [](auto& x){x.protection_since=x.enable;},
        [](auto& x){x.release[0].reset();},
        [](auto& x){x.actual[1].reset();},
        [&](auto& x){x.actual=normal.inputs[200].actual;},
        [](auto& x){x.normal=true;},
        [](auto& x){x.service_mask=0;}
    };
    for(const auto& fault:faults) {
        native::Admission gate(42,trace.inputs.front().observed);native::Output out;
        for(unsigned i=0;i<200;++i)ASSERT_TRUE(gate.accept(trace.inputs[i],trace.inputs[i].observed,out))<<gate.error();
        auto bad=trace.inputs[200];fault(bad);EXPECT_FALSE(gate.accept(bad,bad.observed,out));
        EXPECT_FALSE(gate.accept(trace.inputs[201],trace.inputs[201].observed,out));
    }
    native::Admission gate(42,trace.inputs.front().observed);native::Output out;
    for(unsigned i=0;i<=200;++i)ASSERT_TRUE(gate.accept(trace.inputs[i],trace.inputs[i].observed,out))<<gate.error();
    EXPECT_FALSE(gate.accept(normal.inputs[201],normal.inputs[201].observed,out));
    EXPECT_EQ(gate.error(),"native_protection_terminal");
}
TEST(M7NativeAdmission, ProtectionKeepsOriginalReceiversAndFrozenSelectionTime) {
    Trace trace(false,true);
    for(unsigned fault=0;fault<4;++fault) {
        native::Admission gate(42,trace.inputs.front().observed);native::Output out;
        for(unsigned i=0;i<220;++i)ASSERT_TRUE(gate.accept(trace.inputs[i],trace.inputs[i].observed,out))<<gate.error();
        auto bad=trace.inputs[220];
        if(fault==0)bad.actual=trace.inputs[200].actual; // replay/stale, valid CRC/P05
        if(fault==1)bad.actual=trace.inputs[221].actual; // future original source
        if(fault==2)++bad.protection_since;
        if(fault==3)mutate(bad.actual[1],[](auto& m){m.from=session::Role::RearZone;});
        EXPECT_FALSE(gate.accept(bad,bad.observed,out))<<fault;
        EXPECT_FALSE(gate.accept(trace.inputs[221],trace.inputs[221].observed,out));
    }
}
} // namespace
