#include "continuity_review_fixture.hpp"
#include "diagnostics_fixture.hpp"
#include <limits>

namespace {
using namespace continuity_fixture;
TEST_F(ContinuityReviewTest, ExplicitUnknownHistoryDispositionAndFreshRecordingQualifyOnlyCurrentConditionBeforeClear) {
    baseline();auto before=encode(incident);EXPECT_FALSE(inspector.prepare(writer->ledger(),incident.id,global,streams(),ContinuityDisposition::AcceptUnknownHistory,evidence(),1).plan);
    fresh();auto p=plan();ASSERT_TRUE(writer->record(p.proof).durable);EXPECT_TRUE(writer->ledger().unmapped());
    ASSERT_TRUE(writer->review(p.review).durable);EXPECT_FALSE(writer->ledger().unmapped());EXPECT_EQ(writer->ledger().find(incident.key)->condition,Condition::Unknown);
    EXPECT_EQ(writer->clear(clear_request()).result,Result::NotReady);ASSERT_TRUE(writer->record(p.passed).durable);
    ASSERT_EQ(writer->ledger().find(incident.key)->condition,Condition::Passed);const auto c=clear_request();ASSERT_TRUE(writer->clear(c).durable);
    EXPECT_EQ(writer->clear(c).result,Result::Duplicate);EXPECT_EQ(writer->review(p.review).result,Result::Duplicate);
    EXPECT_EQ(encode(writer->ledger().events()[2]),before);EXPECT_TRUE(incident.cause_unknown);EXPECT_TRUE(incident.unmapped);EXPECT_EQ(writer->ledger().find(incident.key)->count,1U);
    const auto bytes=encode(p.review);EXPECT_EQ(encode(decode(bytes)),bytes);for(std::size_t i=0;i<bytes.size();++i)EXPECT_THROW(decode({bytes.begin(),bytes.begin()+static_cast<std::ptrdiff_t>(i)}),std::runtime_error);
}
TEST_F(ContinuityReviewTest, ManifestAndFrozenCoverageRejectOmissionForeignBindingPendingLossAndIncompleteStorage) {
    baseline();fresh();const auto e=evidence();const auto inspect=[&](auto snapshot){return inspector.prepare(writer->ledger(),incident.id,global,snapshot,ContinuityDisposition::AcceptUnknownHistory,e,1);};
    auto states=streams();states.pop_back();EXPECT_EQ(inspect(states).blocked,ReviewBlock::Streams);
    states=streams();states[0].source=replicas[1].get();EXPECT_EQ(inspect(states).blocked,ReviewBlock::Streams);
    states=streams();--states[0].acknowledged;EXPECT_EQ(inspect(states).blocked,ReviewBlock::Pending);
    states=streams();states[0].pending=1;EXPECT_EQ(inspect(states).blocked,ReviewBlock::Pending);
    states=streams();states[0].queue={1,7,false};EXPECT_EQ(inspect(states).blocked,ReviewBlock::Pending);
    sources[0]->invalidate();EXPECT_EQ(inspect(streams()).blocked,ReviewBlock::Storage);EXPECT_TRUE(writer->ledger().unmapped());
    for(const auto& manifest:std::vector<std::vector<StreamBinding>>{{},{{0,30}},{{500,99}},{{500,30},{500,31}},{{500,30},{501,30}},std::vector<StreamBinding>(33,{500,30})})EXPECT_THROW((ContinuityInspector{context(99),manifest}),std::invalid_argument);
}
TEST_F(ContinuityReviewTest, RequestAndServiceStateCannotSubstituteForNewGlobalReleaseOrExactOriginalContext) {
    baseline();fresh();auto e=evidence();EXPECT_FALSE(inspector.prepare(writer->ledger(),incident.id,global,streams(),ContinuityDisposition::None,e,1).plan);
    for(unsigned n=0;n<6;++n){auto bad=e;if(n==0)bad.normal_dispatch_inhibited=false;if(n==1)bad.current_streams_valid=false;if(n==2)bad.wheel_rad_s=.02;if(n==3)bad.torque_nm=1;if(n==4)bad.pressure_pa=0;if(n==5)bad.wheel.ns-=30000001;
        EXPECT_EQ(inspector.prepare(writer->ledger(),incident.id,global,streams(),ContinuityDisposition::AcceptUnknownHistory,bad,1).blocked,ReviewBlock::Request);}
    auto bad=global;bad.received_roles=127;EXPECT_EQ(inspector.prepare(writer->ledger(),incident.id,bad,streams(),ContinuityDisposition::AcceptUnknownHistory,e,1).blocked,ReviewBlock::Session);
    EXPECT_FALSE(inspector.prepare(writer->ledger(),incident.id,global,streams(),ContinuityDisposition::AcceptUnknownHistory,e,std::numeric_limits<std::uint64_t>::max()).plan);
}
TEST_F(ContinuityReviewTest, ReviewRejectsStaleRevisionWrongProofCutAndUnrelatedUnknownCauseWithoutTaintingARefusedRequest) {
    baseline();fresh();const auto p=plan();ASSERT_TRUE(writer->record(p.proof).durable);
    for(unsigned n=0;n<7;++n){auto bad=p.review;if(n==0)++bad.revision;if(n==1)bad.disposition=ContinuityDisposition::None;if(n==2)++bad.proof_event.sequence;if(n==3)bad.streams[0].tip_crc^=1;if(n==4)bad.streams.push_back(bad.streams[0]);if(n==5)bad.evidence.now.ns+=30000001;if(n==6)bad.incident=p.proof.id;
        EXPECT_NE(writer->review(bad).result,Result::Accepted);EXPECT_TRUE(writer->ledger().complete());EXPECT_TRUE(writer->ledger().unmapped());}
    auto unknown=p.proof;unknown.id.sequence=90;unknown.proof=Proof::None;unknown.key={};unknown.occurrence={};unknown.unmapped=true;ASSERT_TRUE(writer->record(unknown).durable);
    approve(p);EXPECT_TRUE(writer->ledger().unmapped());EXPECT_EQ(writer->clear(clear_request()).result,Result::NotReady);
}
TEST_F(ContinuityReviewTest, PassedBeforeApprovalCannotBePromotedRetroactivelyAndRestartRequiresANewInspection) {
    baseline();fresh();const auto p=plan();ASSERT_TRUE(writer->record(p.proof).durable);ASSERT_TRUE(writer->record(p.passed).durable);ASSERT_TRUE(writer->review(p.review).durable);
    auto note=p.proof;note.id.sequence=4;note.proof=Proof::None;ASSERT_TRUE(writer->record(note).durable);EXPECT_EQ(writer->ledger().find(incident.key)->condition,Condition::Unknown);
    writer.reset();local.reset();local=std::make_unique<FileJournal>((root/"case").string());writer=std::make_unique<Recorder>(*local);
    EXPECT_EQ(writer->review(p.review).result,Result::Duplicate);auto stale=p.review;stale.id.sequence=9;stale.revision=writer->ledger().find(incident.key)->revision;EXPECT_EQ(writer->review(stale).result,Result::NotReady);note.id.sequence=5;ASSERT_TRUE(writer->record(note).durable);EXPECT_EQ(writer->ledger().find(incident.key)->condition,Condition::Unknown);
    fresh(4);const auto next=plan(10);approve(next);EXPECT_TRUE(writer->clear(clear_request()).durable);
}
TEST_F(ContinuityReviewTest, ReviewStorageFailureConflictingIdentityAndLegacyRegistryNeverGrantAServiceClear) {
    baseline();fresh();const auto p=plan();ASSERT_TRUE(writer->record(p.proof).durable);
    {diagnostics_fixture::MemoryJournal broken;broken.entries=local->committed();broken.entries.pop_back();Recorder w(broken);ASSERT_TRUE(w.record(p.proof).durable);broken.fail=true;
        EXPECT_EQ(w.review(p.review).result,Result::StorageFailure);EXPECT_TRUE(w.ledger().unmapped());EXPECT_FALSE(w.ledger().complete());}
    ASSERT_TRUE(writer->review(p.review).durable);auto conflict=p.review;conflict.streams[0].tip_crc^=1;
    EXPECT_EQ(writer->review(conflict).result,Result::Conflict);EXPECT_FALSE(local->writable());EXPECT_FALSE(writer->ledger().complete());
    FileJournal::initialize((root/"legacy").string(),9001,{},3);FileJournal legacy((root/"legacy").string());EXPECT_FALSE(legacy.append(p.review));EXPECT_TRUE(legacy.committed().empty());
}
TEST_F(ContinuityReviewTest, EveryUnreviewedIncidentAndConcurrentRevisionChangeContinueToBlockClear) {
    baseline();fresh();const auto p=plan();ASSERT_TRUE(writer->record(p.proof).durable);
    auto changed=p.proof;changed.id.sequence=4;changed.kind=Kind::Unavailable;changed.proof=Proof::None;ASSERT_TRUE(writer->record(changed).durable);
    EXPECT_EQ(writer->review(p.review).result,Result::NotReady);const auto current=plan(10);approve(current);
    const auto other=continuity_fault(context((1ULL<<32)|31),31,2,Component::Rear,3,global.session_enable.ns,global.session_enable.ns-1,central.now);
    ASSERT_TRUE(writer->record(other).durable);EXPECT_TRUE(writer->ledger().unmapped());EXPECT_EQ(writer->clear(clear_request()).result,Result::NotReady);
    EXPECT_EQ(writer->ledger().find(incident.key)->condition,Condition::Passed);EXPECT_EQ(writer->ledger().find(other.key)->condition,Condition::Failed);
}
TEST_F(ContinuityReviewTest, MaintenanceCapacityIsSharedAndCannotEvictAReviewToMakeRoomForClear) {
    baseline();fresh();const auto p=plan();diagnostics_fixture::MemoryJournal limited;limited.config.clears=1;limited.entries=local->committed();Recorder w(limited);
    ASSERT_TRUE(w.record(p.proof).durable);ASSERT_TRUE(w.review(p.review).durable);ASSERT_TRUE(w.record(p.passed).durable);
    auto request=clear_request();request.targets[0].revision=w.ledger().find(incident.key)->revision;
    EXPECT_EQ(w.clear(request).result,Result::Capacity);EXPECT_FALSE(w.ledger().complete());EXPECT_FALSE(w.ledger().find(incident.key)->cleared);EXPECT_EQ(w.ledger().find(incident.key)->count,1U);
}
} // namespace
