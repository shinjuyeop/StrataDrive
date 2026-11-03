#include "continuity_service_fixture.hpp"
#include "diagnostics_fixture.hpp"
#include <limits>

namespace {
using namespace continuity_fixture;
TEST_F(ContinuityServiceTest, AuthenticatedReviewAndSeparateClearKeepTheGuardAcrossAllDurableWrites) {
    baseline();fresh();ContinuityService service(*writer,bindings,permit(),capture);const auto before=local->committed().size();const auto review=request();
    const auto approved=call(service,review);ASSERT_EQ(approved.status,ServiceStatus::Accepted);EXPECT_EQ(approved.stage,3);EXPECT_FALSE(capture.held);EXPECT_EQ(capture.acquires,1U);EXPECT_EQ(capture.samples,3U);
    EXPECT_FALSE(writer->ledger().find(incident.key)->cleared);EXPECT_EQ(writer->ledger().find(incident.key)->condition,Condition::Passed);
    EXPECT_EQ(encode_service_reply(call(service,review)),encode_service_reply(approved));EXPECT_EQ(capture.acquires,1U);EXPECT_EQ(local->committed().size(),before+3);
    const auto& stored=std::get<ContinuityReview>(local->committed()[before+1]);EXPECT_LT(stored.evidence.brake.ns,stored.evidence.drive.ns);EXPECT_LT(stored.evidence.drive.ns,stored.evidence.wheel.ns);EXPECT_LT(stored.evidence.wheel.ns,stored.evidence.now.ns);
    const auto& original_proof=std::get<Event>(local->committed()[before]);const auto& current_passed=std::get<Event>(local->committed()[before+2]);
    EXPECT_EQ(current_passed.source.source.ns,original_proof.source.source.ns);EXPECT_EQ(current_passed.source.sequence,original_proof.source.sequence);
    EXPECT_GT(current_passed.times[static_cast<std::size_t>(Time::Observed)].ns,stored.evidence.now.ns);
    const auto clear=request(2,ServiceOperation::Clear);const auto cleared=call(service,clear);ASSERT_EQ(cleared.status,ServiceStatus::Accepted);EXPECT_EQ(cleared.stage,4);EXPECT_TRUE(writer->ledger().find(incident.key)->cleared);
    EXPECT_EQ(call(service,clear).watermark,cleared.watermark);EXPECT_EQ(capture.acquires,2U);EXPECT_EQ(local->committed().size(),before+4);EXPECT_TRUE(incident.cause_unknown);EXPECT_TRUE(incident.unmapped);
}
TEST_F(ContinuityServiceTest, WrongKernelPrincipalCapabilitySessionIncidentRevisionAndMalformedPacketsCannotCaptureOrWrite) {
    baseline();fresh();const auto base=local->committed().size();auto denied=permit();++denied.pid;ContinuityService no_peer(*writer,bindings,denied,capture);
    EXPECT_EQ(call(no_peer,request()).status,ServiceStatus::Unauthorized);denied=permit();++denied.uid;ContinuityService no_uid(*writer,bindings,denied,capture);EXPECT_EQ(call(no_uid,request()).status,ServiceStatus::Unauthorized);
    ContinuityService service(*writer,bindings,permit(),capture);auto r=request();r.capability[0]^=1;EXPECT_EQ(call(service,r).status,ServiceStatus::Unauthorized);
    r=request();r.disposition=ContinuityDisposition::None;EXPECT_EQ(call(service,r).status,ServiceStatus::Malformed);
    auto bytes=encode_service_request(request());bytes.push_back(0);EXPECT_EQ(packet(service,bytes).status,ServiceStatus::Malformed);bytes=encode_service_request(request());bytes.pop_back();EXPECT_EQ(packet(service,bytes).status,ServiceStatus::Malformed);
    r=request(1);++r.session.epoch;EXPECT_EQ(call(service,r).status,ServiceStatus::Scope);
    r=request(2);++r.incident.sequence;EXPECT_EQ(call(service,r).status,ServiceStatus::Scope);
    r=request(3);++r.revision;EXPECT_EQ(call(service,r).status,ServiceStatus::Revision);
    EXPECT_EQ(call(service,request(4,ServiceOperation::Clear)).status,ServiceStatus::NotReady);EXPECT_EQ(capture.acquires,0U);EXPECT_EQ(local->committed().size(),base);EXPECT_TRUE(writer->ledger().complete());
}
TEST_F(ContinuityServiceTest, FailedFreezeUnsafeOrStaleActualAndChangedSourceCutCannotClear) {
    baseline();fresh();central.now+=40000000;ContinuityService service(*writer,bindings,permit(),capture);const auto base=local->committed().size();
    capture.available=false;EXPECT_EQ(call(service,request(1)).status,ServiceStatus::Freeze);capture.available=true;
    capture.speed=.02;EXPECT_EQ(call(service,request(2)).status,ServiceStatus::Inspection);capture.speed=0;
    capture.age=30000001;EXPECT_EQ(call(service,request(3)).status,ServiceStatus::Inspection);capture.age=0;
    capture.inhibited=false;EXPECT_EQ(call(service,request(4)).status,ServiceStatus::Inspection);capture.inhibited=true;
    EXPECT_EQ(local->committed().size(),base);ASSERT_EQ(call(service,request(5)).status,ServiceStatus::Accepted);
    const auto clear=request(6,ServiceOperation::Clear);auto extra=incident;extra.kind=Kind::Observation;extra.id.sequence=2;extra.session=global.session;extra.session_enable=global.session_enable;
    ASSERT_EQ(out[0]->submit(extra),Result::Accepted);transfer();EXPECT_EQ(call(service,clear).status,ServiceStatus::Inspection);EXPECT_FALSE(writer->ledger().find(incident.key)->cleared);EXPECT_FALSE(capture.held);
}
TEST_F(ContinuityServiceTest, PhysicalEvidenceIsResampledBetweenCommitsAndRequestNumbersCannotBeReused) {
    baseline();fresh();ContinuityService service(*writer,bindings,permit(),capture);capture.fail_sample=2;
    const auto r=request();const auto base=local->committed().size();auto answer=call(service,r);EXPECT_EQ(answer.status,ServiceStatus::Physical);EXPECT_EQ(answer.stage,1);EXPECT_EQ(local->committed().size(),base+1);EXPECT_TRUE(writer->ledger().unmapped());EXPECT_FALSE(capture.held);
    EXPECT_EQ(call(service,r).stage,1);auto changed=r;++changed.revision;EXPECT_EQ(call(service,changed).status,ServiceStatus::Conflict);
    capture.fail_sample=0;ASSERT_EQ(call(service,request(2)).status,ServiceStatus::Accepted);EXPECT_EQ(writer->ledger().find(incident.key)->condition,Condition::Passed);
    EXPECT_THROW((ContinuityService{*writer,bindings,permit(),capture}),std::invalid_argument);
}
TEST_F(ContinuityServiceTest, FiniteRequestBudgetDoesNotEvictRepliesAndStorageFailureNeverPublishesPassed) {
    baseline();fresh();ContinuityService service(*writer,bindings,permit(),capture);
    for(std::uint64_t n=1;n<=ContinuityService::request_budget;++n){auto r=request(n);++r.revision;ASSERT_EQ(call(service,r).status,ServiceStatus::Revision);}
    EXPECT_EQ(call(service,request(33)).status,ServiceStatus::Capacity);EXPECT_EQ(capture.acquires,0U);
    auto first=request();++first.revision;EXPECT_EQ(call(service,first).status,ServiceStatus::Revision);
    diagnostics_fixture::MemoryJournal memory;memory.entries=local->committed();Recorder w(memory);ContinuityService broken(w,bindings,permit(),capture);memory.fail=true;
    EXPECT_EQ(call(broken,request()).status,ServiceStatus::Storage);EXPECT_FALSE(w.ledger().complete());EXPECT_NE(w.ledger().find(incident.key)->condition,Condition::Passed);EXPECT_FALSE(capture.held);
}
TEST_F(ContinuityServiceTest, InterruptedReplacementReviewCannotReuseAnOlderPassedAndCaptureExceptionsReleaseTheGuard) {
    baseline();fresh();ContinuityService service(*writer,bindings,permit(),capture);ASSERT_EQ(call(service,request()).status,ServiceStatus::Accepted);
    capture.fail_sample=6;const auto failed=call(service,request(2));EXPECT_EQ(failed.status,ServiceStatus::Physical);EXPECT_EQ(failed.stage,2);
    EXPECT_EQ(call(service,request(3,ServiceOperation::Clear)).status,ServiceStatus::NotReady);EXPECT_FALSE(capture.held);
    capture.throw_sample=true;EXPECT_EQ(call(service,request(4)).status,ServiceStatus::Storage);EXPECT_FALSE(capture.held);
    capture.throw_sample=false;EXPECT_EQ(call(service,request(5)).status,ServiceStatus::Storage);EXPECT_FALSE(writer->ledger().find(incident.key)->cleared);
}
TEST_F(ContinuityServiceTest, CodecIsCanonicalBoundedAndActualAdapterRejectsForeignEpochClockCommandAndMissingWheel) {
    baseline();fresh();const auto r=request();const auto bytes=encode_service_request(r);ASSERT_EQ(bytes.size(),76U);EXPECT_EQ(encode_service_request(decode_service_request(bytes)),bytes);
    for(std::size_t i=0;i<bytes.size();++i)EXPECT_THROW(decode_service_request({bytes.begin(),bytes.begin()+static_cast<std::ptrdiff_t>(i)}),std::invalid_argument);
    for(unsigned i=0;i<4;++i){auto bad=bytes;if(i==0)bad[3]=2;if(i==1)bad[74]=1;if(i==2)bad[72]=3;if(i==3)bad[73]=0;EXPECT_THROW(decode_service_request(bad),std::invalid_argument);}
    auto maximum=r;maximum.number=std::numeric_limits<std::uint64_t>::max();EXPECT_THROW(decode_service_request(encode_service_request(maximum)),std::invalid_argument);
    auto cut=capture.acquire();auto e=cut->sample();ASSERT_TRUE(stationary_evidence(e));central::NormalDriveReadinessInputs input;input.epoch=global.session.epoch;input.session_enable_ns=global.session_enable.ns;
    input.rear.drive_actual.emplace();auto& d=*input.rear.drive_actual;d.kind=can::DriveFrameKind::Actual;d.epoch=input.epoch;d.source_time_ns=e.drive.ns;d.torque_nm=0;d.wheel_speed=can::DriveWheelSpeed{0,e.wheel.ns};
    input.front.brake_actual.emplace();auto& b=*input.front.brake_actual;b.kind=can::BrakeFrameKind::Actual;b.epoch=input.epoch;b.source_time_ns=e.brake.ns;b.pressure_pa=100000;
    EXPECT_TRUE(stationary_evidence(capture_service_evidence(context(99),global.session,global.session_enable,input,e.now,true)));
    ++d.epoch;EXPECT_FALSE(capture_service_evidence(context(99),global.session,global.session_enable,input,e.now,true).current_streams_valid);--d.epoch;
    d.kind=can::DriveFrameKind::Command;EXPECT_FALSE(capture_service_evidence(context(99),global.session,global.session_enable,input,e.now,true).current_streams_valid);d.kind=can::DriveFrameKind::Actual;
    d.wheel_speed.reset();EXPECT_FALSE(capture_service_evidence(context(99),global.session,global.session_enable,input,e.now,true).current_streams_valid);
    auto foreign=e.now;++foreign.instance;EXPECT_FALSE(capture_service_evidence(context(99),global.session,global.session_enable,input,foreign,true).current_streams_valid);
}
} // namespace
