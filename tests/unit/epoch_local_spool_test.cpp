#include "epoch_local_spool.hpp"
#include "diagnostics_fixture.hpp"
#include <gtest/gtest.h>
#include <cstdlib>
#include <filesystem>

namespace {
using namespace diagnostics_fixture;
class LocalEpochSpool:public ::testing::Test {
protected:
    std::filesystem::path root;
    EventQueue startup{10,20},control{10,30};
    void SetUp() override {
        char path[]="/tmp/stratadrive-spool-XXXXXX";auto* p=mkdtemp(path);ASSERT_NE(p,nullptr);root=p;
        EpochRecorder::initialize((root/"store").string(),8300,{{64,8,16,8},1,8});
    }
    void TearDown() override {std::filesystem::remove_all(root);}
    Event boundary(unsigned epoch) {auto e=session(epoch,epoch);e.session_enable=stamp(epoch*1000000000ULL);return e;}
    Event tail(unsigned epoch,unsigned sequence) {
        auto e=fault(sequence,Code::SpeedInput,epoch);e.id.producer=e.occurrence.producer=30;e.session_enable=boundary(epoch).session_enable;return e;
    }
};
TEST_F(LocalEpochSpool, NewBoundaryWaitsForActualRetirementAndBothQueueTails) {
    EpochRecorder store((root/"store").string());EpochLocalSpool spool(store,20,30);
    ASSERT_TRUE(startup.publish(boundary(1)));EXPECT_EQ(spool.drain(startup,control,0),1U);
    ASSERT_TRUE(startup.publish(boundary(2)));EXPECT_EQ(spool.drain(startup,control,0),1U);
    EXPECT_EQ(store.watermark(),1U);EXPECT_EQ(spool.pending(),1U);
    // Last old-owner event arrives after the earlier queue snapshot, before cut.
    const auto original=tail(1,1);ASSERT_TRUE(control.publish(original));
    EXPECT_EQ(spool.drain(startup,control,1),1U);ASSERT_EQ(store.watermark(),3U);EXPECT_EQ(spool.pending(),0U);
    EXPECT_EQ(store.segment(),2U);EXPECT_EQ(encode(store.committed(2)),encode(original));
    EXPECT_EQ(encode(store.committed(3)),encode(boundary(2)));EXPECT_TRUE(spool.healthy());
}
TEST_F(LocalEpochSpool, NewEpochObservationWaitsBehindOriginalContextWithoutChangingBytes) {
    EpochRecorder store((root/"store").string());EpochLocalSpool spool(store,20,30);
    ASSERT_TRUE(startup.publish(boundary(1)));spool.drain(startup,control,0);
    const auto old=tail(1,1),fresh=tail(2,2);
    ASSERT_TRUE(control.publish(old));ASSERT_TRUE(control.publish(fresh));
    ASSERT_TRUE(startup.publish(boundary(2)));EXPECT_EQ(spool.drain(startup,control,0),3U);
    EXPECT_EQ(store.watermark(),2U);EXPECT_EQ(spool.pending(),2U);
    EXPECT_EQ(spool.drain(startup,control,1),0U);ASSERT_EQ(store.watermark(),4U);
    EXPECT_EQ(encode(store.committed(2)),encode(old));EXPECT_EQ(encode(store.committed(4)),encode(fresh));
    EXPECT_EQ(store.ledger().find(old.key)->count,2U);EXPECT_TRUE(spool.healthy());
}
TEST_F(LocalEpochSpool, LateOldEventAfterTheRetirementBoundaryFailsClosed) {
    EpochRecorder store((root/"store").string());EpochLocalSpool spool(store,20,30);
    ASSERT_TRUE(startup.publish(boundary(1)));ASSERT_TRUE(startup.publish(boundary(2)));spool.drain(startup,control,1);
    ASSERT_TRUE(control.publish(tail(1,1)));spool.drain(startup,control,1);
    EXPECT_FALSE(spool.healthy());EXPECT_EQ(store.watermark(),2U);EXPECT_FALSE(spool.delivery().next());
}
TEST_F(LocalEpochSpool, RegressedRetirementOrForeignBoundaryCannotQualifyRotation) {
    EpochRecorder store((root/"store").string());EpochLocalSpool spool(store,20,30);
    ASSERT_TRUE(startup.publish(boundary(1)));spool.drain(startup,control,1);spool.drain(startup,control,0);
    EXPECT_FALSE(spool.healthy());EXPECT_EQ(store.watermark(),1U);
}
TEST_F(LocalEpochSpool, ControlObserverCannotFabricateGlobalBoundary) {
    EpochRecorder store((root/"store").string());EpochLocalSpool spool(store,20,30);
    auto foreign=boundary(1);foreign.id.producer=30;ASSERT_TRUE(control.publish(foreign));
    spool.drain(startup,control,0);EXPECT_FALSE(spool.healthy());EXPECT_EQ(store.watermark(),0U);
}
TEST_F(LocalEpochSpool, AbandonedPendingBoundaryIsPersistentlyIncomplete) {
    {
        EpochRecorder store((root/"store").string());EpochLocalSpool spool(store,20,30);
        ASSERT_TRUE(startup.publish(boundary(1)));ASSERT_TRUE(startup.publish(boundary(2)));spool.drain(startup,control,0);
        EXPECT_EQ(spool.pending(),1U);
    }
    EpochRecorder store((root/"store").string());EXPECT_FALSE(store.ledger().complete());
}
TEST_F(LocalEpochSpool, QueueLossAndPublisherBindingAreNotRecoveredByRetirement) {
    EpochRecorder store((root/"store").string());
    EXPECT_THROW((EpochLocalSpool{store,20,20}),std::invalid_argument);
    EpochLocalSpool spool(store,20,30);
    for(unsigned i=0;i<EventQueue::kCapacity;++i)ASSERT_TRUE(control.publish(tail(1,i+1)));
    EXPECT_FALSE(control.publish(tail(1,257)));spool.drain(startup,control,1);
    EXPECT_FALSE(spool.healthy());EXPECT_EQ(store.watermark(),0U);
}
} // namespace
