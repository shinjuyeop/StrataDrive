#include "diagnostics_fixture.hpp"
#include "diagnostics_journal.hpp"
#include <gtest/gtest.h>
#include <array>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <system_error>

namespace {
using namespace diagnostics_fixture;
class DiagnosticsJournal : public ::testing::Test {
protected:
    std::filesystem::path root,path;
    void SetUp() override {
        std::array<char,48> name{}; const std::string pattern="/tmp/stratadrive-diagnostics-XXXXXX";
        std::copy(pattern.begin(),pattern.end(),name.begin()); const auto* p=mkdtemp(name.data());
        ASSERT_NE(p,nullptr); root=p; path=root/"store";
    }
    void TearDown() override { std::filesystem::remove_all(root); }
    void initialize() { FileJournal::initialize(path.string(),1234); }
    std::vector<char> read(const char* name) {
        std::ifstream f(path/name,std::ios::binary); return {std::istreambuf_iterator<char>(f),std::istreambuf_iterator<char>()};
    }
    void write(const char* name,const std::vector<char>& bytes) {
        std::ofstream f(path/name,std::ios::binary|std::ios::trunc); f.write(bytes.data(),static_cast<std::streamsize>(bytes.size()));
    }
};
TEST_F(DiagnosticsJournal, ExplicitBootstrapNeverCreatesOrOverwritesAMissingOrExistingStore) {
    EXPECT_THROW(FileJournal(path.string()),std::system_error);
    initialize(); EXPECT_THROW(initialize(),std::system_error);
    FileJournal journal(path.string()); EXPECT_EQ(journal.store_id(),1234U); EXPECT_TRUE(journal.writable());
    EXPECT_TRUE(journal.committed().empty()); EXPECT_EQ(journal.uncommitted_bytes(),0U);
}
TEST_F(DiagnosticsJournal, LifetimeLockRejectsConcurrentWritersAndSymlinkFiles) {
    initialize(); { FileJournal first(path.string()); EXPECT_THROW(FileJournal(path.string()),std::system_error); }
    std::filesystem::rename(path/"journal",root/"outside"); std::filesystem::create_symlink(root/"outside",path/"journal");
    EXPECT_THROW(FileJournal(path.string()),std::system_error);
}
TEST_F(DiagnosticsJournal, CommittedEventsReplayWithUnknownCurrentConditionAndIdempotentCount) {
    initialize(); const auto f=fault();
    {
        FileJournal journal(path.string()); Recorder recorder(journal);
        ASSERT_TRUE(recorder.record(session()).durable); ASSERT_TRUE(recorder.record(f).durable);
        EXPECT_EQ(recorder.record(f).watermark,2U); EXPECT_EQ(journal.committed().size(),2U);
    }
    {
        FileJournal journal(path.string()); Recorder recorder(journal); const auto* r=recorder.ledger().find(f.key);
        ASSERT_NE(r,nullptr); EXPECT_EQ(r->count,1U); EXPECT_EQ(r->condition,Condition::Unknown); EXPECT_EQ(r->latch,Latch::Unknown);
        const auto result=recorder.record(f); EXPECT_EQ(result.result,Result::Duplicate); EXPECT_TRUE(result.durable);
        EXPECT_EQ(result.watermark,2U); EXPECT_EQ(recorder.ledger().find(f.key)->condition,Condition::Unknown);
    }
}
TEST_F(DiagnosticsJournal, DurableClearTombstoneSurvivesReopenAndRequestReplay) {
    initialize(); const auto f=fault(); Clear request;
    {
        FileJournal journal(path.string()); Recorder recorder(journal);
        ASSERT_TRUE(recorder.record(session()).durable); ASSERT_TRUE(recorder.record(f).durable);
        ASSERT_TRUE(recorder.record(proof(f)).durable); ASSERT_TRUE(recorder.record(passed(proof(f))).durable);
        request=clear(*recorder.ledger().find(f.key)); ASSERT_TRUE(recorder.clear(request).durable);
        EXPECT_EQ(journal.committed().size(),5U); EXPECT_EQ(recorder.ledger().find(f.key)->latch,Latch::Set);
    }
    FileJournal journal(path.string()); Recorder recorder(journal);
    ASSERT_TRUE(recorder.ledger().find(f.key)->cleared);
    const auto replay=recorder.clear(request); EXPECT_EQ(replay.result,Result::Duplicate); EXPECT_TRUE(replay.durable);
    EXPECT_EQ(journal.committed().size(),5U); EXPECT_EQ(recorder.ledger().events().size(),4U);
}
TEST_F(DiagnosticsJournal, DataBeyondPreviousWatermarkNeverRestoresAnUncommittedClear) {
    initialize(); const auto f=fault(); std::vector<char> before_clear;
    {
        FileJournal journal(path.string()); Recorder recorder(journal);
        ASSERT_TRUE(recorder.record(session()).durable); ASSERT_TRUE(recorder.record(f).durable);
        ASSERT_TRUE(recorder.record(proof(f)).durable); ASSERT_TRUE(recorder.record(passed(proof(f))).durable);
        before_clear=read("commit"); ASSERT_TRUE(recorder.clear(clear(*recorder.ledger().find(f.key))).durable);
    }
    write("commit",before_clear); const auto original=read("journal");
    FileJournal journal(path.string()); Recorder recorder(journal);
    EXPECT_EQ(journal.committed().size(),4U); EXPECT_GT(journal.uncommitted_bytes(),0U);
    EXPECT_FALSE(journal.writable()); EXPECT_FALSE(recorder.ledger().find(f.key)->cleared);
    EXPECT_FALSE(recorder.ledger().complete()); EXPECT_EQ(read("journal"),original);
}
TEST_F(DiagnosticsJournal, PartialTailIsRetainedAndMissingCommittedBytesAreRejected) {
    initialize(); { FileJournal journal(path.string()); Recorder recorder(journal); ASSERT_TRUE(recorder.record(session()).durable); }
    const auto committed=read("journal"); auto bytes=committed; bytes.insert(bytes.end(),{'S','D','D'}); write("journal",bytes);
    { FileJournal journal(path.string()); EXPECT_EQ(journal.uncommitted_bytes(),3U); EXPECT_FALSE(journal.writable()); EXPECT_EQ(read("journal"),bytes); }
    bytes=committed; bytes.pop_back(); write("journal",bytes); EXPECT_THROW(FileJournal(path.string()),std::runtime_error);
}
TEST_F(DiagnosticsJournal, ChecksumsLengthsMagicSequenceAndMetadataAreVerified) {
    initialize(); { FileJournal journal(path.string()); Recorder recorder(journal); ASSERT_TRUE(recorder.record(session()).durable); ASSERT_TRUE(recorder.record(fault()).durable); }
    const auto original=read("journal");
    for(const auto offset : {0U,8U,16U,25U}) {
        auto bytes=original; bytes[offset]^=1; write("journal",bytes);
        EXPECT_THROW(FileJournal(path.string()),std::runtime_error); write("journal",original);
    }
    auto commit=read("commit"); commit.back()^=1; write("commit",commit); EXPECT_THROW(FileJournal(path.string()),std::runtime_error);
}
TEST_F(DiagnosticsJournal, FailedCommitKeepsOldWatermarkAndCannotAcknowledgeClear) {
    initialize(); const auto f=fault();
    {
        FileJournal journal(path.string()); Recorder recorder(journal);
        ASSERT_TRUE(recorder.record(session()).durable); ASSERT_TRUE(recorder.record(f).durable);
        ASSERT_TRUE(recorder.record(proof(f)).durable); ASSERT_TRUE(recorder.record(passed(proof(f))).durable);
        const auto watermark=read("commit"); std::filesystem::create_directory(path/"pending");
        const auto result=recorder.clear(clear(*recorder.ledger().find(f.key)));
        EXPECT_EQ(result.result,Result::StorageFailure); EXPECT_FALSE(result.durable); EXPECT_FALSE(recorder.ledger().find(f.key)->cleared);
        EXPECT_EQ(read("commit"),watermark); EXPECT_FALSE(journal.writable());
    }
    FileJournal journal(path.string()); Recorder recorder(journal);
    EXPECT_EQ(journal.committed().size(),4U); EXPECT_GT(journal.uncommitted_bytes(),0U);
    EXPECT_FALSE(recorder.ledger().find(f.key)->cleared); EXPECT_FALSE(recorder.ledger().complete());
}
TEST_F(DiagnosticsJournal, RejectedMutationRemainsIncompleteAfterAProcessRestart) {
    initialize(); auto f=fault();
    {
        FileJournal journal(path.string()); Recorder recorder(journal);
        ASSERT_TRUE(recorder.record(session()).durable); ASSERT_TRUE(recorder.record(f).durable);
        f.native_reason=2; EXPECT_EQ(recorder.record(f).result,Result::Conflict); EXPECT_FALSE(journal.writable());
    }
    FileJournal journal(path.string()); Recorder recorder(journal);
    EXPECT_FALSE(recorder.ledger().complete()); EXPECT_EQ(journal.committed().size(),2U);
    EXPECT_EQ(recorder.ledger().events().back().native_reason,1U);
}
TEST_F(DiagnosticsJournal, MissingManifestAndHardlinkedDataNeverBecomeAnEmptyStore) {
    initialize(); std::filesystem::create_hard_link(path/"journal",root/"linked");
    EXPECT_THROW(FileJournal(path.string()),std::runtime_error); std::filesystem::remove(root/"linked");
    std::filesystem::remove(path/"manifest"); EXPECT_THROW(FileJournal(path.string()),std::system_error);
}
TEST_F(DiagnosticsJournal, ExtendedCodesRequireExplicitRegistryTwoWithoutChangingLegacyDefault) {
    initialize(); const auto old_manifest=read("manifest");
    {
        FileJournal j(path.string()); EXPECT_EQ(j.registry_revision(),1U); Recorder w(j);
        ASSERT_TRUE(w.record(session()).durable); const auto before=read("commit");
        const auto receipt=w.record(fault(2,Code::Gateway)); EXPECT_EQ(receipt.result,Result::Accepted); EXPECT_FALSE(receipt.durable); EXPECT_FALSE(w.ledger().complete());
        EXPECT_EQ(read("commit"),before); EXPECT_EQ(read("manifest"),old_manifest); EXPECT_FALSE(j.writable());
    }
    FileJournal j(path.string()); EXPECT_EQ(j.registry_revision(),1U); EXPECT_EQ(j.committed().size(),1U); EXPECT_FALSE(j.writable());
}
TEST_F(DiagnosticsJournal, RegistryTwoReplaysNewCodesAndPreservesUnknownCurrentState) {
    FileJournal::initialize(path.string(),1234,{},2);
    {
        FileJournal j(path.string()); EXPECT_EQ(j.registry_revision(),2U); Recorder w(j); ASSERT_TRUE(w.record(session()).durable);
        for(const auto code:{Code::Gateway,Code::BmsLocal,Code::PowerLocal}) {
            const auto seq=static_cast<std::uint64_t>(w.ledger().events().size()+1); ASSERT_TRUE(w.record(fault(seq,code)).durable);
        }
    }
    FileJournal j(path.string()); Recorder w(j); EXPECT_TRUE(j.writable()); ASSERT_EQ(w.ledger().records().size(),3U);
    for(const auto& r:w.ledger().records()) { EXPECT_EQ(r.condition,Condition::Unknown); EXPECT_EQ(r.count,1U); }
}
TEST_F(DiagnosticsJournal, UnsupportedRegistryDoesNotCreateAStore) {
    for(const auto revision:{0U,5U}) { EXPECT_THROW(FileJournal::initialize(path.string(),1234,{},revision),std::invalid_argument); EXPECT_FALSE(std::filesystem::exists(path)); }
}
TEST_F(DiagnosticsJournal, ExplicitRegistryThreeRetainsPrereleaseFaultAcrossWriterRestart) {
    FileJournal::initialize(path.string(),1234,{},3); auto a=session(); a.kind=Kind::Attempt; a.session_enable={}; a.source={true,a.id.producer,1,1,stamp(),{}};
    auto f=fault(2,Code::Startup); f.session_enable={};
    { FileJournal j(path.string()); Recorder w(j); ASSERT_TRUE(w.record(a).durable); ASSERT_TRUE(w.record(f).durable); EXPECT_EQ(w.ledger().find(f.key)->condition,Condition::Failed); }
    FileJournal j(path.string()); Recorder w(j); EXPECT_EQ(j.registry_revision(),3U); ASSERT_EQ(w.ledger().records().size(),1U);
    EXPECT_EQ(w.ledger().find(f.key)->condition,Condition::Unknown); EXPECT_EQ(w.clear(clear(*w.ledger().find(f.key))).result,Result::NotReady);
}
TEST_F(DiagnosticsJournal, RegistryTwoRefusesAttemptEvenWithoutANewCode) {
    FileJournal::initialize(path.string(),1234,{},2); auto a=session(); a.kind=Kind::Attempt; a.session_enable={}; a.source={true,a.id.producer,1,1,stamp(),{}};
    FileJournal j(path.string()); Recorder w(j); const auto r=w.record(a); EXPECT_FALSE(r.durable); EXPECT_FALSE(j.writable()); EXPECT_TRUE(j.committed().empty());
}
} // namespace
