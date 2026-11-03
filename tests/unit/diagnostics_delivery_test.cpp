#include "diagnostics_delivery.hpp"
#include "diagnostics_fixture.hpp"
#include <gtest/gtest.h>
#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>

namespace {
using namespace diagnostics_fixture;
wire::Bytes data(const Event& e,std::uint64_t sequence,std::uint64_t stream=1234,std::uint32_t registry=3) { return wire::encode(wire::Data{stream,sequence,registry,e}); }
wire::Bytes ack(const Event& e,std::uint64_t sequence,std::uint64_t stream=1234,std::uint32_t registry=3) { return wire::encode(wire::Ack{stream,sequence,registry,wire::event_crc(e)}); }
void reseal(wire::Bytes& b) {
    std::uint32_t c=0xffffffff;
    for(std::size_t n=0;n<b.size()-4;++n) { c^=b[n]; for(unsigned bit=0;bit<8;++bit) c=(c>>1)^((c&1)?0xedb88320U:0U); }
    c=~c; for(unsigned i=0;i<4;++i) b[b.size()-4+i]=static_cast<std::uint8_t>(c>>(i*8));
}
TEST(DiagnosticsWire, CanonicalEventAndAckRoundTripAcrossEverySupportedRegistry) {
    for(std::uint32_t registry=1;registry<=3;++registry) {
        auto e=fault(); if(registry==2) e.key.code=Code::BmsLocal;
        if(registry==3) { e=session(); e.kind=Kind::Attempt; e.session_enable={}; e.source={true,20,1,1,stamp(),{}}; }
        const auto bytes=data(e,17,1234,registry); ASSERT_LE(bytes.size(),wire::kMaxPacket);
        const auto decoded=wire::decode(bytes); const auto& d=std::get<wire::Data>(decoded);
        EXPECT_EQ(d.stream,1234U); EXPECT_EQ(d.sequence,17U); EXPECT_EQ(d.registry,registry); EXPECT_EQ(encode(d.event),encode(e)); EXPECT_EQ(wire::encode(decoded),bytes);
        const auto a=ack(e,17,1234,registry); EXPECT_EQ(wire::encode(wire::decode(a)),a); EXPECT_EQ(std::get<wire::Ack>(wire::decode(a)).event_crc,wire::event_crc(e));
    }
}
TEST(DiagnosticsWire, EveryByteCorruptionAndTruncationIsRejectedBeforeAdmission) {
    const auto bytes=data(fault(),2);
    for(std::size_t i=0;i<bytes.size();++i) {
        auto changed=bytes; changed[i]^=1; EXPECT_THROW(wire::decode(changed),std::exception)<<i;
        EXPECT_THROW(wire::decode(wire::Bytes(bytes.begin(),bytes.begin()+static_cast<std::ptrdiff_t>(i))),std::exception)<<i;
    }
    auto extra=bytes; extra.push_back(0); EXPECT_THROW(wire::decode(extra),std::exception);
    EXPECT_THROW(wire::decode(wire::Bytes(wire::kMaxPacket+1)),std::exception);
    for(const auto offset:{0U,6U,8U,9U,12U,32U,36U}) {
        auto changed=bytes; changed[offset]=0xff; reseal(changed); EXPECT_THROW(wire::decode(changed),std::exception)<<offset;
    }
    for(const auto offset:{16U,24U}) { auto changed=bytes; std::fill_n(changed.begin()+offset,8,0); reseal(changed); EXPECT_THROW(wire::decode(changed),std::exception)<<offset; }
}
TEST(DiagnosticsWire, UnsupportedIdentitySchemaAndDictionaryAreRejected) {
    EXPECT_THROW(data(session(),0),std::exception);
    EXPECT_THROW(data(session(),1,0),std::exception);
    EXPECT_THROW(data(session(),1,1234,4),std::exception);
    auto e=fault(); e.key.code=Code::Startup; EXPECT_THROW(data(e,1,1234,2),std::exception);
    e.key.code=static_cast<Code>(0xffff); EXPECT_THROW(data(e,1),std::exception);
    e=session(); e.kind=Kind::Attempt; EXPECT_THROW(data(e,1,1234,2),std::exception);
    e=session(); e.schema=2; EXPECT_THROW(data(e,1),std::exception);
    e=session(); e.kind=static_cast<Kind>(255); EXPECT_THROW(data(e,1),std::exception);
}
TEST(DiagnosticsWire, ACanonicalLocalClearTransactionCannotBeEncodedAsRemoteData) {
    Record r; r.key=fault().key; r.revision=1; const auto payload=encode(clear(r));
    auto bytes=data(session(),1); bytes.resize(36); bytes[32]=static_cast<std::uint8_t>(payload.size()); bytes[33]=static_cast<std::uint8_t>(payload.size()>>8); bytes[34]=bytes[35]=0;
    bytes.insert(bytes.end(),payload.begin(),payload.end()); bytes.resize(bytes.size()+4); reseal(bytes);
    EXPECT_THROW(wire::decode(bytes),std::exception);
}
class DiagnosticsDelivery : public ::testing::Test {
protected:
    std::filesystem::path root,source,dest;
    void SetUp() override {
        char name[]="/tmp/stratadrive-delivery-XXXXXX"; auto* p=mkdtemp(name); ASSERT_NE(p,nullptr); root=p; source=root/"source"; dest=root/"replica";
    }
    void TearDown() override { std::filesystem::remove_all(root); }
    void init(Limits limits={}) { FileJournal::initialize(source.string(),1234,limits,3); FileJournal::initialize(dest.string(),1234,limits,3); }
};
TEST_F(DiagnosticsDelivery, OnlyDurableSourceEventsAndExactCommittedAcksAdvanceWithoutDeletingHistory) {
    init(); FileJournal s(source.string()),d(dest.string()); Outbox out(s); Inbox in(d); EXPECT_FALSE(out.next());
    ASSERT_TRUE(out.record(session()).durable); ASSERT_TRUE(out.record(fault()).durable);
    for(unsigned i=1;i<=2;++i) {
        const auto bytes=out.next(); ASSERT_TRUE(bytes); EXPECT_EQ(out.next(),bytes);
        const auto got=in.receive(*bytes); ASSERT_TRUE(got.ack); EXPECT_EQ(got.result,Result::Accepted); EXPECT_EQ(got.watermark,i);
        EXPECT_EQ(out.acknowledge(*got.ack),Result::Accepted); EXPECT_EQ(out.acknowledge(*got.ack),Result::Duplicate);
    }
    EXPECT_FALSE(out.next()); EXPECT_EQ(s.committed().size(),2U); EXPECT_EQ(out.acknowledged(),2U); EXPECT_EQ(d.committed().size(),2U);
    EXPECT_EQ(encode(s.committed()[1]),encode(d.committed()[1])); EXPECT_EQ(in.ledger().find(fault().key)->condition,Condition::Failed);
}
TEST_F(DiagnosticsDelivery, LostAckAndBothRestartsReplayEveryOrdinalWithoutHealingUnknown) {
    init(); {
        FileJournal s(source.string()),d(dest.string()); Outbox out(s); Inbox in(d);
        ASSERT_TRUE(out.record(session()).durable); ASSERT_TRUE(out.record(fault()).durable);
        const auto bytes=out.next(); ASSERT_TRUE(bytes); ASSERT_TRUE(in.receive(*bytes).ack); EXPECT_EQ(out.acknowledged(),0U);
    }
    {
        FileJournal s(source.string()),d(dest.string()); Outbox out(s); Inbox in(d); EXPECT_EQ(out.acknowledged(),0U);
        auto got=in.receive(*out.next()); ASSERT_TRUE(got.ack); EXPECT_EQ(got.result,Result::Duplicate); ASSERT_EQ(out.acknowledge(*got.ack),Result::Accepted);
        got=in.receive(*out.next()); ASSERT_TRUE(got.ack); ASSERT_EQ(out.acknowledge(*got.ack),Result::Accepted); EXPECT_EQ(in.ledger().find(fault().key)->count,1U);
    }
    FileJournal s(source.string()),d(dest.string()); Outbox out(s); Inbox in(d);
    EXPECT_EQ(in.ledger().find(fault().key)->condition,Condition::Unknown);
    while(const auto bytes=out.next()) { const auto got=in.receive(*bytes); ASSERT_TRUE(got.ack); EXPECT_EQ(got.result,Result::Duplicate); ASSERT_EQ(out.acknowledge(*got.ack),Result::Accepted); }
    EXPECT_EQ(in.ledger().find(fault().key)->condition,Condition::Unknown); EXPECT_EQ(d.committed().size(),2U); EXPECT_EQ(in.ledger().find(fault().key)->count,1U);
}
TEST_F(DiagnosticsDelivery, FutureCorruptAndMismatchedDataCannotMoveWatermarkAndCanBeRetried) {
    init(); FileJournal d(dest.string()); Inbox in(d);
    EXPECT_EQ(in.receive(data(fault(),2)).result,Result::NotReady);
    auto bad=data(session(),1); bad.back()^=1; EXPECT_EQ(in.receive(bad).result,Result::Invalid);
    EXPECT_EQ(in.receive(data(session(),1,5678)).result,Result::Invalid);
    EXPECT_EQ(in.receive(data(session(),1,1234,2)).result,Result::Invalid);
    EXPECT_EQ(in.receive(ack(session(),1)).result,Result::Invalid); EXPECT_TRUE(d.committed().empty()); EXPECT_TRUE(in.healthy());
    const auto got=in.receive(data(session(),1)); EXPECT_TRUE(got.ack); EXPECT_EQ(got.watermark,1U);
}
TEST_F(DiagnosticsDelivery, AckCannotSkipUnpreparedOrWrongStreamRegistryDirectionAndPayload) {
    init(); FileJournal s(source.string()); Outbox out(s); ASSERT_TRUE(out.record(session()).durable); ASSERT_TRUE(out.record(fault()).durable);
    EXPECT_EQ(out.acknowledge(ack(session(),1)),Result::NotReady); ASSERT_TRUE(out.next());
    EXPECT_EQ(out.acknowledge(ack(fault(),2)),Result::NotReady);
    EXPECT_EQ(out.acknowledge(ack(session(),1,5678)),Result::Invalid);
    EXPECT_EQ(out.acknowledge(ack(session(),1,1234,2)),Result::Invalid);
    EXPECT_EQ(out.acknowledge(data(session(),1)),Result::Invalid);
    EXPECT_EQ(out.acknowledge(ack(fault(),1)),Result::Conflict);
    auto broken=ack(session(),1); broken.back()^=1; EXPECT_EQ(out.acknowledge(broken),Result::Invalid);
    EXPECT_EQ(out.acknowledged(),0U); EXPECT_TRUE(out.healthy()); EXPECT_EQ(out.acknowledge(ack(session(),1)),Result::Accepted);
}
TEST_F(DiagnosticsDelivery, DifferentDuplicatePermanentlyMarksReplicaIncompleteWithoutOverwritingOrigin) {
    init(); const auto original=session(); {
        FileJournal d(dest.string()); Inbox in(d); ASSERT_TRUE(in.receive(data(original,1)).ack);
        auto changed=original; changed.native_reason=9; const auto got=in.receive(data(changed,1)); EXPECT_EQ(got.result,Result::Conflict); EXPECT_FALSE(got.ack); EXPECT_FALSE(in.healthy());
        EXPECT_FALSE(in.ledger().complete()); EXPECT_EQ(encode(d.committed()[0]),encode(original)); EXPECT_FALSE(in.receive(data(original,1)).ack);
    }
    FileJournal d(dest.string()); Inbox in(d); EXPECT_FALSE(in.healthy()); EXPECT_FALSE(in.receive(data(original,1)).ack); EXPECT_EQ(d.committed().size(),1U);
}
TEST_F(DiagnosticsDelivery, ReusingAnEventIdentityAtAnotherOrdinalCannotInventASecondCommit) {
    init(); FileJournal d(dest.string()); Inbox in(d); ASSERT_TRUE(in.receive(data(session(),1)).ack);
    const auto got=in.receive(data(session(),2)); EXPECT_EQ(got.result,Result::Conflict); EXPECT_FALSE(got.ack); EXPECT_FALSE(in.healthy()); EXPECT_EQ(d.committed().size(),1U);
}
TEST_F(DiagnosticsDelivery, CapacityNeverEvictsOrReusesHistoryEvenAfterAcknowledgement) {
    init({2,1,1,1}); FileJournal s(source.string()),d(dest.string()); Outbox out(s); Inbox in(d);
    ASSERT_TRUE(out.record(session()).durable); ASSERT_TRUE(out.record(fault()).durable);
    while(const auto bytes=out.next()) { const auto got=in.receive(*bytes); ASSERT_TRUE(got.ack); ASSERT_EQ(out.acknowledge(*got.ack),Result::Accepted); }
    auto e=session(3); e.kind=Kind::Observation; const auto got=out.record(e); EXPECT_EQ(got.result,Result::Capacity); EXPECT_FALSE(got.durable);
    EXPECT_EQ(s.committed().size(),2U); EXPECT_FALSE(out.healthy()); EXPECT_FALSE(out.next()); EXPECT_EQ(encode(s.committed()[1]),encode(fault()));
}
TEST_F(DiagnosticsDelivery, ReceiverCommitFailureCannotAckOrEraseItsUncommittedTail) {
    init(); {
        FileJournal d(dest.string()); Inbox in(d); ASSERT_TRUE(in.receive(data(session(),1)).ack); std::filesystem::create_directory(dest/"pending");
        const auto got=in.receive(data(fault(),2)); EXPECT_EQ(got.result,Result::StorageFailure); EXPECT_FALSE(got.ack); EXPECT_EQ(got.watermark,1U); EXPECT_FALSE(in.healthy()); EXPECT_GT(d.uncommitted_bytes(),0U);
    }
    const auto bytes=std::filesystem::file_size(dest/"journal"); FileJournal d(dest.string()); Inbox in(d);
    EXPECT_EQ(d.committed().size(),1U); EXPECT_FALSE(in.receive(data(fault(),2)).ack); EXPECT_EQ(std::filesystem::file_size(dest/"journal"),bytes); EXPECT_GT(d.uncommitted_bytes(),0U);
}
TEST_F(DiagnosticsDelivery, ReceiverCapacityCannotAckAnEventItCannotRetain) {
    FileJournal::initialize(dest.string(),1234,{1,1,1,1},3); FileJournal d(dest.string()); Inbox in(d);
    ASSERT_TRUE(in.receive(data(session(),1)).ack); const auto got=in.receive(data(fault(),2));
    EXPECT_EQ(got.result,Result::Capacity); EXPECT_FALSE(got.ack); EXPECT_EQ(got.watermark,1U); EXPECT_FALSE(in.healthy()); EXPECT_EQ(d.committed().size(),1U);
}
TEST_F(DiagnosticsDelivery, IncompleteSourceAndReplicaNeverClaimDeliverySuccess) {
    init(); { FileJournal s(source.string()); Outbox out(s); ASSERT_TRUE(out.record(session()).durable); }
    std::ofstream(source/"journal",std::ios::app|std::ios::binary)<<"tail";
    FileJournal s(source.string()),d(dest.string()); Outbox out(s); Inbox in(d); EXPECT_FALSE(out.healthy()); EXPECT_FALSE(out.next()); EXPECT_EQ(out.acknowledge(ack(session(),1)),Result::NotReady);
    d.invalidate(); EXPECT_FALSE(in.receive(data(session(),1)).ack); EXPECT_TRUE(d.committed().empty());
}
TEST_F(DiagnosticsDelivery, QueueOverflowIsStickyBeforeTheNonRtSpoolCanClaimSuccess) {
    init(); FileJournal s(source.string()); Outbox out(s); EventQueue queue(10,20);
    for(std::size_t i=0;i<=EventQueue::kCapacity;++i) { auto e=session(i+1); if(i) e.kind=Kind::Observation; queue.publish(e); }
    EXPECT_EQ(out.drain(queue,1),1U); EXPECT_FALSE(out.healthy()); EXPECT_FALSE(out.next()); EXPECT_EQ(queue.health().dropped,1U);
}
TEST_F(DiagnosticsDelivery, ALocalStoreWithClearTombstoneCannotBeAdoptedAsAnEventOnlyStream) {
    init(); FileJournal s(source.string()); Recorder local(s); const auto f=fault();
    for(const auto& e:{session(),f,proof(f),passed(proof(f))}) ASSERT_TRUE(local.record(e).durable);
    ASSERT_TRUE(local.clear(clear(*local.ledger().find(f.key))).durable);
    EXPECT_THROW(Outbox{s},std::invalid_argument);
    EXPECT_THROW(Inbox{s},std::invalid_argument);
    EXPECT_TRUE(s.writable()); EXPECT_EQ(s.committed().size(),5U);
}
TEST_F(DiagnosticsDelivery, CollectorRepairsReplicaOnlyCommitBeforeAcknowledgingAndKeepsUnknown) {
    init(); const auto merged=root/"merged"; FileJournal::initialize(merged.string(),9000,{},3);
    { FileJournal d(dest.string()); Inbox in(d); ASSERT_TRUE(in.receive(data(session(),1)).ack); ASSERT_TRUE(in.receive(data(fault(),2)).ack); }
    FileJournal d(dest.string()),m(merged.string()); MergedCollector in(m,{&d});
    ASSERT_EQ(m.committed().size(),2U); EXPECT_EQ(encode(m.committed()[1]),encode(fault()));
    ASSERT_TRUE(in.ledger().find(fault().key)); EXPECT_EQ(in.ledger().find(fault().key)->condition,Condition::Unknown);
    const auto got=in.receive(data(fault(),2)); ASSERT_TRUE(got.ack); EXPECT_EQ(got.result,Result::Duplicate);
    EXPECT_EQ(in.ledger().find(fault().key)->condition,Condition::Unknown); EXPECT_EQ(in.ledger().find(fault().key)->count,1U);
}
TEST_F(DiagnosticsDelivery, CollectorCannotAckReplicaWhenMergedCommitFails) {
    init(); const auto merged=root/"merged"; FileJournal::initialize(merged.string(),9000,{},3);
    FileJournal d(dest.string()),m(merged.string()); MergedCollector in(m,{&d});
    ASSERT_TRUE(in.receive(data(session(),1)).ack); std::filesystem::create_directory(merged/"pending");
    const auto got=in.receive(data(fault(),2)); EXPECT_FALSE(got.ack); EXPECT_EQ(got.result,Result::StorageFailure);
    EXPECT_EQ(d.committed().size(),2U); EXPECT_EQ(m.committed().size(),1U); EXPECT_FALSE(in.healthy());
    EXPECT_FALSE(in.receive(data(fault(),2)).ack);
}
TEST_F(DiagnosticsDelivery, CollectorDeduplicatesSharedSessionAndKeepsIndependentOrdinalsAcrossRestart) {
    init(); const auto merged=root/"merged",other=root/"other"; FileJournal::initialize(merged.string(),9000,{},3); FileJournal::initialize(other.string(),5678,{},3);
    for(unsigned round=0;round<2;++round) {
        FileJournal d(dest.string()),o(other.string()),m(merged.string()); MergedCollector in(m,{&d,&o});
        EXPECT_TRUE(in.receive(data(session(),1)).ack); EXPECT_TRUE(in.receive(data(session(),1,5678)).ack);
        EXPECT_TRUE(in.receive(data(fault(),2)).ack); EXPECT_EQ(m.committed().size(),2U);
        EXPECT_EQ(in.ledger().find(fault().key)->condition,round?Condition::Unknown:Condition::Failed);
        EXPECT_EQ(in.ledger().find(fault().key)->count,1U); EXPECT_EQ(in.ledger().find(fault().key)->generation,1U);
    }
}
TEST_F(DiagnosticsDelivery, CollectorRejectsForeignRegistryDuplicateStreamAndUnknownDataWithoutMutation) {
    init(); const auto merged=root/"merged",other=root/"other"; FileJournal::initialize(merged.string(),9000,{},3); FileJournal::initialize(other.string(),5678,{},2);
    FileJournal d(dest.string()),o(other.string()),m(merged.string());
    EXPECT_THROW((MergedCollector{m,{&d,&d}}),std::invalid_argument);
    EXPECT_THROW((MergedCollector{m,{&o}}),std::invalid_argument);
    EXPECT_THROW((MergedCollector{m,{&m}}),std::invalid_argument);
    EXPECT_THROW((MergedCollector{m,{nullptr}}),std::invalid_argument);
    MergedCollector in(m,{&d}); EXPECT_FALSE(in.receive(data(session(),1,5678)).ack);
    EXPECT_FALSE(in.receive(data(session(),1,1234,2)).ack); EXPECT_TRUE(d.committed().empty()); EXPECT_TRUE(m.committed().empty()); EXPECT_TRUE(in.healthy());
}
TEST_F(DiagnosticsDelivery, CollectorConflictingReplicaHistoryFailsClosedAndKeepsOriginalMergedBytes) {
    init(); const auto merged=root/"merged"; FileJournal::initialize(merged.string(),9000,{},3);
    FileJournal d(dest.string()),m(merged.string()); Inbox in(d); Recorder original(m); ASSERT_TRUE(original.record(session()).durable);
    auto changed=session(); changed.native_reason=42; ASSERT_TRUE(in.receive(data(changed,1)).ack);
    EXPECT_THROW((MergedCollector{m,{&d}}),std::runtime_error); EXPECT_EQ(m.committed().size(),1U); EXPECT_EQ(encode(m.committed()[0]),encode(session())); EXPECT_FALSE(m.writable());
}
TEST_F(DiagnosticsDelivery, ArchivedReplayExportsOnlyVerifiedCommittedPrefixAndPreservesUncommittedTail) {
    init();{FileJournal s(source.string());Outbox out(s);ASSERT_TRUE(out.record(session()).durable);ASSERT_TRUE(out.record(fault()).durable);}
    std::ofstream(source/"journal",std::ios::app|std::ios::binary)<<"original uncommitted bytes";
    const auto length=std::filesystem::file_size(source/"journal");FileJournal s(source.string()),d(dest.string());CommittedReplay replay(s);Inbox in(d);
    EXPECT_FALSE(replay.source_complete());EXPECT_GT(s.uncommitted_bytes(),0U);EXPECT_EQ(replay.acknowledge(ack(session(),1)),Result::NotReady);
    EXPECT_EQ(replay.acknowledge(ack(fault(),2)),Result::NotReady);
    while(auto packet=replay.next()){const auto got=in.receive(*packet);ASSERT_TRUE(got.ack);ASSERT_EQ(replay.acknowledge(*got.ack),Result::Accepted);}
    EXPECT_EQ(replay.acknowledged(),2U);EXPECT_EQ(s.committed().size(),2U);EXPECT_EQ(std::filesystem::file_size(source/"journal"),length);EXPECT_FALSE(s.writable());
    EXPECT_EQ(replay.acknowledge(ack(session(),1,5678)),Result::Invalid);EXPECT_EQ(replay.acknowledge(ack(fault(),1)),Result::Conflict);
}
} // namespace
