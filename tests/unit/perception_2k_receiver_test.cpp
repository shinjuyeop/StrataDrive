#include "perception_2k_receiver.hpp"
#include <gtest/gtest.h>
#include <cmath>
#include <limits>

namespace stratadrive::central {
namespace {
constexpr std::uint64_t ms=1000000, wall=9000000000000;
Native2kNow time_at(std::uint64_t source,std::uint64_t elapsed) { return {source*ms,wall+elapsed*ms,wall+elapsed*ms}; }
Native2kFrame frame(std::uint64_t number=1,std::uint64_t source=50,std::uint64_t receipt=55) {
    Native2kFrame f;f.epoch=1;f.source_clock=7;f.wall_clock=8;f.frame=number;
    f.source_ns=source*ms;f.expires_ns=f.source_ns+kPerceptionLifetimeNs;
    f.received_wall_ns=wall+receipt*ms;f.wall_expires_ns=f.received_wall_ns+kPerceptionLifetimeNs;
    f.count=1;f.detections[0]={2,.8,0,0,2560,1536};f.valid=true;return f;
}
class Native2kTest:public ::testing::Test {
protected:
    Native2kReceiver receiver;
    void SetUp() override { ASSERT_TRUE(receiver.start_session({1,7,8,0,wall})); }
};
TEST(Native2kNoSession, ImagesCannotIssueSession) {
    Native2kReceiver receiver;EXPECT_FALSE(receiver.receive(frame(),time_at(50,60)));
    EXPECT_EQ(receiver.reason(),Native2kReason::Session);
}
TEST_F(Native2kTest, EmptyValidIsAvailableButNoTracksOrPermission) {
    auto f=frame();f.count=0;ASSERT_TRUE(receiver.receive(f,time_at(50,60)));
    const auto* p=receiver.snapshot(time_at(149,154));ASSERT_NE(p,nullptr);EXPECT_EQ(p->count,0U);
    EXPECT_EQ(receiver.tracks().count,0U);EXPECT_EQ(p->source_ns,50*ms);EXPECT_EQ(p->received_wall_ns,wall+55*ms);
    EXPECT_EQ(receiver.snapshot(time_at(150,154)),nullptr);
    EXPECT_EQ(receiver.reason(),Native2kReason::SourceExpired);
}
TEST_F(Native2kTest, PausedSimulationStillExpiresAtOriginalReceipt) {
    ASSERT_TRUE(receiver.receive(frame(),time_at(50,60)));
    ASSERT_NE(receiver.snapshot(time_at(50,154)),nullptr);
    EXPECT_EQ(receiver.snapshot(time_at(50,155)),nullptr);
    EXPECT_EQ(receiver.reason(),Native2kReason::ReceiptExpired);
    EXPECT_EQ(receiver.tracks().count,0U);
}
TEST_F(Native2kTest, RepeatedPollDoesNotRenewEitherClockOrTrackHistory) {
    ASSERT_TRUE(receiver.receive(frame(),time_at(50,60)));
    for(unsigned i=60;i<150;++i) {
        const auto* p=receiver.snapshot(time_at(i,i));ASSERT_NE(p,nullptr);
        EXPECT_EQ(p->expires_ns,150*ms);EXPECT_EQ(p->wall_expires_ns,wall+155*ms);
        EXPECT_EQ(receiver.tracks().tracks[0].count,1U);
    }
    EXPECT_EQ(receiver.snapshot(time_at(150,150)),nullptr);
}
TEST_F(Native2kTest, BothClocksAndStateReceiptRegressionLatch) {
    for(unsigned variant=0;variant<4;++variant) {
        Native2kReceiver r;ASSERT_TRUE(r.start_session({1,7,8,0,wall}));
        ASSERT_TRUE(r.receive(frame(),time_at(50,60)));
        auto now=time_at(60,70);
        if(variant==0)now.source_ns=49*ms;
        if(variant==1)now.wall_ns=wall+59*ms;
        if(variant==2)now.state_received_wall_ns=wall+59*ms;
        if(variant==3)now.state_received_wall_ns=wall+71*ms;
        EXPECT_EQ(r.snapshot(now),nullptr);EXPECT_EQ(r.reason(),Native2kReason::Clock);
        EXPECT_FALSE(r.receive(frame(2,100,105),time_at(100,110)));
        EXPECT_FALSE(r.start_session({1,9,10,0,0}));
        EXPECT_TRUE(r.start_session({2,9,10,0,0}));
    }
}
TEST_F(Native2kTest, StateSilenceClearsAndNeedsANewAcquisition) {
    auto f=frame(1,50,149);ASSERT_TRUE(receiver.receive(f,{50*ms,wall+149*ms,wall+50*ms}));
    EXPECT_EQ(receiver.snapshot({50*ms,wall+150*ms,wall+50*ms}),nullptr);
    EXPECT_EQ(receiver.reason(),Native2kReason::StateStale);
    EXPECT_FALSE(receiver.receive(f,time_at(60,151)));EXPECT_EQ(receiver.reason(),Native2kReason::Replay);
    EXPECT_TRUE(receiver.receive(frame(2,100,155),time_at(100,155)));
}
TEST_F(Native2kTest, RejectedInitPreservesCurrentAndMonotonicDomains) {
    ASSERT_TRUE(receiver.receive(frame(),time_at(50,60)));
    EXPECT_FALSE(receiver.start_session({2,7,8,49*ms,wall+60*ms}));
    EXPECT_FALSE(receiver.start_session({2,9,8,0,wall+59*ms}));
    EXPECT_FALSE(receiver.start_session({2,7,0,50*ms,wall+60*ms}));
    EXPECT_FALSE(receiver.start_session({1,9,10,0,0}));
    ASSERT_NE(receiver.snapshot(time_at(50,60)),nullptr);
    EXPECT_EQ(receiver.tracks().count,1U);
}
TEST_F(Native2kTest, IdentityLayoutAndEveryDetectionFailClosed) {
    for(unsigned variant=0;variant<19;++variant) {
        auto f=frame(variant+1,50+variant,55+variant);
        switch(variant) {
        case 0:++f.epoch;break;case 1:++f.source_clock;break;case 2:++f.wall_clock;break;
        case 3:++f.camera_id;break;case 4:++f.calibration_revision;break;case 5:f.model_hash[0]^=1;break;
        case 6:++f.schema;break;case 7:++f.candidate;break;case 8:f.width=3840;break;case 9:f.height=384;break;
        case 10:f.count=101;break;case 11:f.valid=false;break;case 12:f.frame=0;break;
        case 13:f.detections[0].score=.59;break;case 14:f.detections[0].class_id=4;break;
        case 15:f.detections[0].y2=1537;break;case 16:f.detections[0].x1=-1;break;
        case 17:f.detections[0].x2=0;break;
        default:f.count=100;f.detections.fill(f.detections[0]);f.detections[99].score=std::numeric_limits<double>::quiet_NaN();break;
        }
        EXPECT_FALSE(receiver.receive(f,time_at(50+variant,60+variant)))<<variant;
        EXPECT_EQ(receiver.snapshot(time_at(50+variant,60+variant)),nullptr);
        EXPECT_EQ(receiver.tracks().count,0U);
    }
}
TEST_F(Native2kTest, ClassThresholdsAndAllImageEdgesAreExact) {
    const std::array<std::pair<unsigned,double>,6> thresholds{{{0,.6},{1,.4},{2,.6},{3,.5},{5,.5},{7,.6}}};
    std::uint64_t seq=1;
    for(const auto& item:thresholds) {
        auto f=frame(seq,seq,seq);++seq;
        f.count=100;f.detections.fill({item.first,item.second,0,0,2560,1536});
        ASSERT_TRUE(receiver.receive(f,time_at(seq,seq)));
        EXPECT_EQ(receiver.tracks().count,100U);
        f=frame(seq,seq,seq);++seq;f.detections[0].class_id=item.first;
        f.detections[0].score=std::nextafter(item.second,0.);
        EXPECT_FALSE(receiver.receive(f,time_at(seq,seq)));
    }
}
TEST_F(Native2kTest, DeadlineMutationFutureAndOverflowRejectedInBothDomains) {
    for(unsigned variant=0;variant<8;++variant) {
        auto f=frame(variant+1);
        switch(variant) {
        case 0:++f.expires_ns;break;case 1:--f.expires_ns;break;
        case 2:++f.wall_expires_ns;break;case 3:--f.wall_expires_ns;break;
        case 4:f.source_ns=51*ms;f.expires_ns=f.source_ns+kPerceptionLifetimeNs;break;
        case 5:f.received_wall_ns=wall+61*ms;f.wall_expires_ns=f.received_wall_ns+kPerceptionLifetimeNs;break;
        case 6:f.source_ns=std::numeric_limits<std::uint64_t>::max()-1;f.expires_ns=1;break;
        default:f.received_wall_ns=std::numeric_limits<std::uint64_t>::max()-1;f.wall_expires_ns=1;break;
        }
        EXPECT_FALSE(receiver.receive(f,time_at(50,60)))<<variant;
    }
}
TEST_F(Native2kTest, DuplicateChangedPayloadAndStaleRecoveryCannotResurrectOldFrame) {
    ASSERT_TRUE(receiver.receive(frame(),time_at(50,60)));
    auto duplicate=frame();duplicate.detections[0].score=.99;
    EXPECT_FALSE(receiver.receive(duplicate,time_at(50,61)));
    EXPECT_EQ(receiver.reason(),Native2kReason::Replay);
    EXPECT_EQ(receiver.snapshot(time_at(50,61)),nullptr);
    EXPECT_FALSE(receiver.receive(frame(2,50,62),time_at(50,62)));
    EXPECT_TRUE(receiver.receive(frame(3,51,63),time_at(51,63)));
    receiver.unavailable(time_at(51,64));EXPECT_EQ(receiver.tracks().count,0U);
    EXPECT_FALSE(receiver.receive(frame(3,51,63),time_at(51,65)));
}
TEST_F(Native2kTest, TrackHistoryIsBoundedAndNewFrameOnly) {
    for(std::uint64_t i=1;i<=12;++i)ASSERT_TRUE(receiver.receive(frame(i,i*10,i*10),time_at(i*10,i*10)));
    const auto& t=receiver.tracks().tracks[0];EXPECT_EQ(t.id,1U);ASSERT_EQ(t.count,10U);
    EXPECT_EQ(t.history[0].frame,3U);EXPECT_EQ(t.history[9].frame,12U);
    EXPECT_EQ(t.history[9].detection.x2,2560);
}
TEST_F(Native2kTest, ClassChangesAndEmptyFramesDoNotCoast) {
    ASSERT_TRUE(receiver.receive(frame(),time_at(50,60)));
    auto next=frame(2,75,80);next.detections[0].class_id=0;
    ASSERT_TRUE(receiver.receive(next,time_at(75,80)));EXPECT_EQ(receiver.tracks().tracks[0].id,2U);
    next=frame(3,90,95);next.count=0;ASSERT_TRUE(receiver.receive(next,time_at(90,95)));
    EXPECT_EQ(receiver.tracks().count,0U);
    ASSERT_TRUE(receiver.receive(frame(4,100,105),time_at(100,105)));
    EXPECT_EQ(receiver.tracks().tracks[0].id,3U);EXPECT_EQ(receiver.tracks().tracks[0].count,1U);
}
TEST_F(Native2kTest, MatchingIsOneToOneAndDeterministicOnTies) {
    auto f=frame();f.count=2;f.detections[1]=f.detections[0];ASSERT_TRUE(receiver.receive(f,time_at(50,60)));
    f=frame(2,75,80);f.count=3;f.detections[1]=f.detections[2]=f.detections[0];
    ASSERT_TRUE(receiver.receive(f,time_at(75,80)));
    for(unsigned i=0;i<3;++i) {
        EXPECT_EQ(receiver.tracks().tracks[i].id,i+1);
        EXPECT_EQ(receiver.tracks().tracks[i].count,i<2?2U:1U);
    }
}
TEST_F(Native2kTest, ExpiredHistoryAndNewSessionNeverContinueOldTrack) {
    ASSERT_TRUE(receiver.receive(frame(),time_at(50,60)));
    ASSERT_TRUE(receiver.receive(frame(2,100,155),time_at(100,155)));
    EXPECT_EQ(receiver.tracks().tracks[0].id,2U);EXPECT_EQ(receiver.tracks().tracks[0].count,1U);
    ASSERT_TRUE(receiver.start_session({2,7,8,100*ms,wall+155*ms}));
    auto f=frame(1,110,160);f.epoch=2;ASSERT_TRUE(receiver.receive(f,time_at(110,160)));
    EXPECT_EQ(receiver.tracks().tracks[0].id,1U);EXPECT_EQ(receiver.tracks().tracks[0].count,1U);
}
} // namespace
} // namespace stratadrive::central
