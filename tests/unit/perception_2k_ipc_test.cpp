#include "perception_2k_ipc.hpp"
#include <gtest/gtest.h>
#include <cstring>
#include <memory>
#include <sys/socket.h>
#include <unistd.h>

namespace {
using namespace stratadrive::central;
constexpr std::uint64_t ms=1000000,wall=9000000000;
PerceptionIpcMessage message(std::uint64_t sequence=1,std::uint64_t frame=5) {
    PerceptionIpcMessage m;m.kind=PerceptionIpcKind::Result;m.sequence=sequence;m.epoch=42;
    m.source_clock=77;m.wall_clock=88;m.sender_wall_ns=wall+frame*10*ms;
    m.state_frame=frame;m.observed={frame*10*ms,0,m.sender_wall_ns};
    auto& f=m.result;f.epoch=42;f.source_clock=77;f.wall_clock=88;f.frame=frame;
    f.source_ns=m.observed.source_ns;f.expires_ns=f.source_ns+kPerceptionLifetimeNs;
    f.received_wall_ns=m.sender_wall_ns;f.wall_expires_ns=f.received_wall_ns+kPerceptionLifetimeNs;
    f.count=1;f.detections[0]={2,.8,0,0,2560,1536};f.valid=true;return m;
}
class Ipc2k:public ::testing::Test {
protected:
    int sender=-1;std::unique_ptr<PerceptionIpcShadow> receiver;
    void SetUp() override {
        int pair[2];ASSERT_EQ(socketpair(AF_UNIX,SOCK_SEQPACKET|SOCK_NONBLOCK,0,pair),0);
        sender=pair[0];receiver=std::make_unique<PerceptionIpcShadow>(pair[1],42,77,88);
        ASSERT_TRUE(receiver->observe_native_init(42,wall));
    }
    void TearDown() override {if(sender>=0)close(sender);}
    void send(const PerceptionIpcMessage& m) {
        std::array<std::uint8_t,kPerceptionIpcMax> bytes{};const auto n=encode_perception_ipc(m,bytes);
        ASSERT_GT(n,0U);ASSERT_EQ(::send(sender,bytes.data(),n,MSG_NOSIGNAL),static_cast<ssize_t>(n));
    }
};
TEST(Ipc2kCodec, CanonicalLayoutRoundtripAndBounds) {
    auto m=message();m.result.count=100;m.result.detections.fill(m.result.detections[0]);
    std::array<std::uint8_t,kPerceptionIpcMax> bytes{};
    ASSERT_EQ(encode_perception_ipc(m,bytes),4984U);
    EXPECT_EQ(std::string(reinterpret_cast<char*>(bytes.data()),8),"S2KPIPC1");
    EXPECT_EQ(bytes[16],1);EXPECT_EQ(bytes[24],42);EXPECT_EQ(bytes[32],77);EXPECT_EQ(bytes[40],88);
    PerceptionIpcMessage out;ASSERT_TRUE(decode_perception_ipc(bytes.data(),bytes.size(),out));
    EXPECT_EQ(out.result.model_hash,kNative2kModelHash);EXPECT_EQ(out.result.count,100U);
    EXPECT_DOUBLE_EQ(out.result.detections[99].y2,1536);EXPECT_EQ(out.result.received_wall_ns,m.result.received_wall_ns);
    for(std::size_t size=0;size<bytes.size();++size)EXPECT_FALSE(decode_perception_ipc(bytes.data(),size,out))<<size;
    EXPECT_FALSE(decode_perception_ipc(bytes.data(),bytes.size()+1,out));
    bytes[188]=1;EXPECT_FALSE(decode_perception_ipc(bytes.data(),bytes.size(),out)); // Detection reserved word.
}
TEST_F(Ipc2k, OriginalAcquisitionAndWallReceiptReachNativeUnchanged) {
    auto m=message();send(m);const auto v=receiver->poll(m.sender_wall_ns+ms);
    ASSERT_TRUE(v.available);EXPECT_TRUE(v.initialized);EXPECT_EQ(v.frame,5U);EXPECT_EQ(v.tracks,1U);
    EXPECT_EQ(v.source_ns,50*ms);EXPECT_EQ(v.received_wall_ns,wall+50*ms);EXPECT_EQ(v.wall_expires_ns,wall+150*ms);
    EXPECT_EQ(v.source_enable_ns,50*ms);EXPECT_EQ(v.wall_enable_ns,wall);EXPECT_EQ(v.accepted_results,1U);
}
TEST_F(Ipc2k, PollDoesNotRepublishOrExtendReceipt) {
    auto m=message();send(m);ASSERT_TRUE(receiver->poll(m.sender_wall_ns).available);
    m.sequence=2;m.kind=PerceptionIpcKind::Poll;m.sender_wall_ns+=50*ms;send(m);
    auto v=receiver->poll(m.sender_wall_ns);ASSERT_TRUE(v.available);EXPECT_EQ(v.accepted_results,1U);EXPECT_EQ(v.polls,1U);
    EXPECT_EQ(v.wall_expires_ns,wall+150*ms);
    v=receiver->poll(wall+150*ms);EXPECT_FALSE(v.available);EXPECT_EQ(v.reason,Native2kReason::StateStale);
}
TEST_F(Ipc2k, RepeatingStateMustNotRenewOriginalStateReceipt) {
    auto m=message();send(m);ASSERT_TRUE(receiver->poll(m.sender_wall_ns).available);
    ++m.sequence;m.sender_wall_ns+=ms;++m.observed.state_received_wall_ns;send(m);
    auto v=receiver->poll(m.sender_wall_ns);EXPECT_FALSE(v.available);EXPECT_TRUE(v.state_fault);
    m=message(3,10);send(m);v=receiver->poll(m.sender_wall_ns);EXPECT_FALSE(v.available);EXPECT_TRUE(v.state_fault);
}
TEST_F(Ipc2k, NoStateAndUnavailableClearOutputWithoutSyntheticTimestamp) {
    auto m=message();send(m);ASSERT_TRUE(receiver->poll(m.sender_wall_ns).available);
    m.kind=PerceptionIpcKind::Unavailable;++m.sequence;m.state_frame=0;m.observed={};send(m);
    auto v=receiver->poll(m.sender_wall_ns+ms);EXPECT_FALSE(v.available);EXPECT_EQ(v.state_frame,5U);EXPECT_EQ(v.unavailable,1U);
    m=message(3,5);send(m);v=receiver->poll(m.sender_wall_ns+2*ms);EXPECT_FALSE(v.available);EXPECT_EQ(v.reason,Native2kReason::Replay);
    m=message(4,10);send(m);EXPECT_TRUE(receiver->poll(m.sender_wall_ns).available);
}
TEST_F(Ipc2k, SourceAndReceiptAreNotReplacedWithSendTime) {
    auto m=message();send(m);ASSERT_TRUE(receiver->poll(m.sender_wall_ns).available);
    m=message(2,10);m.result.received_wall_ns=wall;m.result.wall_expires_ns=wall+100*ms;send(m);
    const auto v=receiver->poll(m.sender_wall_ns);EXPECT_FALSE(v.available);EXPECT_EQ(v.reason,Native2kReason::ReceiptExpired);
}
TEST_F(Ipc2k, IdentityAndSequenceRejectionCannotResurrectOutput) {
    auto m=message();send(m);ASSERT_TRUE(receiver->poll(m.sender_wall_ns).available);
    m.sequence=2;++m.wall_clock;send(m);auto v=receiver->poll(m.sender_wall_ns);EXPECT_FALSE(v.available);
    EXPECT_EQ(v.transport_fault,PerceptionIpcFault::Identity);
    m=message();send(m);v=receiver->poll(m.sender_wall_ns);EXPECT_FALSE(v.available);EXPECT_EQ(v.transport_fault,PerceptionIpcFault::Sequence);
}
TEST_F(Ipc2k, OldTransportAndFutureSenderAreRejected) {
    auto m=message();send(m);auto v=receiver->poll(m.sender_wall_ns+100*ms);
    EXPECT_FALSE(v.available);EXPECT_EQ(v.transport_fault,PerceptionIpcFault::TransportAge);
    m=message(2,20);send(m);v=receiver->poll(m.sender_wall_ns-1);
    EXPECT_FALSE(v.available);EXPECT_EQ(v.transport_fault,PerceptionIpcFault::TransportAge);
}
TEST_F(Ipc2k, OversizeAndMalformedPacketsFailClosed) {
    auto m=message();send(m);ASSERT_TRUE(receiver->poll(m.sender_wall_ns).available);
    std::array<std::uint8_t,kPerceptionIpcMax+1> bytes{};
    ASSERT_EQ(::send(sender,bytes.data(),bytes.size(),MSG_NOSIGNAL),static_cast<ssize_t>(bytes.size()));
    auto v=receiver->poll(m.sender_wall_ns);EXPECT_FALSE(v.available);EXPECT_EQ(v.transport_fault,PerceptionIpcFault::Encoding);
}
TEST_F(Ipc2k, PeerDisconnectClearsSnapshotAndRemainsClosed) {
    auto m=message();send(m);ASSERT_TRUE(receiver->poll(m.sender_wall_ns).available);
    close(sender);sender=-1;auto v=receiver->poll(m.sender_wall_ns+ms);
    EXPECT_TRUE(v.disconnected);EXPECT_FALSE(v.available);EXPECT_EQ(v.transport_fault,PerceptionIpcFault::Disconnected);
    EXPECT_FALSE(receiver->poll(m.sender_wall_ns+2*ms).available);
}
TEST_F(Ipc2k, DrainIsBoundedAndQuietPollNeverBlocks) {
    for(unsigned i=1;i<=6;++i) {auto m=message(i);m.kind=PerceptionIpcKind::Poll;send(m);}
    auto v=receiver->poll(wall+50*ms);EXPECT_EQ(v.received,4U);EXPECT_EQ(v.budget_hits,1U);
    v=receiver->poll(wall+50*ms);EXPECT_EQ(v.received,6U);EXPECT_EQ(v.budget_hits,1U);
    for(unsigned i=0;i<100;++i)v=receiver->poll(wall+50*ms+i);
    EXPECT_EQ(v.received,6U);
}
TEST(Ipc2kInit, ImageCannotStartSessionAndOldPublicationCannotCrossAcceptedInit) {
    int pair[2];ASSERT_EQ(socketpair(AF_UNIX,SOCK_SEQPACKET|SOCK_NONBLOCK,0,pair),0);
    PerceptionIpcShadow receiver(pair[1],42,77,88);
    auto put=[&](PerceptionIpcMessage m) {std::array<std::uint8_t,kPerceptionIpcMax> b{};const auto n=encode_perception_ipc(m,b);return ::send(pair[0],b.data(),n,MSG_NOSIGNAL)>0;};
    ASSERT_TRUE(put(message()));EXPECT_FALSE(receiver.poll(wall+50*ms).initialized);
    ASSERT_TRUE(receiver.observe_native_init(42,wall+60*ms));
    auto m=message(2,10);m.result=message().result;ASSERT_TRUE(put(m));auto v=receiver.poll(wall+100*ms);
    EXPECT_TRUE(v.initialized);EXPECT_FALSE(v.available);EXPECT_EQ(v.reason,Native2kReason::SourceExpired);
    ASSERT_TRUE(put(message(3,15)));EXPECT_TRUE(receiver.poll(wall+150*ms).available);
    EXPECT_FALSE(receiver.observe_native_init(42,wall+61*ms));
    EXPECT_FALSE(receiver.poll(wall+151*ms).available);close(pair[0]);
}
TEST_F(Ipc2k, UnexpectedTrustedRootEpochLatchesClosed) {
    auto m=message();send(m);ASSERT_TRUE(receiver->poll(m.sender_wall_ns).available);
    EXPECT_FALSE(receiver->observe_native_init(43,wall));
    auto v=receiver->poll(m.sender_wall_ns+ms);EXPECT_TRUE(v.state_fault);EXPECT_FALSE(v.available);
    send(message(2,1));EXPECT_FALSE(receiver->poll(m.sender_wall_ns+5*ms).available);
}
} // namespace
