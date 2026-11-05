#include "bootstrap_journal.hpp"
#include "diagnostics_journal.hpp"
#include "epoch_store.hpp"
#include <gtest/gtest.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
#include <array>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <system_error>

namespace {
namespace fs=std::filesystem;
namespace d=stratadrive::diagnostics;
using stratadrive::session::EpochStore;
class BootstrapJournalTest:public ::testing::Test {
protected:
    fs::path root,spool;
    void SetUp() override {
        std::string pattern="/var/tmp/stratadrive-boot-test-XXXXXX";
        auto* path=mkdtemp(pattern.data());ASSERT_NE(path,nullptr);root=path;spool=root/"incidents";
        d::BootstrapJournal::initialize(spool.string());
    }
    void TearDown() override {
        if(const auto* evidence=std::getenv("STRATADRIVE_BOOT_EVIDENCE")) {
            fs::create_directories(evidence);
            fs::copy(root,fs::path(evidence)/::testing::UnitTest::GetInstance()->current_test_info()->name(),fs::copy_options::recursive|fs::copy_options::copy_symlinks);
        }
        fs::remove_all(root);
    }
    std::vector<fs::path> attempts() {
        std::vector<fs::path> result;for(const auto& p:fs::directory_iterator(spool))if(p.is_directory())result.push_back(p.path());return result;
    }
    static std::vector<unsigned char> read(const fs::path& path) {
        std::ifstream input(path,std::ios::binary);return {std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
    }
    template<class F> auto run(d::BootOperation operation,F&& fn) {
        return d::record_bootstrap(spool.string(),d::BootRole::Central,operation,std::forward<F>(fn));
    }
};
TEST_F(BootstrapJournalTest, SuccessfulOperationsHaveUniqueDurableIdentityAndNoApplicationEpoch) {
    run(d::BootOperation::EpochInitialize,[&]{EpochStore::initialize((root/"epochs").string());});
    EXPECT_EQ(run(d::BootOperation::EpochIssue,[&]{return EpochStore((root/"epochs").string()).issue();}),1U);
    const auto entries=attempts();ASSERT_EQ(entries.size(),2U);EXPECT_NE(entries[0],entries[1]);
    for(const auto& entry:entries) {const auto begin=read(entry/"begin"),end=read(entry/"outcome");ASSERT_EQ(begin.size(),320U);ASSERT_EQ(end.size(),320U);EXPECT_EQ(begin[8],1);EXPECT_EQ(end[8],2);EXPECT_EQ(begin[10],1);EXPECT_TRUE(std::equal(begin.begin()+32,begin.begin()+64,end.begin()+32));EXPECT_EQ(end[64],0);EXPECT_FALSE(fs::exists(entry/"outcome.pending"));}
}
TEST_F(BootstrapJournalTest, RealEpochFailureIsRetainedAfterExplicitRepairAndRetry) {
    EXPECT_THROW(run(d::BootOperation::EpochIssue,[&]{return EpochStore((root/"epochs").string()).issue();}),std::system_error);
    const auto original=attempts().at(0);const auto failure=read(original/"outcome");ASSERT_EQ(failure.size(),320U);EXPECT_EQ(failure[8],3);
    EpochStore::initialize((root/"epochs").string());
    EXPECT_EQ(run(d::BootOperation::EpochIssue,[&]{return EpochStore((root/"epochs").string()).issue();}),1U);
    EXPECT_EQ(attempts().size(),2U);EXPECT_EQ(read(original/"outcome"),failure);
}
TEST_F(BootstrapJournalTest, CorruptEpochIsNeverResetOrGranted) {
    EpochStore::initialize((root/"epochs").string());std::ofstream(root/"epochs/epoch")<<"corrupt";
    const auto before=read(root/"epochs/epoch");
    EXPECT_THROW(run(d::BootOperation::EpochIssue,[&]{return EpochStore((root/"epochs").string()).issue();}),std::runtime_error);
    EXPECT_EQ(read(root/"epochs/epoch"),before);EXPECT_EQ(read(attempts().at(0)/"outcome")[8],3);
}
TEST_F(BootstrapJournalTest, JournalInitializationFailureUsesIndependentSpool) {
    std::ofstream(root/"blocked")<<"not a directory";
    EXPECT_THROW(run(d::BootOperation::JournalInitialize,[&]{d::FileJournal::initialize((root/"blocked/store").string(),1);}),std::system_error);
    EXPECT_EQ(read(attempts().at(0)/"outcome")[8],3);
}
TEST_F(BootstrapJournalTest, JournalOpenFailureCannotRunDependentWork) {
    bool authority=false;
    EXPECT_THROW(run(d::BootOperation::JournalOpen,[&]{d::FileJournal store((root/"missing").string());authority=true;}),std::system_error);
    EXPECT_FALSE(authority);EXPECT_EQ(read(attempts().at(0)/"outcome")[8],3);
}
TEST_F(BootstrapJournalTest, MissingOrCorruptSpoolStopsBeforeOperation) {
    bool ran=false;
    EXPECT_THROW(d::record_bootstrap((root/"missing").string(),d::BootRole::Central,d::BootOperation::EpochIssue,[&]{ran=true;}),std::system_error);
    std::ofstream(spool/"format")<<"bad";
    EXPECT_THROW(run(d::BootOperation::EpochIssue,[&]{ran=true;}),std::runtime_error);
    EXPECT_FALSE(ran);EXPECT_TRUE(attempts().empty());
}
TEST_F(BootstrapJournalTest, ExplicitInitializationAndPrivatePathsNeverOverwriteExistingData) {
    const auto original=read(spool/"format");EXPECT_THROW(d::BootstrapJournal::initialize(spool.string()),std::system_error);EXPECT_EQ(read(spool/"format"),original);
    fs::create_directory_symlink(spool,root/"alias");
    EXPECT_THROW(d::BootstrapJournal((root/"alias").string(),d::BootRole::Central,d::BootOperation::EpochIssue),std::system_error);
    fs::permissions(spool,fs::perms::others_read,fs::perm_options::add);
    EXPECT_THROW(d::BootstrapJournal(spool.string(),d::BootRole::Central,d::BootOperation::EpochIssue),std::runtime_error);
    fs::permissions(spool,fs::perms::others_read,fs::perm_options::remove);
}
TEST_F(BootstrapJournalTest, OutcomeIsImmutableAndErrorTextIsBounded) {
    d::BootstrapJournal attempt(spool.string(),d::BootRole::Front,d::BootOperation::JournalOpen);
    attempt.failed(std::string(400,'x'));const auto path=attempts().at(0)/"outcome";const auto original=read(path);
    EXPECT_EQ(original[64],240);EXPECT_EQ(original[65],0);EXPECT_EQ(original[66],1);
    EXPECT_THROW(attempt.succeeded(),std::logic_error);
    EXPECT_THROW(attempt.failed("again"),std::logic_error);
    EXPECT_EQ(read(path),original);
}
TEST_F(BootstrapJournalTest, FailedOutcomeCommitCannotReturnAnEpochOrOverwriteEvidence) {
    bool returned=false;fs::path attempt;
    EpochStore::initialize((root/"epochs").string());
    EXPECT_THROW({const auto epoch=run(d::BootOperation::EpochIssue,[&]{attempt=attempts().at(0);std::ofstream(attempt/"outcome")<<"existing evidence";return EpochStore((root/"epochs").string()).issue();});returned=epoch==1;},std::system_error);
    EXPECT_FALSE(returned);EXPECT_EQ(read(attempt/"outcome").size(),17U);EXPECT_TRUE(fs::exists(attempt/"outcome.pending"));
    EXPECT_EQ(EpochStore((root/"epochs").string()).issue(),2U); // committed but unreturned Epoch1 is never reused
}
TEST_F(BootstrapJournalTest, KilledProcessLeavesUnfinishedAttemptAndRetryKeepsIt) {
    int pipefd[2];ASSERT_EQ(pipe(pipefd),0);const auto pid=fork();ASSERT_GE(pid,0);
    if(pid==0) {
        close(pipefd[0]);d::BootstrapJournal attempt(spool.string(),d::BootRole::Central,d::BootOperation::EpochIssue);
        const char ready='R';if(write(pipefd[1],&ready,1)!=1)_exit(2);for(;;)pause();
    }
    close(pipefd[1]);char ready=0;const auto count=::read(pipefd[0],&ready,1);close(pipefd[0]);
    const auto killed=kill(pid,SIGKILL);int status=0;ASSERT_EQ(waitpid(pid,&status,0),pid);
    ASSERT_EQ(count,1);ASSERT_EQ(ready,'R');ASSERT_EQ(killed,0);ASSERT_TRUE(WIFSIGNALED(status));ASSERT_EQ(WTERMSIG(status),SIGKILL);
    const auto old=attempts().at(0);const auto begin=read(old/"begin");EXPECT_FALSE(fs::exists(old/"outcome"));
    run(d::BootOperation::EpochInitialize,[&]{EpochStore::initialize((root/"epochs").string());});
    EXPECT_EQ(read(old/"begin"),begin);EXPECT_FALSE(fs::exists(old/"outcome"));EXPECT_EQ(attempts().size(),2U);
}
TEST_F(BootstrapJournalTest, NonStandardExceptionIsRecordedBeforePropagation) {
    EXPECT_THROW(run(d::BootOperation::JournalOpen,[]{throw 7;}),int);
    EXPECT_EQ(read(attempts().at(0)/"outcome")[8],3);
}
} // namespace
