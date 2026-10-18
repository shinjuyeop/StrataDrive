#include "multirate_fixture.hpp"
#ifdef __linux__
#include "multirate_runtime.hpp"
#endif
#include <gtest/gtest.h>

namespace {
using stratadrive::simulation::multirate_fixture::TrustedHistory;
using namespace stratadrive;
can::BmsFrame frame(std::uint32_t sequence) {
    can::BmsMessage m; m.kind=can::BmsFrameKind::PowerRequest; m.epoch=1; m.sequence=sequence;
    m.source_time_ns=1000+sequence; m.origin=can::ActuatorOrigin::NormalPath;
    m.causal_sequence=100+sequence; m.content=can::BmsPowerRequest{can::BmsPowerAction::Enable,2000,m.source_time_ns};
    can::BmsTxState tx{m.kind}; return can::encode_bms_frame(m,tx).value();
}
TEST(RuntimeTrust, ReceivingAnUnissuedFrameDoesNotCreateAuthority) {
    TrustedHistory history; EXPECT_FALSE(history.find(frame(0)));
}
TEST(RuntimeTrust, ExactIssuedEnvelopeRecoversOnlyItsSeparateParent) {
    TrustedHistory history; const auto f=frame(0);
    history.issue(f,can::BmsParentContext{7,42,900,2000});
    const auto matched=history.find(f); ASSERT_TRUE(matched); ASSERT_TRUE(matched->parent);
    EXPECT_EQ(matched->parent->epoch,7U); EXPECT_EQ(matched->parent->sequence,42U);
    EXPECT_EQ(matched->parent->source_time_ns,900U);
}
TEST(RuntimeTrust, ChangedPayloadOrEnvelopeCannotBorrowAnIssuedParent) {
    TrustedHistory history; const auto f=frame(0); history.issue(f,can::BmsParentContext{1,100,1000,2000});
    auto altered=f; altered.payload[0]^=1; EXPECT_FALSE(history.find(altered));
    altered=f; altered.is_fd=false; EXPECT_FALSE(history.find(altered));
    altered=f; altered.fd_flags^=1; EXPECT_FALSE(history.find(altered));
    altered=f; altered.payload_length=64; EXPECT_FALSE(history.find(altered));
    altered=f; altered.can_id=0x194; EXPECT_FALSE(history.find(altered));
}
TEST(RuntimeTrust, BoundedHistoryExpiresOldAuthorityWithoutLearningFromReplay) {
    TrustedHistory history;
    for(std::uint32_t i=0;i<5;++i) history.issue(frame(i),can::BmsParentContext{1,100+i,1000+i,2000});
    EXPECT_FALSE(history.find(frame(0))); EXPECT_TRUE(history.find(frame(1))); EXPECT_TRUE(history.find(frame(4)));
}
#ifdef __linux__
TEST(RuntimeScheduling, PreservesEveryExplicitPriorityIncludingSupportedBoundaries) {
    EXPECT_EQ(simulation::parse_runtime_owner_fifo("1,10,9,10,18,20,99"), (std::array<int,7>{1,10,9,10,18,20,99}));
}
TEST(RuntimeScheduling, RejectsPartialMalformedAndOutOfRangePriorityMaps) {
    for(const auto* value:{"", "1,2,3", "0,10,9,10,18,20,19", "100,10,9,10,18,20,19",
            "-1,10,9,10,18,20,19", "1,10,9,10,18,20,19,1", "1,10,9,10,18,20,19,",
            "1,10,9,10,18,20,19x", "1,10,9,10,18,20, 19", "99999999999999999,10,9,10,18,20,19"}) {
        EXPECT_THROW(simulation::parse_runtime_owner_fifo(value),std::invalid_argument) << value;
    }
}
#endif
} // namespace
