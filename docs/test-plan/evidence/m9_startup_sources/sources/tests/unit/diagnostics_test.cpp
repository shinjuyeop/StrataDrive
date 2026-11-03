#include "diagnostics_fixture.hpp"
#include <gtest/gtest.h>
#include <atomic>
#include <limits>
#include <thread>

namespace {
using namespace diagnostics_fixture;
class DiagnosticsTest : public ::testing::Test {
protected:
    Ledger ledger;
    void start() { ASSERT_EQ(ledger.record(session()),Result::Accepted); }
    void recover(const Event& f) {
        const auto p=proof(f); ASSERT_EQ(ledger.record(p),Result::Accepted);
        ASSERT_EQ(ledger.record(passed(p)),Result::Accepted);
    }
};
TEST_F(DiagnosticsTest, NormalStartupAndObservationDoNotCreateDtc) {
    start(); auto e=session(2); e.kind=Kind::Observation;
    ASSERT_EQ(ledger.record(e),Result::Accepted); EXPECT_TRUE(ledger.records().empty());
    EXPECT_TRUE(ledger.complete());
}
TEST(DiagnosticsConfig, BoundedNonzeroLimitsAndProducerIdentityRequired) {
    EXPECT_THROW(Ledger(Limits{0,1,1,1}),std::invalid_argument);
    EXPECT_THROW(Ledger(Limits{4097,1,1,1}),std::invalid_argument);
    EXPECT_THROW(EventQueue(0,20),std::invalid_argument);
}
TEST_F(DiagnosticsTest, FirstQualifiedFaultIsImmediateAndPreservesOrigin) {
    start(); auto f=fault(); f.profile=42; f.times[0]=stamp(999999999);
    ASSERT_EQ(ledger.record(f),Result::Accepted); const auto* r=ledger.find(f.key); ASSERT_NE(r,nullptr);
    EXPECT_EQ(r->condition,Condition::Failed); EXPECT_EQ(r->count,1U); EXPECT_EQ(r->latch,Latch::Set);
    EXPECT_EQ(r->first_detected.ns,1000000002U); EXPECT_EQ(ledger.events().back().profile,42U);
}
TEST_F(DiagnosticsTest, ReplayAndRepeatedOccurrenceNeverIncreaseCount) {
    start(); auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted);
    const auto revision=ledger.find(f.key)->revision;
    EXPECT_EQ(ledger.record(f),Result::Duplicate); EXPECT_EQ(ledger.find(f.key)->revision,revision);
    f.id.sequence=3; EXPECT_EQ(ledger.record(f),Result::Accepted);
    EXPECT_EQ(ledger.find(f.key)->count,1U); EXPECT_EQ(ledger.find(f.key)->first_event.sequence,2U);
}
TEST_F(DiagnosticsTest, MutatedIdentityFailsWithoutOverwritingFirstCause) {
    start(); auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted); f.native_reason=7;
    EXPECT_EQ(ledger.record(f),Result::Conflict); EXPECT_FALSE(ledger.complete());
    EXPECT_EQ(ledger.events()[1].native_reason,1U); EXPECT_EQ(ledger.find(f.key)->count,1U);
    EXPECT_EQ(ledger.find(f.key)->condition,Condition::Unknown);
}
TEST_F(DiagnosticsTest, PassNeedsMatchingQualifiedProofAndKeepsObservedLatch) {
    start(); auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted);
    auto p=proof(f,3,Proof::Response); ASSERT_EQ(ledger.record(p),Result::Accepted);
    ASSERT_EQ(ledger.record(passed(p)),Result::Accepted); EXPECT_EQ(ledger.find(f.key)->condition,Condition::Failed);
    p=proof(f,5); ASSERT_EQ(ledger.record(p),Result::Accepted);
    ASSERT_EQ(ledger.record(passed(p,6)),Result::Accepted);
    EXPECT_EQ(ledger.find(f.key)->condition,Condition::Passed); EXPECT_EQ(ledger.find(f.key)->latch,Latch::Set);
    EXPECT_EQ(ledger.find(f.key)->count,1U);
}
TEST_F(DiagnosticsTest, PassThenNewFaultCountsExactlyOneNewOccurrence) {
    start(); const auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted); recover(f);
    const auto next=fault(5); ASSERT_EQ(ledger.record(next),Result::Accepted);
    EXPECT_EQ(ledger.find(f.key)->count,2U); EXPECT_EQ(ledger.find(f.key)->condition,Condition::Failed);
    EXPECT_EQ(ledger.find(f.key)->first_event.sequence,2U);
}
TEST_F(DiagnosticsTest, NewEpisodeWithoutPassOrNewEpochIsAProtocolConflict) {
    start(); const auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted);
    EXPECT_EQ(ledger.record(fault(3)),Result::Conflict);
    EXPECT_EQ(ledger.find(f.key)->count,1U); EXPECT_FALSE(ledger.complete());
}
TEST_F(DiagnosticsTest, LateActualAndPassCanBeCorrelatedWithoutRetimestamping) {
    start(); const auto f=fault(),p=proof(f); auto pass=passed(p);
    ASSERT_EQ(ledger.record(pass),Result::Accepted); ASSERT_EQ(ledger.record(p),Result::Accepted);
    EXPECT_TRUE(ledger.records().empty()); ASSERT_EQ(ledger.record(f),Result::Accepted);
    ASSERT_NE(ledger.find(f.key),nullptr); EXPECT_EQ(ledger.find(f.key)->condition,Condition::Passed);
    EXPECT_EQ(ledger.find(f.key)->first_detected.ns,f.times[2].ns);
}
TEST_F(DiagnosticsTest, IndependentSourcesAndMonitorsAreNotAggregatedTogether) {
    start(); auto a=fault(),b=fault(3),c=fault(4); b.key.subject=4; c.key.monitor=3; c.occurrence.monitor=3;
    ASSERT_EQ(ledger.record(a),Result::Accepted); ASSERT_EQ(ledger.record(b),Result::Accepted);
    ASSERT_EQ(ledger.record(c),Result::Accepted); EXPECT_EQ(ledger.records().size(),3U);
}
TEST_F(DiagnosticsTest, NewSessionAndRestartRequireNewCurrentEvidence) {
    start(); const auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted); recover(f);
    ledger.restarted(); EXPECT_EQ(ledger.find(f.key)->condition,Condition::Unknown);
    auto e=session(5); e.kind=Kind::Observation; ASSERT_EQ(ledger.record(e),Result::Accepted);
    EXPECT_EQ(ledger.find(f.key)->condition,Condition::Unknown); // old pass cannot heal a restart
    ASSERT_EQ(ledger.record(session(6,2)),Result::Accepted);
    const auto old=fault(7); ASSERT_EQ(ledger.record(old),Result::Accepted);
    EXPECT_EQ(ledger.find(f.key)->condition,Condition::Unknown);
    EXPECT_EQ(ledger.record(session(8,1)),Result::Invalid);
}
TEST_F(DiagnosticsTest, LostObservationInvalidatesPassAndRequiresLaterRecoveryEvidence) {
    start(); const auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted); recover(f);
    auto lost=f; lost.id.sequence=5; lost.kind=Kind::Unavailable;
    ASSERT_EQ(ledger.record(lost),Result::Accepted); EXPECT_EQ(ledger.find(f.key)->condition,Condition::Unknown);
    auto reused=passed(proof(f),6); ASSERT_EQ(ledger.record(reused),Result::Accepted);
    EXPECT_EQ(ledger.find(f.key)->condition,Condition::Unknown);
    const auto new_proof=proof(f,7); ASSERT_EQ(ledger.record(new_proof),Result::Accepted);
    ASSERT_EQ(ledger.record(passed(new_proof,8)),Result::Accepted);
    EXPECT_EQ(ledger.find(f.key)->condition,Condition::Passed);
}
TEST_F(DiagnosticsTest, ProofBeforeFaultAndDifferentSourceCannotDeclareRecovery) {
    start(); const auto f=fault(4); const auto p=proof(f,2);
    ASSERT_EQ(ledger.record(p),Result::Accepted); ASSERT_EQ(ledger.record(f),Result::Accepted);
    ASSERT_EQ(ledger.record(passed(p,5)),Result::Accepted); EXPECT_EQ(ledger.find(f.key)->condition,Condition::Failed);
    auto other=fault(6); other.id.producer=21; other.occurrence.producer=21;
    EXPECT_EQ(ledger.record(other),Result::Conflict); EXPECT_EQ(ledger.find(f.key)->count,1U);
    EXPECT_EQ(ledger.find(f.key)->condition,Condition::Unknown);
}
TEST_F(DiagnosticsTest, DelayedOlderFaultDoesNotOverwriteLatestOrFirstCausalOrder) {
    start(); auto newest=fault(8); ASSERT_EQ(ledger.record(newest),Result::Accepted);
    const auto oldest=fault(2); ASSERT_EQ(ledger.record(oldest),Result::Accepted);
    const auto* r=ledger.find(oldest.key); EXPECT_EQ(r->first_event.sequence,2U); EXPECT_EQ(r->last_event.sequence,8U);
    EXPECT_EQ(r->state_event.sequence,8U); EXPECT_EQ(r->first_detected.ns,oldest.times[2].ns);
}
TEST_F(DiagnosticsTest, ClearUsesTheActualSessionEnableAndAllTargetsAreAtomic) {
    start(); const auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted); recover(f);
    auto c=clear(*ledger.find(f.key)); c.evidence.enable.ns-=1;
    EXPECT_EQ(ledger.clear(c),Result::NotReady);
    c=clear(*ledger.find(f.key)); const auto second=fault(5,Code::Handoff);
    ASSERT_EQ(ledger.record(second),Result::Accepted); c.targets.push_back({second.key,ledger.find(second.key)->revision}); c.all=true;
    EXPECT_EQ(ledger.clear(c),Result::NotReady); EXPECT_FALSE(ledger.find(f.key)->cleared);
    const auto p=proof(second,6,Proof::Handoff); ASSERT_EQ(ledger.record(p),Result::Accepted);
    ASSERT_EQ(ledger.record(passed(p,7)),Result::Accepted);
    c.targets[1].revision=ledger.find(second.key)->revision;
    ASSERT_EQ(ledger.clear(c),Result::Accepted); EXPECT_TRUE(ledger.find(f.key)->cleared); EXPECT_TRUE(ledger.find(second.key)->cleared);
}
TEST(DiagnosticsTime, DomainsInstancesAndTrustMustMatchBeforeSubtraction) {
    auto a=stamp(),b=stamp(1); EXPECT_TRUE(comparable(a,b));
    b.instance=8; EXPECT_FALSE(comparable(a,b)); b=a; b.domain=Domain::Monotonic; EXPECT_FALSE(comparable(a,b));
    b=a; b.trusted=false; EXPECT_FALSE(comparable(a,b)); b={}; EXPECT_FALSE(comparable(a,b));
}
TEST_F(DiagnosticsTest, ClearRequiresPassedFreshStationaryAndInhibitedEvidence) {
    start(); const auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted);
    EXPECT_EQ(ledger.clear(clear(*ledger.find(f.key))),Result::NotReady); recover(f);
    const auto good=clear(*ledger.find(f.key));
    for(unsigned n=0;n<7;++n) {
        auto c=good;
        if(n==0) c.evidence.wheel_rad_s=.011;
        if(n==1) c.evidence.pressure_pa=99999;
        if(n==2) c.evidence.torque_nm=.1001;
        if(n==3) c.evidence.normal_dispatch_inhibited=false;
        if(n==4) c.evidence.wheel.ns=c.evidence.now.ns-30000001;
        if(n==5) c.evidence.drive.instance=9;
        if(n==6) c.evidence.pressure_pa=std::numeric_limits<double>::quiet_NaN();
        EXPECT_EQ(ledger.clear(c),Result::NotReady); EXPECT_FALSE(ledger.find(f.key)->cleared);
    }
    ASSERT_EQ(ledger.clear(good),Result::Accepted); EXPECT_TRUE(ledger.find(f.key)->cleared);
    EXPECT_EQ(ledger.find(f.key)->latch,Latch::Set); EXPECT_EQ(ledger.clear(good),Result::Duplicate);
}
TEST_F(DiagnosticsTest, ClearIsAtomicAndRevisionCheckedAcrossRecurrence) {
    start(); const auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted); recover(f);
    auto c=clear(*ledger.find(f.key)); ASSERT_EQ(ledger.record(fault(5,Code::Handoff)),Result::Accepted);
    c.all=true; EXPECT_EQ(ledger.clear(c),Result::NotReady); c.all=false;
    ASSERT_EQ(ledger.record(fault(6)),Result::Accepted);
    EXPECT_EQ(ledger.clear(c),Result::NotReady); EXPECT_FALSE(ledger.find(f.key)->cleared);
}
TEST_F(DiagnosticsTest, ClearRejectsDuplicateTargetsAndDoesNotPartiallyErase) {
    start(); const auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted); recover(f);
    auto c=clear(*ledger.find(f.key)); c.targets.push_back(c.targets.front());
    EXPECT_EQ(ledger.clear(c),Result::Invalid); EXPECT_FALSE(ledger.find(f.key)->cleared);
}
TEST_F(DiagnosticsTest, ClearedHistoryIsKeptAndOnlyANewerFaultOpensNextGeneration) {
    start(); const auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted);
    const auto p=proof(f,6); ASSERT_EQ(ledger.record(p),Result::Accepted); ASSERT_EQ(ledger.record(passed(p,7)),Result::Accepted);
    ASSERT_EQ(ledger.clear(clear(*ledger.find(f.key))),Result::Accepted);
    ASSERT_EQ(ledger.record(fault(4)),Result::Accepted); EXPECT_TRUE(ledger.find(f.key)->cleared);
    ASSERT_EQ(ledger.record(fault(8)),Result::Accepted);
    EXPECT_FALSE(ledger.find(f.key)->cleared); EXPECT_EQ(ledger.find(f.key)->generation,2U); EXPECT_EQ(ledger.find(f.key)->count,1U);
    EXPECT_EQ(ledger.events().size(),6U);
}
TEST(DiagnosticsBounds, EventRecordAndEpisodeCapacityNeverSilentlyEvict) {
    for(unsigned n=0;n<3;++n) {
        auto limits=Limits{}; if(n==0) limits.events=2; if(n==1) limits.records=1; if(n==2) limits.occurrences=1;
        Ledger ledger(limits); ASSERT_EQ(ledger.record(session()),Result::Accepted);
        const auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted);
        auto next=fault(3); next.key.subject=4;
        EXPECT_EQ(ledger.record(next),Result::Capacity); EXPECT_FALSE(ledger.complete());
        EXPECT_EQ(ledger.find(f.key)->count,1U); EXPECT_EQ(ledger.records().size(),1U);
    }
}
TEST_F(DiagnosticsTest, UnmappedAndRecordingLossCannotBeClearedAsHealthy) {
    start(); const auto f=fault(); ASSERT_EQ(ledger.record(f),Result::Accepted); recover(f);
    auto raw=session(5); raw.kind=Kind::Observation; raw.unmapped=true;
    ASSERT_EQ(ledger.record(raw),Result::Accepted); EXPECT_TRUE(ledger.unmapped());
    EXPECT_EQ(ledger.clear(clear(*ledger.find(f.key))),Result::NotReady);
    raw.id.sequence=6; raw.kind=Kind::Gap; ASSERT_EQ(ledger.record(raw),Result::Accepted);
    EXPECT_FALSE(ledger.complete()); EXPECT_EQ(ledger.find(f.key)->condition,Condition::Unknown);
}
TEST(DiagnosticsCodec, CanonicalRoundTripPreservesMetadataAndRejectsTruncation) {
    auto f=fault(); f.source={true,90,99,1,stamp(11),stamp(22)}; f.related={10,21,32}; f.measured=.125;
    f.times[0]={Domain::Monotonic,9,123,true,false}; f.expected_roles=255; f.received_roles=127;
    const auto bytes=encode(f); EXPECT_EQ(encode(decode(bytes)),bytes);
    for(std::size_t i=0;i<bytes.size();++i) EXPECT_THROW(decode(std::vector<std::uint8_t>(bytes.begin(),bytes.begin()+static_cast<std::ptrdiff_t>(i))),std::runtime_error);
    auto bad=bytes; bad.push_back(0); EXPECT_THROW(decode(bad),std::runtime_error);
    Ledger ledger; ASSERT_EQ(ledger.record(session()),Result::Accepted); ASSERT_EQ(ledger.record(f),Result::Accepted);
    auto c=clear(*ledger.find(f.key)); EXPECT_EQ(encode(decode(encode(c))),encode(c));
}
TEST(DiagnosticsRecorder, FailedStorageNeverClaimsDurabilityOrAppliesClear) {
    MemoryJournal store; Recorder recorder(store); ASSERT_TRUE(recorder.record(session()).durable);
    auto f=fault(); ASSERT_TRUE(recorder.record(f).durable); ASSERT_TRUE(recorder.record(proof(f)).durable);
    ASSERT_TRUE(recorder.record(passed(proof(f))).durable);
    const auto c=clear(*recorder.ledger().find(f.key)); store.fail=true;
    EXPECT_FALSE(recorder.clear(c).durable); EXPECT_FALSE(recorder.ledger().find(f.key)->cleared);
    EXPECT_FALSE(recorder.ledger().complete()); EXPECT_EQ(store.entries.size(),4U);
}
TEST(DiagnosticsRecorder, InMemoryFaultIsNotReportedDurableAfterAWriteFailure) {
    MemoryJournal store; Recorder recorder(store); ASSERT_TRUE(recorder.record(session()).durable); store.fail=true;
    const auto f=fault(); EXPECT_FALSE(recorder.record(f).durable); EXPECT_FALSE(recorder.record(f).durable);
    EXPECT_EQ(recorder.ledger().find(f.key)->count,1U); EXPECT_EQ(store.entries.size(),1U);
}
TEST(DiagnosticsRecorder, QueueHealthReachesWriterEvenWhenNoDroppedEventCanBeEnqueued) {
    MemoryJournal store; Recorder recorder(store); EventQueue queue(10,20);
    ASSERT_TRUE(queue.publish(session())); ASSERT_TRUE(queue.publish(fault()));
    EXPECT_EQ(recorder.drain(queue,1),1U); EXPECT_EQ(store.entries.size(),1U);
    EXPECT_EQ(recorder.drain(queue),1U); EXPECT_EQ(store.entries.size(),2U);
    for(std::size_t n=0;n<EventQueue::kCapacity;++n) {
        auto e=session(n+3); e.kind=Kind::Observation; ASSERT_TRUE(queue.publish(e));
    }
    EXPECT_FALSE(queue.publish(session(1000))); EXPECT_EQ(recorder.drain(queue,0),0U);
    EXPECT_FALSE(recorder.ledger().complete()); EXPECT_FALSE(store.healthy); EXPECT_EQ(store.entries.size(),2U);
}
TEST(DiagnosticsQueue, OverflowAndIdentityLossAreStickyWithoutDestroyingQueuedEvents) {
    EventQueue queue(10,20);
    for(std::size_t i=1;i<=EventQueue::kCapacity;++i) ASSERT_TRUE(queue.publish(session(i)));
    EXPECT_FALSE(queue.publish(session(257))); EXPECT_EQ(queue.health().dropped,1U); EXPECT_EQ(queue.health().first_lost_sequence,257U);
    for(std::size_t i=1;i<=EventQueue::kCapacity;++i) { Event e; ASSERT_TRUE(queue.pop(e)); EXPECT_EQ(e.id.sequence,i); }
    Event e; EXPECT_FALSE(queue.pop(e)); ASSERT_TRUE(queue.publish(session(258)));
    auto wrong=session(259); wrong.id.producer=21; EXPECT_FALSE(queue.publish(wrong));
    EXPECT_TRUE(queue.health().identity_error); EXPECT_EQ(queue.health().dropped,2U);
}
TEST(DiagnosticsQueue, SingleProducerConsumerPreserveEveryPayloadThroughWraparound) {
    EventQueue queue(10,20); constexpr std::uint64_t count=20000; std::atomic<bool> mismatch{false};
    std::thread consumer([&] {
        for(std::uint64_t n=1;n<=count;++n) {
            Event e; while(!queue.pop(e)) std::this_thread::yield();
            if(e.id.sequence!=n || e.profile!=n*7) mismatch.store(true);
        }
    });
    for(std::uint64_t n=1;n<=count;++n) { auto e=session(n); e.profile=n*7; while(!queue.publish(e)) std::this_thread::yield(); }
    consumer.join(); EXPECT_FALSE(mismatch.load());
}
Event startup_attempt(std::uint64_t seq=1,std::uint32_t epoch=1) {
    auto e=session(seq,epoch); e.kind=Kind::Attempt; e.session_enable={};
    e.source={true,e.id.producer,epoch,epoch,stamp(),{}}; return e;
}
TEST(DiagnosticsStartup, AttemptAdmitsFailureWithoutPretendingReleaseAndPromotionPreservesIt) {
    Ledger ledger; ASSERT_EQ(ledger.record(startup_attempt()),Result::Accepted);
    auto f=fault(2,Code::Startup); f.session_enable={}; ASSERT_EQ(ledger.record(f),Result::Accepted);
    ASSERT_EQ(ledger.find(f.key)->condition,Condition::Failed);
    auto release=session(3); release.expected_roles=release.received_roles=255;
    ASSERT_EQ(ledger.record(release),Result::Accepted); EXPECT_EQ(ledger.find(f.key)->condition,Condition::Failed);
    auto p=proof(f,4,Proof::Control); p.session_enable=stamp(); ASSERT_EQ(ledger.record(p),Result::Accepted);
    ASSERT_EQ(ledger.record(passed(p,5)),Result::Accepted); EXPECT_EQ(ledger.find(f.key)->condition,Condition::Failed);
}
TEST(DiagnosticsStartup, PrereleaseProofCannotBeStoredForRetroactivePassingOrCleared) {
    Ledger ledger; ASSERT_EQ(ledger.record(startup_attempt()),Result::Accepted); auto f=fault(2,Code::Startup); f.session_enable={};
    ASSERT_EQ(ledger.record(f),Result::Accepted); auto copy=ledger;
    EXPECT_EQ(copy.record(proof(f,3,Proof::Control)),Result::NotReady);
    EXPECT_EQ(ledger.clear(clear(*ledger.find(f.key))),Result::NotReady);
    EXPECT_EQ(ledger.events().size(),2U);
}
TEST(DiagnosticsStartup, ReleaseRequiresSameIssuerAndFullRoleMaskAndMonotonicEnable) {
    for(unsigned variant=0;variant<3;++variant) {
        Ledger ledger; ASSERT_EQ(ledger.record(startup_attempt()),Result::Accepted); auto release=session(2); release.expected_roles=release.received_roles=255;
        if(variant==0) release.id.producer=99;
        if(variant==1) release.received_roles=127;
        if(variant==2) release.session_enable=stamp(999999999);
        EXPECT_EQ(ledger.record(release),Result::Invalid);
    }
}
TEST(DiagnosticsStartup, NewAttemptMakesHistoryUnknownAndFullNewReleasePermitsNewProof) {
    Ledger ledger; ASSERT_EQ(ledger.record(startup_attempt()),Result::Accepted); auto f=fault(2,Code::Startup); f.session_enable={};
    ASSERT_EQ(ledger.record(f),Result::Accepted); ASSERT_EQ(ledger.record(startup_attempt(3,2)),Result::Accepted);
    EXPECT_EQ(ledger.find(f.key)->condition,Condition::Unknown); auto release=session(4,2); release.expected_roles=release.received_roles=255;
    ASSERT_EQ(ledger.record(release),Result::Accepted); auto p=proof(f,5,Proof::Control,2); p.session_enable=stamp();
    ASSERT_EQ(ledger.record(p),Result::Accepted); ASSERT_EQ(ledger.record(passed(p,6)),Result::Accepted);
    EXPECT_EQ(ledger.find(f.key)->condition,Condition::Passed); EXPECT_EQ(ledger.find(f.key)->count,1U);
}
} // namespace
