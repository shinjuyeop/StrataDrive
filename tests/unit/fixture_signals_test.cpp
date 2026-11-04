#include "../integration/someip/fixture_signals.hpp"
#include <gtest/gtest.h>
#include <future>
#include <unistd.h>

namespace {
namespace fs=std::filesystem;
using stratadrive::someip::test::FixtureSignals;
struct FixtureSignalsTest: ::testing::Test {
    fs::path folder;
    void SetUp() override {
        std::string pattern="/tmp/stratadrive-signals-XXXXXX";
        const auto* created=mkdtemp(pattern.data());ASSERT_NE(created,nullptr);folder=created;
    }
    void TearDown() override {fs::remove_all(folder);}
    template<class Predicate> bool until(Predicate p) {
        const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
        while(!p() && std::chrono::steady_clock::now()<deadline)std::this_thread::yield();
        return p();
    }
};
TEST_F(FixtureSignalsTest,BlockedDiskDoesNotBlockOwnerAndRetainsFirstSource) {
    std::promise<void> entered,release;auto released=release.get_future().share();
    auto started=entered.get_future();
    FixtureSignals signals(folder,"central-2",{},[&](const fs::path& p){
        if(p.filename()=="armed"){entered.set_value();released.wait();}
    });
    signals.mark(folder/"armed",123);
    const bool blocked=started.wait_for(std::chrono::seconds(2))==std::future_status::ready;
    EXPECT_TRUE(blocked);
    // A real worker is stuck in its write, while the owner can keep sampling
    // inputs and publish a later prerequisite. No fabricated write completion.
    for(unsigned i=0;i<1000;++i){signals.mark(folder/"armed",999);EXPECT_FALSE(signals.exists(folder/"armed"));}
    signals.mark(folder/"control-established",456);
    EXPECT_FALSE(signals.exists(folder/"control-established"));
    release.set_value();signals.finish();EXPECT_FALSE(signals.failed());
    std::uint64_t source=0;std::ifstream(folder/"armed")>>source;EXPECT_EQ(source,123U);
    std::ifstream(folder/"control-established")>>source;EXPECT_EQ(source,456U);
}
TEST_F(FixtureSignalsTest,ExternalSignalsTrackCreateAndRemovalWithoutOwnerFilesystemReads) {
    std::ofstream(folder/"rejoin-request")<<1;
    FixtureSignals signals(folder,"central-2");EXPECT_TRUE(signals.exists(folder/"rejoin-request"));
    std::ofstream(folder/"service-epoch-request")<<2;
    EXPECT_TRUE(until([&]{return signals.exists(folder/"service-epoch-request");}));
    fs::remove(folder/"rejoin-request");
    EXPECT_TRUE(until([&]{return !signals.exists(folder/"rejoin-request");}));
    EXPECT_THROW(signals.mark(folder/"unknown"),std::invalid_argument);
    signals.finish();EXPECT_FALSE(signals.failed());
}
TEST_F(FixtureSignalsTest,FailedWriteCannotBeReportedAsSuccess) {
    fs::create_directory(folder/"armed");FixtureSignals signals(folder,"central-2");
    signals.mark(folder/"armed",123);signals.finish();EXPECT_TRUE(signals.failed());
    EXPECT_TRUE(fs::is_directory(folder/"armed"));
}
TEST_F(FixtureSignalsTest,SubscribedReadsSkipUnrelatedPathsAndKeepWrites) {
    // An unread marker cannot impose filesystem work (or an ELOOP failure).
    fs::create_symlink("stop-front",folder/"stop-front");
    FixtureSignals signals(folder,"plant",{},{},stratadrive::someip::test::fixture_observations("plant"));
    signals.mark(folder/"plant-ready",456);
    EXPECT_THROW(signals.exists(folder/"stop-front"),std::invalid_argument);
    std::ofstream(folder/"incoming")<<1;
    fs::rename(folder/"incoming",folder/"stop-plant");
    EXPECT_TRUE(until([&]{return signals.exists(folder/"stop-plant");}));
    fs::rename(folder/"stop-plant",folder/"removed");
    EXPECT_TRUE(until([&]{return !signals.exists(folder/"stop-plant");}));
    signals.finish();EXPECT_FALSE(signals.failed());
    std::uint64_t source=0;std::ifstream(folder/"plant-ready")>>source;EXPECT_EQ(source,456U);
}
TEST_F(FixtureSignalsTest,InvalidSubscriptionsFailBeforeWorkerStarts) {
    EXPECT_THROW((FixtureSignals(folder,"central",{},{},{"misspelled-marker"})),std::invalid_argument);
    EXPECT_THROW(stratadrive::someip::test::fixture_observations("unknown"),std::invalid_argument);
    std::ofstream(folder/"rejoin-request")<<1;
    FixtureSignals signals(folder,"central",{},{},stratadrive::someip::test::fixture_observations("central"));
    EXPECT_TRUE(signals.exists(folder/"rejoin-request"));
    EXPECT_THROW(signals.exists(folder/"armed"),std::invalid_argument);
    signals.finish();EXPECT_FALSE(signals.failed());
}
} // namespace
