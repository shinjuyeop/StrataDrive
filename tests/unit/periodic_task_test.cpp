#include "periodic_task.hpp"
#include "latest_snapshot.hpp"

#include <gtest/gtest.h>
#include <limits>
#include <stdexcept>
#include <thread>

namespace {
using stratadrive::runtime::TaskSchedule;
using stratadrive::runtime::DeadlineMonitor;
TEST(LatestSnapshot, BeforeFirstPublicationIsUnavailableAndRepeatedReadPreservesIdentity) {
    stratadrive::runtime::LatestSnapshot<std::uint64_t> port;
    EXPECT_FALSE(port.read()); port.publish(7);
    EXPECT_EQ(port.read(),7U); EXPECT_EQ(port.read(),7U);
    EXPECT_EQ(port.overwrites(),0U);
}
TEST(LatestSnapshot, BurstKeepsLatestValueAndCountsSupersededPublications) {
    stratadrive::runtime::LatestSnapshot<std::uint64_t> port;
    port.publish(1); port.publish(2); port.publish(3);
    EXPECT_EQ(port.read(),3U); EXPECT_EQ(port.overwrites(),2U);
    port.publish(4); EXPECT_EQ(port.read(),4U); EXPECT_EQ(port.overwrites(),2U);
}
TEST(LatestSnapshot, ConcurrentOwnerCopiesCannotTearOrRegressAnAcquisition) {
    struct Sample { std::uint64_t sequence{0}; std::array<std::uint64_t,32> payload{}; };
    stratadrive::runtime::LatestSnapshot<Sample> port;
    std::atomic<bool> finished{false};
    constexpr std::uint64_t count=100000;
    std::thread publisher([&] {
        for(std::uint64_t i=1;i<=count;++i) {
            Sample sample; sample.sequence=i; sample.payload.fill(i ^ 0xabcdefU); port.publish(sample);
        }
        finished.store(true,std::memory_order_release);
    });
    std::uint64_t previous=0;
    bool consistent=true;
    do {
        if(const auto sample=port.read()) {
            consistent=consistent && sample->sequence>=previous;
            for(const auto value:sample->payload) consistent=consistent && value==(sample->sequence ^ 0xabcdefU);
            previous=sample->sequence;
        }
    } while(!finished.load(std::memory_order_acquire));
    publisher.join();
    ASSERT_TRUE(port.read()); EXPECT_EQ(port.read()->sequence,count); EXPECT_TRUE(consistent);
}
TEST(PeriodicTask, AbsoluteReleasesDoNotDriftAndDeadlineIsIndependent) {
    const TaskSchedule schedule({100, 10, 7, 4});
    EXPECT_EQ(schedule.release(0), 100U); EXPECT_EQ(schedule.release(3), 130U);
    EXPECT_EQ(schedule.deadline(3), 137U);
    EXPECT_FALSE(schedule.newest_released(99,0)); EXPECT_EQ(schedule.newest_released(100,0),0U);
}
TEST(PeriodicTask, LateWakeSelectsNewestJobWithoutCatchUp) {
    const TaskSchedule schedule({100,10,5,10});
    EXPECT_EQ(schedule.newest_released(137,1),3U);
    EXPECT_FALSE(schedule.newest_released(137,4));
    EXPECT_EQ(schedule.newest_released(999,4),9U);
    EXPECT_FALSE(schedule.newest_released(999,10));
}
TEST(PeriodicTask, InvalidAndOverflowingSchedulesAreRejectedBeforeExecution) {
    EXPECT_THROW(TaskSchedule({0,10,5,1}),std::invalid_argument);
    EXPECT_THROW(TaskSchedule({1,0,5,1}),std::invalid_argument);
    EXPECT_THROW(TaskSchedule({1,10,0,1}),std::invalid_argument);
    EXPECT_THROW(TaskSchedule({1,10,5,0}),std::invalid_argument);
    EXPECT_THROW(TaskSchedule({1,10,5,10001}),std::invalid_argument);
    constexpr auto maximum=std::numeric_limits<std::uint64_t>::max();
    EXPECT_THROW(TaskSchedule({maximum,10,1,1}),std::invalid_argument);
    EXPECT_THROW(TaskSchedule({maximum-20,10,5,3}),std::invalid_argument);
    EXPECT_EQ(TaskSchedule({maximum-20,10,10,2}).deadline(1),maximum);
}
TEST(PeriodicTask, OverlappingJobDeadlinesAreExplicitlySupported) {
    const TaskSchedule schedule({100,10,25,3}); DeadlineMonitor monitor(schedule);
    ASSERT_TRUE(monitor.finish(1,119)); monitor.poll(124); EXPECT_FALSE(monitor.faulted());
    monitor.poll(125); ASSERT_TRUE(monitor.first_fault()); EXPECT_EQ(monitor.first_fault()->job,0U);
    monitor.poll(135); EXPECT_EQ(monitor.detected(1),0U);
}
TEST(PeriodicTask, FinishingExactlyAtDeadlineIsOnTime) {
    DeadlineMonitor monitor(TaskSchedule({100,10,5,2}));
    ASSERT_TRUE(monitor.finish(0,105)); monitor.poll(105); EXPECT_FALSE(monitor.faulted());
    ASSERT_TRUE(monitor.finish(1,115)); monitor.poll(115); EXPECT_FALSE(monitor.faulted());
}
TEST(PeriodicTask, UnstartedJobIsMissedWithoutAnyExecutorCallback) {
    DeadlineMonitor monitor(TaskSchedule({100,10,5,3}));
    monitor.poll(104); EXPECT_FALSE(monitor.faulted()); monitor.poll(105);
    ASSERT_TRUE(monitor.first_fault()); EXPECT_EQ(monitor.first_fault()->detected_ns,105U);
    EXPECT_EQ(monitor.first_fault()->deadline_ns,105U); EXPECT_EQ(monitor.finished(0),0U);
}
TEST(PeriodicTask, LateCompletionDoesNotEraseARecordedMiss) {
    DeadlineMonitor monitor(TaskSchedule({100,10,5,2})); monitor.poll(106);
    ASSERT_TRUE(monitor.finish(0,108)); monitor.poll(109);
    EXPECT_TRUE(monitor.faulted()); EXPECT_EQ(monitor.detected(0),106U); EXPECT_EQ(monitor.finished(0),108U);
}
TEST(PeriodicTask, LateCompletionIsFoundEvenWhenMonitorWakesAfterIt) {
    DeadlineMonitor monitor(TaskSchedule({100,10,5,2}));
    ASSERT_TRUE(monitor.finish(0,106)); monitor.poll(109);
    EXPECT_TRUE(monitor.faulted()); EXPECT_EQ(monitor.detected(0),109U);
}
TEST(PeriodicTask, SkippedAndNeverStartedJobsRemainInTheDenominator) {
    DeadlineMonitor monitor(TaskSchedule({100,10,5,5}));
    ASSERT_TRUE(monitor.finish(0,101)); ASSERT_TRUE(monitor.finish(3,131)); monitor.poll(150);
    std::size_t missed=0;
    for(std::size_t i=0;i<5;++i) if(monitor.detected(i)!=0) ++missed;
    EXPECT_EQ(missed,3U); EXPECT_EQ(monitor.detected(1),150U); EXPECT_EQ(monitor.detected(4),150U);
}
TEST(PeriodicTask, InvalidAndDuplicateCompletionCannotRefreshProgress) {
    DeadlineMonitor monitor(TaskSchedule({100,10,5,2}));
    EXPECT_FALSE(monitor.finish(0,99)); EXPECT_FALSE(monitor.finish(2,120));
    ASSERT_TRUE(monitor.finish(0,104)); EXPECT_FALSE(monitor.finish(0,115)); EXPECT_EQ(monitor.finished(0),104U);
    EXPECT_THROW(monitor.finished(2),std::out_of_range);
    EXPECT_THROW(monitor.detected(2),std::out_of_range);
}
TEST(PeriodicTask, ClockRollbackIsLatchedSeparatelyFromJobFailure) {
    DeadlineMonitor monitor(TaskSchedule({100,10,5,2}));
    monitor.poll(100); monitor.poll(99); EXPECT_TRUE(monitor.clock_error());
    monitor.poll(104); EXPECT_TRUE(monitor.clock_error()); EXPECT_FALSE(monitor.faulted());
}
} // namespace
