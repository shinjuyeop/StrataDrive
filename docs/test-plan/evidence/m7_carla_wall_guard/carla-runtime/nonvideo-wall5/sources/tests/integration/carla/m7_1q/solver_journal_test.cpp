#include "solver_journal.hpp"
#include <gtest/gtest.h>
namespace {
using Journal=stratadrive::m7_native::SolverJournal<2>;
M7SolverTrace trace() {
    M7SolverTrace value{};value.abi=2;value.count=320;value.dt=.01f;
    value.steps[319].after[2]=-1.234567f;value.protected_steer_hold=1;return value;
}
TEST(M7SolverJournal, CopiesRawEvidenceBeforeObserverReuseAndNeverConsumesReads) {
    Journal journal;auto original=trace();ASSERT_TRUE(journal.append(42,7,original));
    original.steps[319].after[2]=999;
    ASSERT_NE(journal.find(7),nullptr);
    EXPECT_FLOAT_EQ(journal.find(7)->trace.steps[319].after[2],-1.234567f);
    EXPECT_EQ(journal.find(7)->frame,42U);EXPECT_EQ(journal.find(7)->trace.protected_steer_hold,1U);
    EXPECT_EQ(journal.find(7),journal.find(7));EXPECT_EQ(journal.find(8),nullptr);
    EXPECT_EQ(journal.size(),1U);
}
TEST(M7SolverJournal, CapacityFailureRetainsAllPriorEvidenceAndLatches) {
    Journal journal;auto value=trace();ASSERT_TRUE(journal.append(10,4,value));
    ASSERT_TRUE(journal.append(11,6,value));EXPECT_TRUE(journal.full());
    EXPECT_FALSE(journal.append(12,7,value));EXPECT_TRUE(journal.failed());
    EXPECT_EQ(journal.find(4)->frame,10U);EXPECT_EQ(journal.find(6)->frame,11U);
    EXPECT_EQ(journal.find(7),nullptr);EXPECT_EQ(journal.size(),2U);
}
TEST(M7SolverJournal, RejectsDuplicateTicketSkippedFrameAndWrongAbiWithoutHealing) {
    for(unsigned fault=0;fault<4;++fault) {
        Journal journal;auto value=trace();ASSERT_TRUE(journal.append(30,2,value));
        if(fault==2)value.abi=1;
        if(fault==3)value.count=321;
        EXPECT_FALSE(journal.append(fault==1?32:31,fault==0?2:3,value));
        EXPECT_FALSE(journal.append(31,3,trace()));EXPECT_EQ(journal.size(),1U);
        Journal new_session;EXPECT_TRUE(new_session.append(50,9,trace()));
    }
}
}
