#include "perception_receiver.hpp"
#include <gtest/gtest.h>
#include <limits>

namespace stratadrive::central {
namespace {
constexpr std::uint64_t ms=1000000;
PerceptionFrame frame(std::uint64_t number=1, std::uint64_t source=50*ms) {
    PerceptionFrame f; f.epoch=1; f.clock_instance=7; f.frame=number;
    f.source_ns=source; f.expires_ns=source+kPerceptionLifetimeNs; f.valid=true;
    f.count=1; f.detections[0]={2,0.8,10,20,100,150}; return f;
}
class PerceptionTest:public ::testing::Test {
protected:
    PerceptionReceiver receiver;
    void SetUp() override { ASSERT_TRUE(receiver.start_session(1,7,0)); }
};
TEST_F(PerceptionTest, EmptyValidIsDistinctFromUnavailable) {
    auto f=frame(); f.count=0;
    ASSERT_TRUE(receiver.receive(f,50*ms));
    ASSERT_NE(receiver.snapshot(149*ms),nullptr);
    EXPECT_EQ(receiver.snapshot(149*ms)->count,0U);
    EXPECT_EQ(receiver.snapshot(150*ms),nullptr);
    EXPECT_EQ(receiver.reason(),PerceptionReason::Stale);
}
TEST_F(PerceptionTest, RejectionDoesNotRenewOrResurrectOldOutput) {
    ASSERT_TRUE(receiver.receive(frame(),50*ms));
    EXPECT_FALSE(receiver.receive(frame(),60*ms));
    EXPECT_EQ(receiver.reason(),PerceptionReason::Replay);
    EXPECT_EQ(receiver.snapshot(60*ms),nullptr);
    ASSERT_TRUE(receiver.receive(frame(2,100*ms),100*ms));
    EXPECT_EQ(receiver.snapshot(100*ms)->frame,2U);
}
TEST_F(PerceptionTest, ClockRegressionRequiresExplicitNewEpoch) {
    ASSERT_TRUE(receiver.receive(frame(),50*ms));
    EXPECT_EQ(receiver.snapshot(49*ms),nullptr);
    EXPECT_FALSE(receiver.receive(frame(2,100*ms),100*ms));
    EXPECT_EQ(receiver.reason(),PerceptionReason::Clock);
    EXPECT_FALSE(receiver.start_session(1,8,0));
    EXPECT_FALSE(receiver.start_session(2,7,49*ms));
    ASSERT_TRUE(receiver.start_session(2,8,0));
    auto f=frame();f.epoch=2;f.clock_instance=8;
    EXPECT_TRUE(receiver.receive(f,50*ms));
}
TEST_F(PerceptionTest, RejectedInitIsAtomicAndCannotAdoptSourceSession) {
    ASSERT_TRUE(receiver.receive(frame(),50*ms));
    EXPECT_FALSE(receiver.start_session(2,0,50*ms));
    ASSERT_NE(receiver.snapshot(50*ms),nullptr);
    auto f=frame(2,100*ms);f.epoch=2;
    EXPECT_FALSE(receiver.receive(f,100*ms));
    EXPECT_TRUE(receiver.receive(frame(2,100*ms),100*ms));
}
TEST_F(PerceptionTest, OldestSourceCannotAdvanceByChangingFrameNumber) {
    ASSERT_TRUE(receiver.receive(frame(),50*ms));
    EXPECT_FALSE(receiver.receive(frame(2),60*ms));
    EXPECT_EQ(receiver.reason(),PerceptionReason::Replay);
}
TEST_F(PerceptionTest, OriginalLifetimeCannotBeExtendedOrOverflow) {
    auto f=frame();++f.expires_ns;
    EXPECT_FALSE(receiver.receive(f,50*ms));
    f=frame();--f.expires_ns;
    EXPECT_FALSE(receiver.receive(f,50*ms));
    f=frame(2,std::numeric_limits<std::uint64_t>::max()-10);
    EXPECT_FALSE(receiver.receive(f,f.source_ns));
}
TEST_F(PerceptionTest, FutureAndPreSessionSourcesAreRejected) {
    EXPECT_FALSE(receiver.receive(frame(),49*ms));
    ASSERT_TRUE(receiver.start_session(2,7,60*ms));
    auto f=frame(); f.epoch=2;
    EXPECT_FALSE(receiver.receive(f,60*ms));
}
TEST_F(PerceptionTest, IdentityMutationsInvalidateCurrent) {
    for(int mutation=0;mutation<5;++mutation) {
        auto f=frame(static_cast<std::uint64_t>(mutation+1),static_cast<std::uint64_t>(mutation+1)*50*ms);
        if(mutation==0) f.epoch=2;
        if(mutation==1) f.clock_instance=8;
        if(mutation==2) f.camera_id=2;
        if(mutation==3) f.calibration_revision=2;
        if(mutation==4) f.model_hash[31]^=1;
        EXPECT_FALSE(receiver.receive(f,f.source_ns));
        EXPECT_EQ(receiver.reason(),PerceptionReason::Identity);
        EXPECT_EQ(receiver.snapshot(f.source_ns),nullptr);
    }
}
TEST_F(PerceptionTest, ShapeScoreClassAndAllBoxesAreValidated) {
    for(int mutation=0;mutation<11;++mutation) {
        auto f=frame(static_cast<std::uint64_t>(mutation+1),static_cast<std::uint64_t>(mutation+1)*50*ms);
        switch(mutation) {
        case 0:f.schema=2;break;
        case 1:f.valid=false;break;
        case 2:f.count=101;break;
        case 3:f.width=639;break;
        case 4:f.height=383;break;
        case 5:f.detections[0].score=std::numeric_limits<double>::quiet_NaN();break;
        case 6:f.detections[0].score=0.34;break;
        case 7:f.detections[0].class_id=4;break;
        case 8:f.detections[0].x1=-1;break;
        case 9:f.detections[0].x2=10;break;
        default:f.count=100;f.detections.fill(f.detections[0]);f.detections[99].y2=385;break;
        }
        EXPECT_FALSE(receiver.receive(f,f.source_ns)) << mutation;
        EXPECT_EQ(receiver.reason(),PerceptionReason::Invalid) << mutation;
    }
}
TEST_F(PerceptionTest, BoundedMaximumAndImageEdgesAreAccepted) {
    auto f=frame(); f.count=kMaxDetections;f.detections.fill({0,0.35,0,0,640,384});
    EXPECT_TRUE(receiver.receive(f,50*ms));
}
TEST(PerceptionNoSessionTest, DataNeverStartsSession) {
    PerceptionReceiver receiver;
    EXPECT_FALSE(receiver.receive(frame(),50*ms));
    EXPECT_EQ(receiver.snapshot(50*ms),nullptr);
}
} // namespace
} // namespace stratadrive::central
