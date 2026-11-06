#include "diagnostics_delivery.hpp"
#include "diagnostics_fixture.hpp"
#include <gtest/gtest.h>
#include <cstdlib>
#include <filesystem>
#include <fstream>

namespace {
using namespace diagnostics_fixture;
class EpochMerge:public ::testing::Test {
protected:
    std::filesystem::path root;
    void SetUp() override {
        char path[]="/tmp/stratadrive-merge-XXXXXX";auto* p=mkdtemp(path);ASSERT_NE(p,nullptr);root=p;
        init("merged",9000,3);init("front",1000,2);init("rear",2000,4);
    }
    void TearDown() override {std::filesystem::remove_all(root);}
    void init(const char* name,std::uint64_t id,unsigned threshold,unsigned maximum=32) {
        EpochRecorder::initialize((root/name).string(),id,{{64,8,16,8},threshold,maximum});
    }
    Event context(unsigned epoch) {auto e=session(100+epoch,epoch);e.session_enable=stamp(epoch*1000000000ULL);return e;}
    Event local(unsigned producer,unsigned epoch,unsigned sequence=1) {
        auto e=fault(epoch*10+sequence,Code::SpeedInput,epoch);e.id.producer=producer;e.occurrence.producer=producer;
        e.key.subject=producer;e.session_enable=context(epoch).session_enable;return e;
    }
    wire::Bytes packet(const Event& e,unsigned ordinal,unsigned stream=1000) {return wire::encode(wire::Data{stream,ordinal,4,e});}
    void first(EpochMergedCollector& merge) {
        EXPECT_FALSE(merge.receive(packet(context(1),1)).ack);
        ASSERT_TRUE(merge.receive(packet(context(1),1,2000)).ack);
        ASSERT_TRUE(merge.receive(packet(context(1),1)).ack);
    }
};
TEST_F(EpochMerge, LaterSessionWaitsForEveryOldTailBeforeRollover) {
    EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
    EpochMergedCollector merge(m,{&a,&b});first(merge);
    ASSERT_TRUE(merge.receive(packet(local(30,1),2)).ack);
    const auto ahead=packet(context(2),3);const auto held=merge.receive(ahead);
    EXPECT_EQ(held.result,Result::NotReady);EXPECT_FALSE(held.ack);EXPECT_EQ(a.segment(),2U);EXPECT_EQ(m.segment(),1U);
    EXPECT_EQ(m.ledger().session().epoch,1U);EXPECT_EQ(m.watermark(),2U);
    ASSERT_TRUE(merge.receive(packet(local(40,1),2,2000)).ack);
    EXPECT_EQ(m.watermark(),3U);EXPECT_EQ(m.ledger().session().epoch,1U);
    ASSERT_TRUE(merge.receive(packet(context(2),3,2000)).ack);
    EXPECT_EQ(m.segment(),2U);EXPECT_EQ(m.watermark(),4U);
    ASSERT_TRUE(merge.receive(ahead).ack);EXPECT_EQ(m.watermark(),4U);
    ASSERT_EQ(m.ledger().records().size(),2U);
    for(const auto& record:m.ledger().records()){EXPECT_EQ(record.count,1U);EXPECT_EQ(record.condition,Condition::Unknown);}
    EXPECT_EQ(encode(m.committed(3)),encode(local(40,1)));
}
TEST_F(EpochMerge, RestartRetainsBarrierAndCannotExcludeAnUnavailableMember) {
    {
        EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
        EpochMergedCollector merge(m,{&a,&b});first(merge);
        ASSERT_TRUE(merge.receive(packet(local(30,1),2)).ack);
        EXPECT_FALSE(merge.receive(packet(context(2),3)).ack);
    }
    EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
    EXPECT_THROW((EpochMergedCollector{m,{&a}}),std::invalid_argument);
    EpochMergedCollector merge(m,{&b,&a});EXPECT_TRUE(merge.healthy());EXPECT_EQ(m.ledger().session().epoch,1U);
    EXPECT_FALSE(merge.receive(packet(context(2),3)).ack);
    ASSERT_TRUE(merge.receive(packet(local(40,1),2,2000)).ack);
    ASSERT_TRUE(merge.receive(packet(context(2),3,2000)).ack);
    ASSERT_TRUE(merge.receive(packet(context(2),3)).ack);
    EXPECT_EQ(m.watermark(),4U);
}
TEST_F(EpochMerge, ReconcilesDurableReplicaPrefixesInEpochOrderAcrossDifferentThresholds) {
    // Simulate death after replica commits and before merged commit. Replaying
    // each source in full would rotate past the other source's original tail.
    {
        EpochRecorder a((root/"front").string()),b((root/"rear").string());
        for(unsigned epoch=1;epoch<=12;++epoch)for(auto* store:{&a,&b}) {
            ASSERT_TRUE(store->record(context(epoch)).durable);
            ASSERT_TRUE(store->record(local(store==&a?30:40,epoch)).durable);
        }
    }
    {
        EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
        EpochMergedCollector merge(m,{&a,&b});EXPECT_TRUE(merge.healthy());EXPECT_EQ(m.watermark(),36U);EXPECT_EQ(m.segment(),12U);
        for(const auto& record:m.ledger().records()){EXPECT_EQ(record.count,12U);EXPECT_EQ(record.condition,Condition::Unknown);}
        for(unsigned epoch=1;epoch<=12;++epoch) {
            ASSERT_TRUE(merge.receive(packet(context(epoch),epoch*2-1)).ack);
            ASSERT_TRUE(merge.receive(packet(local(30,epoch),epoch*2)).ack);
            ASSERT_TRUE(merge.receive(packet(context(epoch),epoch*2-1,2000)).ack);
            ASSERT_TRUE(merge.receive(packet(local(40,epoch),epoch*2,2000)).ack);
        }
        EXPECT_EQ(m.watermark(),36U);
    }
    EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
    EpochMergedCollector merge(m,{&a,&b});EXPECT_EQ(m.watermark(),36U);EXPECT_TRUE(merge.healthy());
}
TEST_F(EpochMerge, CentralAttemptDoesNotDependOnRemoteAckForContextDistribution) {
    EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
    EpochMergedCollector merge(m,{&a,&b});
    const auto attempt=[&](unsigned epoch) {auto e=context(epoch);e.id.sequence=epoch;e.kind=Kind::Attempt;e.session_enable={};e.source={true,20,epoch,epoch,stamp(epoch*1000000000ULL),{}};return e;};
    const auto released=[&](unsigned epoch) {auto e=context(epoch);e.expected_roles=e.received_roles=255;return e;};
    // Remote stream has the original global Session via a separate context
    // route even while Central's earlier Attempt waits for the merge barrier.
    EXPECT_FALSE(merge.receive(packet(released(1),1)).ack);
    ASSERT_TRUE(merge.receive(packet(attempt(1),1,2000)).ack);
    ASSERT_TRUE(merge.receive(packet(released(1),1)).ack);
    ASSERT_TRUE(merge.receive(packet(released(1),2,2000)).ack);
    EXPECT_FALSE(merge.receive(packet(attempt(2),3,2000)).ack);
    // No global release for failed epoch2: the remote's next real Session3
    // closes its old prefix without inventing Session2.
    EXPECT_FALSE(merge.receive(packet(released(3),2)).ack);
    ASSERT_TRUE(merge.receive(packet(attempt(2),3,2000)).ack);
    ASSERT_TRUE(merge.receive(packet(local(40,2),4,2000)).ack);
    ASSERT_TRUE(merge.receive(packet(attempt(3),5,2000)).ack);
    ASSERT_TRUE(merge.receive(packet(released(3),2)).ack);
    ASSERT_TRUE(merge.receive(packet(released(3),6,2000)).ack);
    EXPECT_EQ(m.ledger().session().epoch,3U);EXPECT_TRUE(merge.healthy());
}
TEST_F(EpochMerge, AheadStreamCannotGrowPendingWindowOrSkipAnOrdinal) {
    EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
    EpochMergedCollector merge(m,{&a,&b});
    EXPECT_FALSE(merge.receive(packet(context(1),1)).ack);
    EXPECT_EQ(merge.receive(packet(local(30,1),2)).result,Result::NotReady);EXPECT_EQ(a.watermark(),1U);
    EXPECT_EQ(merge.receive(packet(context(1),1,3000)).result,Result::Invalid);
    EXPECT_EQ(merge.receive(wire::encode(wire::Data{1000,1,3,context(1)})).result,Result::Invalid);
    EXPECT_TRUE(merge.healthy());first(merge);
}
TEST_F(EpochMerge, UnseenOldEventAfterBoundaryIsAStickyConflict) {
    {
        EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
        EpochMergedCollector merge(m,{&a,&b});first(merge);
        EXPECT_FALSE(merge.receive(packet(context(2),2)).ack);
        ASSERT_TRUE(merge.receive(packet(context(2),2,2000)).ack);
        const auto r=merge.receive(packet(local(30,1),3));EXPECT_EQ(r.result,Result::Conflict);EXPECT_FALSE(r.ack);
        EXPECT_FALSE(merge.healthy());EXPECT_EQ(a.watermark(),2U);
    }
    EpochRecorder m((root/"merged").string());EXPECT_FALSE(m.ledger().complete());
}
TEST_F(EpochMerge, FutureFaultWithoutOriginalBoundaryCannotAdvanceEitherStore) {
    EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
    EpochMergedCollector merge(m,{&a,&b});first(merge);
    const auto r=merge.receive(packet(local(30,2),2));EXPECT_EQ(r.result,Result::Conflict);EXPECT_FALSE(r.ack);
    EXPECT_EQ(a.watermark(),1U);EXPECT_EQ(m.watermark(),1U);EXPECT_FALSE(merge.healthy());
}
TEST_F(EpochMerge, ChangedPendingPayloadCannotBeAcknowledgedAfterRestart) {
    {
        EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
        EpochMergedCollector merge(m,{&a,&b});first(merge);EXPECT_FALSE(merge.receive(packet(context(2),2)).ack);
    }
    EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
    EpochMergedCollector merge(m,{&a,&b});auto changed=context(2);++changed.session_enable.ns;
    const auto r=merge.receive(packet(changed,2));EXPECT_EQ(r.result,Result::Conflict);EXPECT_FALSE(r.ack);EXPECT_FALSE(merge.healthy());
    EXPECT_EQ(encode(a.committed(2)),encode(context(2)));
}
TEST_F(EpochMerge, MergedCommitFailureLeavesReplicaEvidenceWithoutAnAck) {
    EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
    EpochMergedCollector merge(m,{&a,&b});first(merge);
    std::filesystem::create_directory(root/"merged"/"00000001"/"pending");
    const auto r=merge.receive(packet(local(30,1),2));EXPECT_FALSE(r.ack);EXPECT_EQ(r.result,Result::StorageFailure);
    EXPECT_EQ(a.watermark(),2U);EXPECT_EQ(m.watermark(),1U);EXPECT_FALSE(merge.healthy());
}
TEST_F(EpochMerge, OtherRunCannotJoinTheBarrier) {
    EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
    EpochMergedCollector merge(m,{&a,&b});EXPECT_FALSE(merge.receive(packet(context(1),1)).ack);
    auto wrong=context(1);wrong.id.run=wrong.session.run=11;
    EXPECT_EQ(merge.receive(packet(wrong,1,2000)).result,Result::Conflict);EXPECT_EQ(b.watermark(),0U);EXPECT_FALSE(merge.healthy());
}
TEST_F(EpochMerge, SegmentQuotaKeepsBothReplicaBoundariesButNeverAcknowledgesTheMerge) {
    init("limited",9500,1,1);
    EpochRecorder m((root/"limited").string()),a((root/"front").string()),b((root/"rear").string());
    EpochMergedCollector merge(m,{&a,&b});first(merge);
    EXPECT_FALSE(merge.receive(packet(context(2),2)).ack);
    const auto r=merge.receive(packet(context(2),2,2000));EXPECT_EQ(r.result,Result::Capacity);EXPECT_FALSE(r.ack);
    EXPECT_FALSE(merge.healthy());EXPECT_EQ(m.watermark(),1U);EXPECT_EQ(a.watermark(),2U);EXPECT_EQ(b.watermark(),2U);
}
TEST_F(EpochMerge, CorruptOrMissingMembershipCannotBeReconstructedFromReceivedTraffic) {
    {
        EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
        EpochMergedCollector merge(m,{&a,&b});first(merge);
    }
    std::filesystem::rename(root/"merged"/"merge-sources",root/"membership-preserved");
    EpochRecorder m((root/"merged").string()),a((root/"front").string()),b((root/"rear").string());
    EXPECT_THROW((EpochMergedCollector{m,{&a,&b}}),std::invalid_argument);
    std::filesystem::rename(root/"membership-preserved",root/"merged"/"merge-sources");
    std::fstream bytes(root/"merged"/"merge-sources",std::ios::in|std::ios::out|std::ios::binary);bytes.seekp(12);bytes.put('X');bytes.close();
    EXPECT_THROW((EpochMergedCollector{m,{&a,&b}}),std::runtime_error);EXPECT_FALSE(m.ledger().complete());
}
} // namespace
