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
    b.abi=1;EXPECT_FALSE(valid());b.abi=2;
    ++b.actor;EXPECT_FALSE(valid());--b.actor;
    ++b.model_initial;EXPECT_FALSE(valid());--b.model_initial;
    EXPECT_TRUE(valid());m7_native::wall_trip(&b.signal);EXPECT_FALSE(valid());
}
}
