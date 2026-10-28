#include "wall_rig.hpp"
#include "owner_wire.hpp"
#include "wall_mailbox.hpp"
#include <gtest/gtest.h>
#include <thread>

namespace {
using namespace stratadrive;
using namespace m7_functional;
constexpr Time start=1000000000000ULL;
WallReceipt receipt(unsigned i) {
    m7_external::SolverWork w;
    w.frame=100+i;w.begin=start+(i-1)*10*ms;w.end=start+i*10*ms;
    w.oldest=w.begin;w.dt=double(.01f*(1.f/320.f));
    w.wheel={0,{7,99+i,w.begin},w.begin};
    return {{99,w.frame,w.end,{0,0,0,0}},w,wall_domain};
}
TEST(M7WallOwner, NewInitRunsAtOriginalRatesWithoutLogicalReplay) {
    WallRig rig({1,42,7},99,start);
    WallReport r;
    for(unsigned i=1;i<=1500;++i) {
        r=rig.service(start+i*ms,i%10==0?std::optional<WallReceipt>(receipt(i/10)):std::nullopt);
        ASSERT_FALSE(r.failed)<<i<<" "<<r.reason;
    }
    ASSERT_TRUE(r.native.armed);EXPECT_EQ(r.native.release_mask,255U);EXPECT_EQ(r.native.credit_mask,255U);
    ASSERT_TRUE(r.native.native_export);
    for(const auto& p:r.native.native_export->actual) {
        ASSERT_TRUE(p);const auto wire=remote::decode_owner_message(p->bytes.data(),p->size);
        ASSERT_TRUE(wire);EXPECT_EQ(wire->clock_domain,wall_domain);
    }
    EXPECT_LE(r.native.controller_releases,75U);
    EXPECT_GE(r.native.controller_releases,65U);
    EXPECT_EQ(r.native.electrical->end,start+1500*ms);
}
TEST(M7WallOwner, MissingReceiptKeepsServiceAndProtectiveResponseRunning) {
    WallRig rig({1,42,7},99,start);
    WallReport r;
    for(unsigned i=1;i<=1500;++i) {
        r=rig.service(start+i*ms,i%10==0?std::optional<WallReceipt>(receipt(i/10)):std::nullopt);
        ASSERT_FALSE(r.failed)<<i<<" "<<r.reason;
    }
    ASSERT_TRUE(r.native.armed);
    const auto last_wheel=r.native.sensor_wheel->source;
    const auto energy=r.native.electrical->end;
    unsigned fresh=0;Time previous=0;
    for(unsigned i=1501;i<=1800;++i) {
        r=rig.service(start+i*ms);
        EXPECT_EQ(r.native.electrical->end,energy);
        EXPECT_EQ(r.native.sensor_wheel->source,last_wheel);
        EXPECT_EQ(r.native.service_mask,255U);
        if(r.native.actual_sources[1]>previous) {previous=r.native.actual_sources[1];++fresh;}
    }
    EXPECT_TRUE(r.failed);EXPECT_FALSE(r.native.armed);EXPECT_EQ(r.native.credit_mask,0U);
    EXPECT_EQ(r.native.native_export->protection_selected_mask,255U);
    EXPECT_GE(fresh,25U);
    const auto& p=r.native.native_export->actual[1];ASSERT_TRUE(p);
    const auto m=remote::decode_owner_message(p->bytes.data(),p->size);ASSERT_TRUE(m);
    const auto b=can::decode_brake_frame(std::get<can::BrakeFrame>(std::get<transport::Feedback>(m->payload)));
    ASSERT_TRUE(b);EXPECT_EQ(b->origin,can::ActuatorOrigin::LocalProtection);
    ASSERT_TRUE(b->pressure_pa);EXPECT_GE(*b->pressure_pa,1000000);
}
TEST(M7WallOwner, SimulationTimestampAndDuplicateReceiptCannotBecomeWallSensors) {
    for(unsigned fault=0;fault<4;++fault) {
        WallRig rig({1,42,7},99,start);
        for(unsigned i=1;i<10;++i)rig.service(start+i*ms);
        auto x=receipt(1);
        if(fault==0)x.wheel.source=1000000000; // simulation time, not local wall
        if(fault==1)++x.work.frame;
        if(fault==3)x.clock=domain;
        auto r=rig.service(start+10*ms,x);
        if(fault==2)r=rig.service(start+11*ms,x);
        EXPECT_TRUE(r.failed);EXPECT_FALSE(r.native.armed);
        EXPECT_EQ(r.native.electrical->end,fault==2?start+10*ms:0U);
    }
}
TEST(M7WallOwner, NoCatchupControllerReleasesAndSingleMutationOwner) {
    WallRig rig({1,42,7},99,start);
    WallReport first;
    for(unsigned i=1;i<=1100;++i)
        first=rig.service(start+i*ms,i%10==0?std::optional<WallReceipt>(receipt(i/10)):std::nullopt);
    ASSERT_TRUE(first.native.armed);
    auto delayed=rig.service(start+1125*ms);
    EXPECT_TRUE(delayed.failed);
    EXPECT_LE(delayed.native.controller_releases-first.native.controller_releases,1U);
    for(const auto body:delayed.native.leaf_body)EXPECT_EQ(body,start+1125*ms);
    bool rejected=false;
    std::thread other([&]{try {rig.service(start+1126*ms);}catch(const std::runtime_error&) {rejected=true;}});
    other.join();EXPECT_TRUE(rejected);
    EXPECT_THROW(rig.service(start+1125*ms),std::runtime_error);
}
TEST(M7WallOwner, FaultDoesNotDiscardCompletedWorkOrReopenNormalAuthority) {
    WallRig rig({1,42,7},99,start);
    WallReport r;
    for(unsigned i=1;i<=1100;++i) {
        r=rig.service(start+i*ms,i%10==0?std::optional<WallReceipt>(receipt(i/10)):std::nullopt);
        ASSERT_FALSE(r.failed)<<i<<' '<<r.reason;
    }
    ASSERT_TRUE(r.native.armed);
    rig.protect("in-flight injected authority fault");
    for(unsigned i=1101;i<=1200;++i) {
        r=rig.service(start+i*ms,i%10==0?std::optional<WallReceipt>(receipt(i/10)):std::nullopt);
        ASSERT_TRUE(r.failed);ASSERT_FALSE(r.native.armed);EXPECT_EQ(r.native.credit_mask,0U);
    }
    EXPECT_EQ(r.native.electrical->end,start+1200*ms);
    EXPECT_EQ(r.native.native_export->protection_selected_mask,255U);
}
TEST(M7WallOwner, CompletedWorkIsVisibleBeforeOwnerServiceWithTimerJitter) {
    for(unsigned phase=0;phase<8;++phase) {
        WallRig rig({1,42,7},99,start);
        WallReport r;
        for(unsigned i=1;i<=1500;++i) {
            const auto jitter=40000+((i*7919U+phase*3019U)%20000U);
            const bool delivered=i>=10+phase && (i-phase)%10==0;
            r=rig.service(start+i*ms+jitter,delivered?std::optional<WallReceipt>(receipt((i-phase)/10)):std::nullopt);
            ASSERT_FALSE(r.failed)<<"phase "<<phase<<" ms "<<i<<" "<<r.reason;
        }
        EXPECT_TRUE(r.native.armed)<<phase;
    }
}
TEST(M7WallOwner, InitPhaseStartsAfterSettledWorkWithoutChangingReceiptTimes) {
    WallRig rig({1,42,7},99,start);
    WallReport r;
    for(unsigned i=1;i<=1500;++i) {
        // Subsequent receipts arrive 1ms late. INIT is phased after the
        // first committed work instead of on its acquisition boundary.
        const auto jitter=i==10?50000:60000;
        const bool delivered=i==10 || (i>20 && i%10==1);
        r=rig.service(start+i*ms+jitter,delivered?std::optional<WallReceipt>(receipt(i/10)):std::nullopt);
        ASSERT_FALSE(r.failed)<<i<<' '<<r.reason;
    }
    ASSERT_TRUE(r.native.armed);
    EXPECT_EQ(r.native.native_export->enable,start+32*ms+60000);
    EXPECT_EQ(r.native.release_mask,255U);
}
TEST(M7WallOwner, MissingSafeInitEvidenceNeverExtendsDeadlineOrCreatesAck) {
    WallRig rig({1,42,7},99,start);
    WallReport r;
    for(unsigned i=1;i<=80;++i) {
        r=rig.service(start+i*ms+60000,i==10?std::optional<WallReceipt>(receipt(1)):std::nullopt);
    }
    EXPECT_TRUE(r.failed);EXPECT_FALSE(r.native.armed);EXPECT_EQ(r.native.release_mask,0U);
    EXPECT_LE(r.protected_at,start+53*ms);
}
TEST(M7WallMailbox, OverflowLatchesWithoutOverwritingUnsettledReceipts) {
    WallMailbox<WallReceipt,2> inbox;
    ASSERT_TRUE(inbox.push(receipt(1)));ASSERT_TRUE(inbox.push(receipt(2)));
    EXPECT_FALSE(inbox.push(receipt(3)));EXPECT_TRUE(inbox.failed());
    EXPECT_EQ(inbox.pop()->work.frame,101U);EXPECT_EQ(inbox.pop()->work.frame,102U);
    EXPECT_FALSE(inbox.pop());EXPECT_FALSE(inbox.push(receipt(4)));
}
TEST(M7WallMailbox, ConcurrentDeliveryPreservesReceiptContentsAndOrder) {
    WallMailbox<WallReceipt,128> inbox;
    std::thread producer([&]{for(unsigned i=1;i<=100;++i)ASSERT_TRUE(inbox.push(receipt(i)));});
    for(unsigned i=1;i<=100;++i) {
        std::optional<WallReceipt> x;
        while(!(x=inbox.pop()))std::this_thread::yield();
        EXPECT_EQ(x->work.frame,100+i);EXPECT_EQ(x->work.end,start+i*10*ms);
    }
    producer.join();EXPECT_FALSE(inbox.failed());
}
}
