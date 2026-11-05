#include "../integration/someip/owner_schedule.hpp"
#include <gtest/gtest.h>
#include <deque>
#include <vector>

namespace {
using stratadrive::someip::test::IngressTurn;
using stratadrive::someip::test::StopRequestRelease;
struct Network {
    std::array<std::deque<int>,4> queues;
    unsigned channels() const {return 4;}
    std::optional<int> pop(unsigned lane) {
        if(queues[lane].empty())return std::nullopt;
        const auto value=queues[lane].front();queues[lane].pop_front();return value;
    }
};
TEST(OwnerSchedule, ArrivalsBetweenSensorAndControlWorkReachSameTurnWithoutIncreasingBudget) {
    Network net;IngressTurn turn;std::vector<int> seen;
    net.queues[2].push_back(1);
    const auto receive=[&](int value){seen.push_back(value);};
    turn.drain(net,receive);
    // New PowerStatus arrives while owner performs its non-network work.
    for(int i=2;i<=9;++i)net.queues[2].push_back(i);
    turn.drain(net,receive);
    ASSERT_EQ(seen.size(),8U);EXPECT_EQ(seen.back(),8);
    ASSERT_EQ(net.queues[2].size(),1U);EXPECT_EQ(net.queues[2].front(),9);
    turn.drain(net,receive);EXPECT_EQ(seen.size(),8U);
    IngressTurn next;next.drain(net,receive);EXPECT_EQ(seen.back(),9);
}
TEST(OwnerSchedule, AuthorityPrecedesNormalLanesAndDoesNotEraseTheirContents) {
    Network net;IngressTurn turn;std::vector<int> seen;
    for(unsigned lane=0;lane<4;++lane)net.queues[lane].push_back(static_cast<int>(lane));
    turn.drain(net,[&](int value){seen.push_back(value);});
    EXPECT_EQ(seen,(std::vector<int>{1,3,0,2}));
}
TEST(OwnerSchedule, StopRenewalRunsBeforeManagementInsteadOfDriftingPastIt) {
    constexpr std::uint64_t enable=1000000000,ms=1000000;
    StopRequestRelease release;
    EXPECT_FALSE(release.due(enable,enable+3*ms,true));
    EXPECT_TRUE(release.due(enable,enable+4*ms,true));
    EXPECT_FALSE(release.due(enable,enable+24*ms,false));
    EXPECT_TRUE(release.due(enable,enable+24*ms+500000,true));
    EXPECT_FALSE(release.due(enable,enable+34*ms,true));
    // Execution jitter does not move the next release to +44.5ms.
    EXPECT_TRUE(release.due(enable,enable+44*ms,true));
    EXPECT_FALSE(release.due(enable,enable+44*ms,true));
}
TEST(OwnerSchedule, MissedStopReleasesAreSkippedAndNeverReplayedAfterRollback) {
    StopRequestRelease release;
    EXPECT_TRUE(release.due(100,4000100,true));
    EXPECT_TRUE(release.due(100,104000100,true));
    EXPECT_FALSE(release.due(100,104000100,true));
    EXPECT_FALSE(release.due(100,24000100,true));
    EXPECT_FALSE(release.due(100,99,true));
    EXPECT_TRUE(release.due(100,124000100,true));
}
}
