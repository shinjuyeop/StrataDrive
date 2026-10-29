#include "wall_rig.hpp"
#include "wall_bridge.hpp"
#include <gtest/gtest.h>
#include <atomic>
#include <thread>
using namespace stratadrive;
namespace {
using namespace m7_functional;
constexpr Time start=1000000000000ULL;
m7_native::Input input(const Report& r) {
    m7_native::Input in;const auto& e=*r.native_export;
    in.observed=e.observed;in.enable=e.enable;in.normal=e.normal;in.protection_since=e.protection_since;
    in.protection_selected_mask=e.protection_selected_mask;in.actual=e.actual;in.commands=e.commands;
    in.release=e.release;in.credit=e.credit;in.permission=e.permission;
    in.release_mask=r.release_mask;in.credit_mask=r.credit_mask;in.service_mask=r.service_mask;return in;
}
WallReceipt sample(unsigned i) {
    m7_external::SolverWork w;w.frame=100+i;w.begin=start+(i-1)*10*ms;w.end=w.begin+10*ms;
    w.oldest=w.begin;w.dt=double(.01f*(1.f/320.f));w.wheel={0,{7,99+i,w.begin},w.begin};
    return {{99,w.frame,w.end,{0,0,0,0}},w,wall_domain};
}
TEST(M7WallAdmission, NormalThenZeroTorqueProtectionWithoutInventingFreshWheel) {
    WallRig rig({1,42,7},99,start);m7_native::Admission gate(42,start,m7_native::ClockPolicy::HostMonotonic);
    unsigned normals=0,protected_frames=0;Time original_wheel=0;
    for(unsigned i=1;i<=1800;++i) {
        if(i==1501)rig.protect("test delivery outage");
        auto r=rig.service(start+i*ms,i<=1500 && i%10==0?std::optional<WallReceipt>(sample(i/10)):std::nullopt);
        if(i<=1500){ASSERT_FALSE(r.failed)<<r.reason;}
        const auto in=input(r.native);m7_native::Output out;
        if(!gate.eligible(in,start+i*ms,out))continue;
        ASSERT_TRUE(gate.accept(in,start+i*ms,out))<<gate.error();
        normals+=out.normal;protected_frames+=out.protection;
        if(i==1500)original_wheel=r.native.sensor_wheel->source;
        if(i>1600 && out.protection){EXPECT_EQ(out.torque,0);EXPECT_EQ(r.native.sensor_wheel->source,start+1500*ms);}
    }
    EXPECT_GT(normals,100U);EXPECT_GT(protected_frames,50U);EXPECT_NE(original_wheel,0U);
}
TEST(M7WallAdmission, FunctionalGateCannotAcceptMonotonicInit) {
    WallRig rig({1,42,7},99,start);m7_native::Admission gate(42,start);
    for(unsigned i=1;i<=100;++i) {
        const auto r=rig.service(start+i*ms,i%10==0?std::optional<WallReceipt>(sample(i/10)):std::nullopt);
        if(i==100){m7_native::Output out;EXPECT_FALSE(gate.accept(input(r.native),start+i*ms,out));}
    }
}
TEST(M7WallAdmission, InitFaultCannotInventMissingProtectiveActual) {
    WallRig rig({1,42,7},99,start);m7_native::Admission gate(42,start,m7_native::ClockPolicy::HostMonotonic);
    unsigned accepted_init=0,protected_frames=0;std::string why;
    for(unsigned i=1;i<=400;++i) {
        if(i==101)rig.protect("startup sensor outage");
        auto r=rig.service(start+i*ms,i<=100 && i%10==0?std::optional<WallReceipt>(sample(i/10)):std::nullopt);
        auto in=input(r.native);m7_native::Output out;
        if(!gate.eligible(in,start+i*ms,out,&why))continue;
        ASSERT_TRUE(gate.accept(in,start+i*ms,out))<<gate.error();
        EXPECT_FALSE(out.normal);
        accepted_init+=!out.empty;
        protected_frames+=out.protection;
    }
    EXPECT_GT(accepted_init,0U);EXPECT_EQ(protected_frames,0U);
    EXPECT_EQ(why,"native_protection_authority");
}
TEST(M7SharedChannel, ConcurrentCopiesCannotTearAndCachedReadKeepsOriginalIdentity) {
    struct Value {std::uint64_t sequence;std::uint64_t elements[320];};
    m7_native::SharedLatest<Value> channel;
    m7_native::SharedWriter<Value> writer;m7_native::SharedReader<Value> reader;
    std::atomic<bool> done{false};
    std::thread thread([&]{for(std::uint64_t i=1;i<=50000;++i){Value v{};v.sequence=i;for(auto& x:v.elements)x=i;writer.publish(channel,v);}done.store(true);});
    std::uint64_t previous=0;unsigned reads=0;
    do {Value v{};if(reader.read(channel,v)){EXPECT_GE(v.sequence,previous);for(auto x:v.elements)EXPECT_EQ(x,v.sequence);previous=v.sequence;++reads;}}while(!done.load());
    thread.join();Value a{},b{};ASSERT_TRUE(reader.read(channel,a));ASSERT_TRUE(reader.read(channel,b));
    EXPECT_EQ(a.sequence,50000U);EXPECT_EQ(b.sequence,a.sequence);EXPECT_GT(reads,0U);
}
TEST(M7SharedChannel, BoundIdentityRejectsOtherRunSessionGenerationAndOldAbi) {
    m7_native::WallBridge b;const std::string run="01234567-89ab-cdef-0123-456789abcdef";
    b.signal={m7_native::wall_signal_magic,start,42,0};b.actor=99;b.model_initial=1000000000;
    b.session=3;b.generation=5;std::memcpy(b.run,run.c_str(),37);
    const auto valid=[&]{return m7_native::bridge_identity(b,42,start,99,1000000000,3,5,run);};
    ASSERT_TRUE(valid());
    ++b.session;EXPECT_FALSE(valid());--b.session;
    ++b.generation;EXPECT_FALSE(valid());--b.generation;
    b.run[0]='f';EXPECT_FALSE(valid());b.run[0]='0';
    b.abi=1;EXPECT_FALSE(valid());b.abi=2;EXPECT_FALSE(valid());b.abi=3;
    b.model_step=5000000;EXPECT_FALSE(valid());
    EXPECT_TRUE(m7_native::bridge_identity(b,42,start,99,1000000000,3,5,run,5000000));
    b.model_step=10000000;
    ++b.actor;EXPECT_FALSE(valid());--b.actor;
    ++b.model_initial;EXPECT_FALSE(valid());--b.model_initial;
    EXPECT_TRUE(valid());m7_native::wall_trip(&b.signal);EXPECT_FALSE(valid());
}
// The old standalone owner tests supplied a new receipt even when admission
// would have refused physics. Here a receipt exists ONLY after an accepted
// step. This exposes the feedback/admission circular wait without an engine.
TEST(M7WallAdmission, CoupledFiveMsPlantProgressWithoutRelaxingNativeBudgets) {
    for(const Time step:{10*ms,5*ms}) {
        constexpr Time model=1000000000;
        WallRig rig({1,42,7},99,start,model,step);
        m7_native::Admission gate(42,start,m7_native::ClockPolicy::HostMonotonic,step);
        std::optional<WallReceipt> pending;
        Time due=start+step;unsigned frames=0,normal=0;WallReport r;
        for(unsigned i=1;i<=4000;++i) {
            const auto now=start+i*ms+50000+(i*7919U)%20000;
            r=rig.service(now,pending);pending.reset();
            if(r.failed)break;
            if(now<due)continue;
            const auto in=input(r.native);m7_native::Output out;
            if(!gate.eligible(in,now,out,nullptr,4*ms))continue;
            ASSERT_TRUE(gate.accept(in,now,out))<<gate.error();
            ++frames;normal+=out.normal;
            if(!out.empty){EXPECT_LE(now+step-out.oldest_actuator,30*ms);}
            // 5ms is an absolute plant release grid; the native owner above
            // still runs exactly once at NOW, never replays ECU invocations.
            due=step==5*ms?start+(frames+1)*step:now+step;
            m7_external::CarlaWork c;auto& w=c.work;
            w.frame=100+frames;w.begin=model+(frames-1)*step;w.end=w.begin+step;w.oldest=w.begin;
            w.dt=double((step==5*ms?.005f:.01f)*(1.f/320.f));
            w.wheel={0,{7,99+frames,w.begin},w.begin};w.torque=out.torque;
            c.applied=now;c.acquired_begin=now+500000;c.acquired_end=c.acquired_begin+1000;
            c.oldest=out.oldest_actuator?out.oldest_actuator:now;c.coils=r.native.coils;c.coil_source=r.native.coil_source;
            pending=WallReceipt{{99,w.frame,c.acquired_begin,{0,0,0,0}},w,wall_domain,c};
        }
        if(step==5*ms) {
            EXPECT_FALSE(r.failed)<<r.reason;EXPECT_EQ(frames,800U);EXPECT_GT(normal,600U);
            EXPECT_LE(r.native.controller_releases,200U);
        } else {EXPECT_TRUE(r.failed);EXPECT_EQ(normal,0U);}
    }
}
TEST(M7WallAdmission, FiveMsIsNotAnImplicitFunctionalClockChange) {
    m7_native::Admission gate(42,start,m7_native::ClockPolicy::Functional,5*ms);
    m7_native::Input in;in.observed=start;in.service_mask=255;m7_native::Output out;
    EXPECT_FALSE(gate.accept(in,start,out));
    EXPECT_THROW(WallRig(Scope{1,42,7},99,start,0,5*ms),std::runtime_error);
}
TEST(M7WallAdmission, ReceptionContinuesAcrossPlantGapWithoutGrantingTicks) {
    WallRig rig({1,42,7},99,start);m7_native::Admission gate(42,start,m7_native::ClockPolicy::HostMonotonic,5*ms);
    unsigned normal=0,protected_frames=0,ingress=0;Time old_source=0;
    for(unsigned i=1;i<=1800;++i) {
        if(i==1501)rig.protect("test physics withholding");
        const auto r=rig.service(start+i*ms,i<=1500 && i%10==0?std::optional<WallReceipt>(sample(i/10)):std::nullopt);
        const auto in=input(r.native);m7_native::Output out;
        if(gate.started()){ASSERT_TRUE(gate.ingest(in,start+i*ms))<<gate.error();++ingress;}
        if(i==1500)old_source=r.native.sensor_wheel->source;
        if(i>1500 && i<=1600)continue; // receive, but deliberately no physics admission
        if(!gate.eligible(in,start+i*ms,out,nullptr,4*ms))continue;
        ASSERT_TRUE(gate.accept(in,start+i*ms,out))<<gate.error();
        normal+=out.normal;protected_frames+=out.protection;
        if(i>1600 && out.protection) {
            EXPECT_EQ(out.torque,0);EXPECT_EQ(r.native.sensor_wheel->source,old_source);
        }
    }
    EXPECT_GT(normal,100U);EXPECT_GT(protected_frames,100U);EXPECT_GT(ingress,1500U);
}
}
