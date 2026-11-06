#include "epoch_recorder.hpp"
#include "diagnostics_fixture.hpp"
#include <gtest/gtest.h>
#include <array>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <sys/wait.h>
#include <unistd.h>
#include <cerrno>

namespace epoch_io {
int mode=0,target=0,calls=0;
bool renames=false;
}
extern "C" int __real_fsync(int);
extern "C" int __real_renameat(int,const char*,int,const char*);
extern "C" int __wrap_fsync(int fd) {
    using namespace epoch_io;
    const bool selected=mode && !renames && ++calls==target;
    if(selected && mode==1){mode=0;errno=EIO;return -1;}
    const auto result=__real_fsync(fd);
    if(selected && mode==2)_exit(77);
    return result;
}
extern "C" int __wrap_renameat(int from,const char* source,int to,const char* destination) {
    using namespace epoch_io;
    const bool selected=mode && renames && ++calls==target;
    if(selected && mode==1){mode=0;errno=EIO;return -1;}
    const auto result=__real_renameat(from,source,to,destination);
    if(selected && mode==2)_exit(77);
    return result;
}

namespace {
using namespace diagnostics_fixture;
class EpochRecorderTest:public ::testing::Test {
protected:
    std::filesystem::path root,path;
    void SetUp() override {
        std::array<char,64> pattern{};const std::string name="/tmp/stratadrive-epoch-XXXXXX";
        std::copy(name.begin(),name.end(),pattern.begin());auto* p=mkdtemp(pattern.data());ASSERT_NE(p,nullptr);root=p;path=root/"family";
    }
    void TearDown() override {epoch_io::mode=0;std::filesystem::remove_all(root);}
    void init(std::uint32_t segments=128){EpochRecorder::initialize(path.string(),100,{{16,4,8,8},4,segments});}
    static std::vector<char> bytes(const std::filesystem::path& file) {
        std::ifstream input(file,std::ios::binary);return {std::istreambuf_iterator<char>(input),{}};
    }
    void prefix(EpochRecorder& r) {
        ASSERT_TRUE(r.record(session()).durable);ASSERT_TRUE(r.record(fault()).durable);
        ASSERT_TRUE(r.record(proof(fault())).durable);ASSERT_TRUE(r.record(passed(proof(fault()))).durable);
    }
};
TEST_F(EpochRecorderTest, RolloverPreservesCountsAndRawBytesButRequiresFreshRecovery) {
    init();std::vector<char> predecessor;
    {
        EpochRecorder r(path.string());prefix(r);const auto before=*r.ledger().find(fault().key);
        predecessor=bytes(path/"00000001/journal");ASSERT_TRUE(r.record(session(5,2)).durable);EXPECT_EQ(r.segment(),2U);
        const auto* after=r.ledger().find(fault().key);ASSERT_NE(after,nullptr);EXPECT_EQ(after->count,before.count);
        EXPECT_EQ(after->generation,before.generation);EXPECT_TRUE(after->first_event==before.first_event);EXPECT_TRUE(after->last_event==before.last_event);
        EXPECT_EQ(after->condition,Condition::Unknown);EXPECT_FALSE(r.clear(clear(*after,1,2)).durable);
        auto p=proof(fault(),6,Proof::Input,2);ASSERT_TRUE(r.record(p).durable);ASSERT_TRUE(r.record(passed(p,7)).durable);
        ASSERT_TRUE(r.clear(clear(*r.ledger().find(fault().key),1,2)).durable);EXPECT_TRUE(r.ledger().find(fault().key)->cleared);
        EXPECT_EQ(bytes(path/"00000001/journal"),predecessor);EXPECT_EQ(r.watermark(),8U);
    }
    EpochRecorder reopened(path.string());EXPECT_EQ(reopened.watermark(),8U);EXPECT_TRUE(reopened.ledger().find(fault().key)->cleared);
    EXPECT_EQ(bytes(path/"00000001/journal"),predecessor);
}
TEST_F(EpochRecorderTest, HistoricalEventAndClearReceiptsRemainDurableAcrossGenerations) {
    init();Clear cleared;
    {
        EpochRecorder r(path.string());prefix(r);cleared=clear(*r.ledger().find(fault().key));ASSERT_TRUE(r.clear(cleared).durable);
        ASSERT_TRUE(r.record(session(5,2)).durable);EXPECT_EQ(r.segment(),2U);
        EXPECT_EQ(r.record(fault()).result,Result::Duplicate);EXPECT_TRUE(r.record(fault()).durable);
        EXPECT_EQ(r.clear(cleared).result,Result::Duplicate);EXPECT_TRUE(r.clear(cleared).durable);EXPECT_EQ(r.watermark(),6U);
    }
    EpochRecorder reopened(path.string());EXPECT_TRUE(reopened.clear(cleared).durable);EXPECT_EQ(reopened.watermark(),6U);
    auto mutation=fault();mutation.native_reason=9;EXPECT_EQ(reopened.record(mutation).result,Result::Conflict);EXPECT_FALSE(reopened.ledger().complete());
}
TEST_F(EpochRecorderTest, ThousandsOfEventsAcrossSessionsReclaimBoundedActiveHistory) {
    init(200);std::uint64_t sequence=1;
    {
        EpochRecorder r(path.string());
        for(std::uint32_t epoch=1;epoch<=100;++epoch) {
            ASSERT_TRUE(r.record(session(sequence++,epoch)).durable);
            for(int j=0;j<14;++j){auto e=session(sequence++,epoch);e.kind=Kind::Observation;ASSERT_TRUE(r.record(e).durable);}
            EXPECT_LE(r.ledger().events().size(),16U);EXPECT_TRUE(r.ledger().complete());
        }
        EXPECT_EQ(r.segment(),100U);EXPECT_EQ(r.watermark(),1500U);
    }
    EpochRecorder reopened(path.string());EXPECT_EQ(reopened.watermark(),1500U);EXPECT_TRUE(reopened.ledger().complete());
    EXPECT_TRUE(reopened.record(session()).durable);EXPECT_EQ(reopened.watermark(),1500U);
}
TEST_F(EpochRecorderTest, NewFaultAfterClearKeepsGenerationAndFirstOccurrenceSemantics) {
    init();EpochRecorder r(path.string());prefix(r);ASSERT_TRUE(r.clear(clear(*r.ledger().find(fault().key))).durable);
    ASSERT_TRUE(r.record(session(5,2)).durable);ASSERT_TRUE(r.record(fault(6,Code::SpeedInput,2)).durable);
    const auto* record=r.ledger().find(fault().key);ASSERT_NE(record,nullptr);EXPECT_EQ(record->generation,2U);EXPECT_EQ(record->count,1U);EXPECT_EQ(record->first.epoch,2U);
}
TEST_F(EpochRecorderTest, RecurrentFaultCountsSurviveMoreEpochsThanTheOccurrenceWindow) {
    init();std::uint64_t sequence=1;
    {
        EpochRecorder r(path.string());
        for(std::uint32_t epoch=1;epoch<=40;++epoch) {
            ASSERT_TRUE(r.record(session(sequence++,epoch)).durable);
            const auto f=fault(sequence++,Code::SpeedInput,epoch);ASSERT_TRUE(r.record(f).durable);
            const auto p=proof(f,sequence++,Proof::Input,epoch);ASSERT_TRUE(r.record(p).durable);
            ASSERT_TRUE(r.record(passed(p,sequence++)).durable);
            const auto* record=r.ledger().find(f.key);ASSERT_NE(record,nullptr);
            EXPECT_EQ(record->count,epoch);EXPECT_EQ(record->generation,1U);EXPECT_EQ(record->condition,Condition::Passed);
            EXPECT_LE(r.ledger().events().size(),5U);
        }
        EXPECT_EQ(r.segment(),40U);EXPECT_EQ(r.watermark(),160U);
    }
    EpochRecorder reopened(path.string());const auto* record=reopened.ledger().find(fault().key);ASSERT_NE(record,nullptr);
    EXPECT_EQ(record->count,40U);EXPECT_EQ(record->condition,Condition::Unknown);
    EXPECT_TRUE(reopened.record(fault()).durable);EXPECT_EQ(record->count,40U);
}
TEST_F(EpochRecorderTest, UnrecordedHistoricalEventCannotMasqueradeAsCurrentRecovery) {
    init();EpochRecorder r(path.string());prefix(r);ASSERT_TRUE(r.record(session(5,2)).durable);
    auto historical=proof(fault(),50);EXPECT_EQ(r.record(historical).result,Result::NotReady);EXPECT_FALSE(r.ledger().complete());
}
TEST_F(EpochRecorderTest, SingleLongEpochStillFailsExplicitlyAtItsFiniteBound) {
    init();EpochRecorder r(path.string());ASSERT_TRUE(r.record(session()).durable);
    for(std::uint64_t i=2;i<=16;++i){auto e=session(i);e.kind=Kind::Observation;ASSERT_TRUE(r.record(e).durable);}
    const auto original=bytes(path/"00000001/journal");auto e=session(17);e.kind=Kind::Observation;
    EXPECT_EQ(r.record(e).result,Result::Capacity);EXPECT_EQ(bytes(path/"00000001/journal"),original);EXPECT_EQ(r.segment(),1U);
}
TEST_F(EpochRecorderTest, ArchiveQuotaNeverSilentlyDeletesEvidence) {
    init(1);EpochRecorder r(path.string());prefix(r);const auto original=bytes(path/"00000001/journal");
    EXPECT_EQ(r.record(session(5,2)).result,Result::Capacity);EXPECT_FALSE(r.ledger().complete());
    EXPECT_EQ(bytes(path/"00000001/journal"),original);EXPECT_FALSE(std::filesystem::exists(path/"00000002"));
}
TEST_F(EpochRecorderTest, BusyStoreAndRootSymlinksAreRejected) {
    init();EpochRecorder r(path.string());EXPECT_THROW(EpochRecorder second(path.string()),std::system_error);
    std::filesystem::create_directory_symlink(path,root/"alias");EXPECT_THROW(EpochRecorder((root/"alias").string()),std::system_error);
}
TEST_F(EpochRecorderTest, InterruptedTransferPreservesPredecessorAndBlocksFurtherWrites) {
    init();{
        EpochRecorder r(path.string());prefix(r);
    }
    const auto original=bytes(path/"00000001/journal");
    // A durable intent with no published successor is deliberately ambiguous.
    std::ofstream(path/"pending")<<"interrupted transfer";
    {EpochRecorder r(path.string());EXPECT_FALSE(r.ledger().complete());EXPECT_FALSE(r.record(session(5,2)).durable);EXPECT_TRUE(r.record(fault()).durable);}
    EXPECT_EQ(bytes(path/"00000001/journal"),original);EXPECT_EQ(bytes(path/"pending").size(),20U);
}
TEST_F(EpochRecorderTest, ConflictingSuccessorIsPreservedAndNeverOverwritten) {
    init();EpochRecorder r(path.string());prefix(r);std::filesystem::create_directory(path/"00000002");
    std::ofstream(path/"00000002/foreign")<<"keep";
    EXPECT_EQ(r.record(session(5,2)).result,Result::StorageFailure);EXPECT_TRUE(std::filesystem::exists(path/"pending"));
    EXPECT_EQ(bytes(path/"00000002/foreign"),(std::vector<char>{'k','e','e','p'}));EXPECT_FALSE(r.ledger().complete());
}
TEST_F(EpochRecorderTest, MissingOrModifiedPredecessorsCannotBeIgnoredOnRestart) {
    init();{EpochRecorder r(path.string());prefix(r);ASSERT_TRUE(r.record(session(5,2)).durable);}
    auto raw=bytes(path/"00000001/journal");raw[25]^=1;std::ofstream out(path/"00000001/journal",std::ios::binary);out.write(raw.data(),raw.size());out.close();
    EXPECT_THROW(EpochRecorder(path.string()),std::runtime_error);
}
TEST_F(EpochRecorderTest, ProducerQueueLossCannotBeHealedByRotation) {
    init();EpochRecorder r(path.string());prefix(r);EventQueue queue(10,20);
    auto invalid=session(5,2);invalid.id.producer=99;EXPECT_FALSE(queue.publish(invalid));EXPECT_EQ(r.drain(queue),0U);
    EXPECT_FALSE(r.record(session(5,2)).durable);EXPECT_FALSE(r.ledger().complete());
}
TEST(EpochCheckpoint, RoundTripRejectsMissingFaultAndFreshAuthority) {
    Ledger ledger;ASSERT_EQ(ledger.record(session()),Result::Accepted);ASSERT_EQ(ledger.record(fault()),Result::Accepted);
    const auto cp=ledger.checkpoint();EXPECT_EQ(encode_checkpoint(decode_checkpoint(encode_checkpoint(cp))),encode_checkpoint(cp));
    auto bad=cp;bad.faults.clear();EXPECT_THROW((Ledger(bad,Limits{})),std::invalid_argument);
    bad=cp;bad.records[0].condition=Condition::Passed;EXPECT_THROW((Ledger(bad,Limits{})),std::invalid_argument);
    auto raw=encode_checkpoint(cp);raw.push_back(0);EXPECT_THROW(decode_checkpoint(raw),std::runtime_error);
}
TEST(EpochCheckpoint, HistoricalOnlyFaultRetainsCountWithoutInventingCurrentIdentity) {
    Ledger ledger;ASSERT_EQ(ledger.record(session(1,2)),Result::Accepted);
    ASSERT_EQ(ledger.record(fault(2,Code::SpeedInput,1)),Result::Accepted);
    Ledger successor(ledger.checkpoint(),Limits{});ASSERT_EQ(successor.record(session(3,3)),Result::Accepted);
    const auto* record=successor.find(fault().key);ASSERT_NE(record,nullptr);EXPECT_EQ(record->count,1U);
    EXPECT_TRUE(record->state_event==EventId{});EXPECT_EQ(record->condition,Condition::Unknown);
}
TEST_F(EpochRecorderTest, EveryRolloverSyncAndRenameFailureOrProcessExitPreservesCommittedHistory) {
    for(bool rename:{false,true}) {
        path=root/(rename?"rename-count":"sync-count");init();int count=0;
        {
            EpochRecorder r(path.string());prefix(r);
            epoch_io::renames=rename;epoch_io::target=0;epoch_io::calls=0;epoch_io::mode=3;
            const auto receipt=r.record(session(5,2));epoch_io::mode=0;count=epoch_io::calls;ASSERT_TRUE(receipt.durable);
        }
        EXPECT_GE(count,rename?3:10);
        for(int mode:{1,2})for(int boundary=1;boundary<=count;++boundary) {
            SCOPED_TRACE(::testing::Message()<<"rename="<<rename<<" mode="<<mode<<" boundary="<<boundary);
            path=root/((rename?"rename-":"sync-")+std::to_string(mode)+"-"+std::to_string(boundary));init();
            {EpochRecorder r(path.string());prefix(r);}
            const auto original=bytes(path/"00000001/journal");
            const auto pid=fork();ASSERT_GE(pid,0);
            if(pid==0) {
                EpochRecorder r(path.string());epoch_io::renames=rename;epoch_io::target=boundary;epoch_io::calls=0;epoch_io::mode=mode;
                const auto result=r.record(session(5,2));epoch_io::mode=0;
                _exit(mode==1 && !result.durable?0:99);
            }
            int status=0;ASSERT_EQ(waitpid(pid,&status,0),pid);ASSERT_TRUE(WIFEXITED(status));EXPECT_EQ(WEXITSTATUS(status),mode==1?0:77);
            EpochRecorder recovered(path.string());EXPECT_EQ(bytes(path/"00000001/journal"),original);
            const auto* record=recovered.ledger().find(fault().key);ASSERT_NE(record,nullptr);EXPECT_EQ(record->count,1U);
            EXPECT_EQ(record->condition,Condition::Unknown);EXPECT_TRUE(recovered.record(fault()).durable);
            EXPECT_FALSE(recovered.clear(clear(*record,9,2)).durable);
        }
        RecordProperty(rename?"rename_boundaries":"sync_boundaries",count);
    }
}
} // namespace
