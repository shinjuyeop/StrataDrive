#include "../../interfaces/common/concurrent_trace_buffer.hpp"
#include "../../interfaces/common/monotonic_condition.hpp"
#include <gtest/gtest.h>
#include <array>
#include <thread>
#include <mutex>
#include <set>

namespace {
struct Row {std::size_t id{0},check{0};};
void parallel_records(std::size_t capacity) {
    stratadrive::runtime::ConcurrentTraceBuffer<Row> trace(capacity);
    std::array<std::thread,4> writers;std::atomic<unsigned> accepted{0};
    for(unsigned w=0;w<writers.size();++w)writers[w]=std::thread([&,w]{
        for(unsigned i=0;i<1024;++i){const std::size_t id=w*1024+i;if(trace.append({id,~id}))++accepted;}
    });
    for(auto& writer:writers)writer.join();
    ASSERT_EQ(trace.size(),capacity);EXPECT_EQ(accepted,capacity);
    EXPECT_EQ(trace.overflowed(),capacity<4096);
    std::set<std::size_t> ids;
    for(std::size_t i=0;i<trace.size();++i){EXPECT_EQ(trace[i].check,~trace[i].id);ids.insert(trace[i].id);}
    EXPECT_EQ(ids.size(),capacity);
    for(unsigned i=0;i<16;++i)EXPECT_FALSE(trace.append({99999,0}));
    EXPECT_EQ(trace.size(),capacity);EXPECT_TRUE(trace.overflowed());
    for(std::size_t i=0;i<trace.size();++i)EXPECT_EQ(trace[i].check,~trace[i].id);
}
TEST(ConcurrentTraceBuffer, ParallelWritersPreserveEveryCompleteRecordAfterJoin) {parallel_records(4096);}
TEST(ConcurrentTraceBuffer, ConcurrentOverflowCannotOverwriteOrWrapReservedSlots) {parallel_records(128);}
struct Pause {
    std::mutex mutex;stratadrive::runtime::MonotonicCondition condition;
    bool entered{false},release{false},other_done{false};
};
struct PausedRow {
    unsigned id{0};Pause* pause{nullptr};
    PausedRow& operator=(const PausedRow& row) noexcept {
        if(row.pause){std::unique_lock<std::mutex> lock(row.pause->mutex);
            row.pause->entered=true;row.pause->condition.notify_one();
            while(!row.pause->release)row.pause->condition.wait_for(lock,std::chrono::seconds(1),[&]{return row.pause->release;});}
        id=row.id;pause=row.pause;return *this;
    }
};
TEST(ConcurrentTraceBuffer, PausedWriterDoesNotHoldAnotherWritersSlot) {
    stratadrive::runtime::ConcurrentTraceBuffer<PausedRow> trace(2);Pause pause;
    std::thread first([&]{trace.append({1,&pause});});
    bool entered=false,completed=false;
    {std::unique_lock<std::mutex> lock(pause.mutex);entered=pause.condition.wait_for(lock,std::chrono::seconds(1),[&]{return pause.entered;});}
    std::thread second([&]{trace.append({2,nullptr});std::lock_guard<std::mutex> lock(pause.mutex);pause.other_done=true;pause.condition.notify_one();});
    {std::unique_lock<std::mutex> lock(pause.mutex);completed=pause.condition.wait_for(lock,std::chrono::seconds(1),[&]{return pause.other_done;});pause.release=true;pause.condition.notify_one();}
    first.join();second.join();EXPECT_TRUE(entered);EXPECT_TRUE(completed);
    ASSERT_EQ(trace.size(),2U);EXPECT_EQ(trace[0].id,1U);EXPECT_EQ(trace[1].id,2U);EXPECT_FALSE(trace.overflowed());
}
} // namespace
