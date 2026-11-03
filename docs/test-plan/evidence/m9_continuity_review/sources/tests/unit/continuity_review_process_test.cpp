#include "continuity_review_fixture.hpp"
#include <sys/wait.h>
#include <poll.h>
#include <signal.h>
#include <unistd.h>

namespace {
using namespace continuity_fixture;
TEST_F(ContinuityReviewTest, SigkillAtProofReviewPassedAndClearCutsPreservesUnknownHistoryAndCommittedDisposition) {
    baseline();fresh();const auto prepared=plan();const auto original=encode(incident);const auto base=local->committed().size();close_files();
    const auto* configured=std::getenv("STRATADRIVE_CONTINUITY_REVIEW_TEST_DIR");
    const auto export_root=configured?std::filesystem::path(configured):root/"exports";std::filesystem::create_directories(export_root);
    std::filesystem::copy_file(root/"release.csv",export_root/"release.csv",std::filesystem::copy_options::overwrite_existing);
    std::filesystem::copy_file(root/"credits.csv",export_root/"credits.csv",std::filesystem::copy_options::overwrite_existing);
    for(unsigned cut=1;cut<=4;++cut){const auto folder=export_root/("cut-"+std::to_string(cut));std::filesystem::create_directories(folder);
        for(const auto name:{"case","source-0","source-1","replica-0","replica-1"})std::filesystem::copy(root/name,folder/name,std::filesystem::copy_options::recursive);
        int channel[2]{};ASSERT_EQ(pipe(channel),0);const auto pid=fork();ASSERT_GE(pid,0);
        if(pid==0){close(channel[0]);try{FileJournal j((folder/"case").string());Recorder w(j);
            // A new child revalidates the frozen proof/review after opening; no
            // inherited C++ projection or uncommitted transaction grants a clear.
            if(!w.record(prepared.proof).durable)_exit(81);
            if(cut>=2 && !w.review(prepared.review).durable)_exit(82);
            if(cut>=3 && !w.record(prepared.passed).durable)_exit(83);
            if(cut>=4){Clear c;c.id={run,100,1};c.session=prepared.review.session;c.evidence=prepared.review.evidence;c.targets={{incident.key,w.ledger().find(incident.key)->revision}};if(!w.clear(c).durable)_exit(84);}
            const char ready='C';if(write(channel[1],&ready,1)!=1)_exit(85);for(;;)pause();
        }catch(...){_exit(86);}}
        close(channel[1]);pollfd wait{channel[0],POLLIN,0};const auto ready=poll(&wait,1,5000);char mark=0;const auto received=ready>0?read(channel[0],&mark,1):0;close(channel[0]);
        kill(pid,SIGKILL);int status=0;ASSERT_EQ(waitpid(pid,&status,0),pid);ASSERT_GT(ready,0);ASSERT_EQ(received,1);ASSERT_EQ(mark,'C');ASSERT_TRUE(WIFSIGNALED(status));ASSERT_EQ(WTERMSIG(status),SIGKILL);
        FileJournal j((folder/"case").string());Recorder w(j);ASSERT_EQ(j.committed().size(),base+cut);const auto* record=w.ledger().find(incident.key);ASSERT_NE(record,nullptr);
        EXPECT_EQ(record->count,1U);EXPECT_EQ(record->generation,1U);EXPECT_EQ(record->condition,Condition::Unknown);EXPECT_EQ(record->cleared,cut==4);
        EXPECT_EQ(encode(w.ledger().events()[2]),original);if(cut>=2){EXPECT_EQ(w.review(prepared.review).result,Result::Duplicate);}
        if(cut<4){auto note=prepared.proof;note.id.sequence=20;note.proof=Proof::None;auto copy=w.ledger();ASSERT_EQ(copy.record(note),Result::Accepted);EXPECT_EQ(copy.find(incident.key)->condition,Condition::Unknown);}
        std::ofstream(folder/"summary.json")<<"{\"stage\":"<<cut<<",\"pid\":"<<pid<<",\"signal\":9,\"watermark\":"<<j.committed().size()<<",\"count\":1,\"generation\":1,\"condition\":0,\"cleared\":"<<(record->cleared?"true":"false")<<"}\n";
    }
}
} // namespace
