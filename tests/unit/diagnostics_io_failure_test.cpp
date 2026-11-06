// Linux test-only syscall interception. Production journal has no test hooks.
#include "diagnostics_fixture.hpp"
#include "diagnostics_journal.hpp"
#include <gtest/gtest.h>
#include <sys/wait.h>
#include <unistd.h>
#include <array>
#include <cerrno>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>

namespace injection {
enum class Mode { Error, CrashAfter, Short, Interrupted };
int point=-1,cursor=0,error=EIO;
Mode mode=Mode::Error;
bool hit() { if(point<0)return false; if(cursor++!=point)return false;point=-1;return true; }
void arm(int p,Mode m,int e=EIO) { point=p;cursor=0;mode=m;error=e; }
}
extern "C" {
ssize_t __real_write(int,const void*,size_t);
int __real_fsync(int);
int __real_renameat(int,const char*,int,const char*);
ssize_t __wrap_write(int fd,const void* data,size_t n) {
    if(!injection::hit())return __real_write(fd,data,n);
    if(injection::mode==injection::Mode::CrashAfter){__real_write(fd,data,n);_exit(77);}
    if(injection::mode==injection::Mode::Short)return __real_write(fd,data,n/2);
    errno=injection::mode==injection::Mode::Interrupted?EINTR:injection::error;return -1;
}
int __wrap_fsync(int fd) {
    if(!injection::hit())return __real_fsync(fd);
    if(injection::mode==injection::Mode::CrashAfter){__real_fsync(fd);_exit(77);}
    errno=injection::mode==injection::Mode::Interrupted?EINTR:injection::error;return -1;
}
int __wrap_renameat(int from,const char* a,int to,const char* b) {
    if(!injection::hit())return __real_renameat(from,a,to,b);
    if(injection::mode==injection::Mode::CrashAfter){__real_renameat(from,a,to,b);_exit(77);}
    errno=injection::error;return -1;
}
}
namespace {
using namespace diagnostics_fixture;
class DiagnosticsIOFailure : public ::testing::Test {
protected:
    std::filesystem::path root,path;
    std::string prefix,checkpoint;
    Clear request;
    static std::string read(const std::filesystem::path& p) {
        std::ifstream f(p,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};
    }
    void SetUp() override {
        std::array<char,48> name{};const std::string pattern="/tmp/stratadrive-io-failure-XXXXXX";
        std::copy(pattern.begin(),pattern.end(),name.begin());const auto* p=mkdtemp(name.data());
        ASSERT_NE(p,nullptr);root=p;path=root/"store";FileJournal::initialize(path.string(),1234);
        FileJournal j(path.string());Recorder r(j);const auto f=fault();
        ASSERT_TRUE(r.record(session()).durable);ASSERT_TRUE(r.record(f).durable);
        ASSERT_TRUE(r.record(proof(f)).durable);ASSERT_TRUE(r.record(passed(proof(f))).durable);
        request=clear(*r.ledger().find(f.key));prefix=read(path/"journal");checkpoint=read(path/"commit");
    }
    void TearDown() override { injection::point=-1;std::filesystem::remove_all(root); }
    void reopen(bool published,bool incomplete) {
        EXPECT_EQ(read(path/"journal").substr(0,prefix.size()),prefix);
        FileJournal j(path.string());Recorder r(j);
        EXPECT_EQ(j.committed().size(),published?5U:4U);
        ASSERT_NE(r.ledger().find(fault().key),nullptr);
        EXPECT_EQ(r.ledger().find(fault().key)->cleared,published);
        EXPECT_EQ(r.ledger().find(fault().key)->condition,Condition::Unknown);
        EXPECT_EQ(j.writable(),!incomplete);EXPECT_EQ(r.ledger().complete(),!incomplete);
        if(!published){EXPECT_EQ(read(path/"commit"),checkpoint);}
        if(incomplete) {
            auto next=request;++next.id.sequence;
            EXPECT_FALSE(r.clear(next).durable); // no NEW clear on an incomplete store
        }
        if(published) {
            const auto duplicate=r.clear(request);
            EXPECT_EQ(duplicate.result,Result::Duplicate);EXPECT_TRUE(duplicate.durable);
        }
    }
};
class IOStage : public DiagnosticsIOFailure,public ::testing::WithParamInterface<int> {};
TEST_P(IOStage, FailedWriteSyncOrRenameNeverAcknowledgesClear) {
    {
        FileJournal j(path.string());
        // Exercise storage with a previously valid clear transaction. Recorder
        // admission from Unknown is independently checked by reopen().
        injection::arm(GetParam(),injection::Mode::Error,GetParam()==0||GetParam()==3?ENOSPC:EIO);
        EXPECT_FALSE(j.append(request));EXPECT_EQ(injection::point,-1);
        EXPECT_FALSE(j.writable());EXPECT_EQ(j.committed().size(),4U);
    }
    reopen(GetParam()==6,true);
}
TEST_P(IOStage, AbruptWriterExitPreservesPrefixAndUnresolvedIntent) {
    const auto pid=fork();ASSERT_GE(pid,0);
    if(pid==0) {
        FileJournal j(path.string());injection::arm(GetParam(),injection::Mode::CrashAfter);
        j.append(request);_exit(78);
    }
    int status=0;ASSERT_EQ(waitpid(pid,&status,0),pid);ASSERT_TRUE(WIFEXITED(status));ASSERT_EQ(WEXITSTATUS(status),77);
    reopen(GetParam()>=5,GetParam()<5);
}
INSTANTIATE_TEST_SUITE_P(AllCommitBoundaries,IOStage,::testing::Range(0,7));
class RetryStage : public DiagnosticsIOFailure,public ::testing::WithParamInterface<int> {};
TEST_P(RetryStage, InterruptedWriteAndSyncAreRetriedWithoutDuplicateEntries) {
    {FileJournal j(path.string());injection::arm(GetParam(),injection::Mode::Interrupted);EXPECT_TRUE(j.append(request));EXPECT_EQ(injection::point,-1);}
    reopen(true,false);
}
INSTANTIATE_TEST_SUITE_P(RetryableBoundaries,RetryStage,::testing::Values(0,1,2,3,4,6));
class ShortStage : public DiagnosticsIOFailure,public ::testing::WithParamInterface<int> {};
TEST_P(ShortStage, ShortWritesCompleteTheSameFrameAndCheckpoint) {
    {FileJournal j(path.string());injection::arm(GetParam(),injection::Mode::Short);EXPECT_TRUE(j.append(request));EXPECT_EQ(injection::point,-1);}
    reopen(true,false);
}
INSTANTIATE_TEST_SUITE_P(DataAndIntent,ShortStage,::testing::Values(0,3));
TEST_F(DiagnosticsIOFailure, PreexistingIntentWithNoTailIsReadOnlyAndPreserved) {
    std::ofstream(path/"pending",std::ios::binary)<<"unresolved intent";
    const auto pending=read(path/"pending");reopen(false,true);
    EXPECT_EQ(read(path/"pending"),pending);EXPECT_EQ(read(path/"journal"),prefix);
}
}
