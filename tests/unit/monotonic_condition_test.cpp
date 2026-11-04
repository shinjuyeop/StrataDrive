#include "../../interfaces/common/monotonic_condition.hpp"
#include <gtest/gtest.h>
#include <atomic>
#include <thread>

namespace {
using stratadrive::runtime::MonotonicCondition;
using namespace std::chrono_literals;
TEST(MonotonicCondition,NotificationPublishesProtectedDataWithoutLostWake) {
    MonotonicCondition ready;std::mutex mutex;unsigned produced=0,consumed=0;std::atomic<bool> failed{false};
    std::thread producer([&]{for(unsigned i=1;i<=1000;++i){
        std::unique_lock<std::mutex> lock(mutex);
        if(!ready.wait_for(lock,2s,[&]{return produced==consumed;})){failed=true;return;}
        produced=i;ready.notify_one();
    }});
    {std::unique_lock<std::mutex> lock(mutex);while(consumed<1000){
        if(!ready.wait_for(lock,2s,[&]{return produced>consumed;})){failed=true;break;}
        EXPECT_EQ(produced,consumed+1);consumed=produced;ready.notify_one();
    }}
    producer.join();EXPECT_FALSE(failed);EXPECT_EQ(consumed,1000U);
}
TEST(MonotonicCondition,SpuriousNotificationsDoNotRenewTheOriginalTimeout) {
    MonotonicCondition ready;std::mutex mutex;std::atomic<bool> stop{false};
    std::thread notifications([&]{while(!stop){ready.notify_one();std::this_thread::sleep_for(100us);}});
    const auto start=std::chrono::steady_clock::now();
    {std::unique_lock<std::mutex> lock(mutex);EXPECT_FALSE(ready.wait_for(lock,10ms,[]{return false;}));EXPECT_TRUE(lock.owns_lock());}
    const auto elapsed=std::chrono::steady_clock::now()-start;stop=true;notifications.join();
    EXPECT_GE(elapsed,10ms);EXPECT_LT(elapsed,1s);
}
TEST(MonotonicCondition,PreexistingPredicateAndZeroTimeoutDoNotNeedANotification) {
    MonotonicCondition ready;std::mutex mutex;std::unique_lock<std::mutex> lock(mutex);
    EXPECT_TRUE(ready.wait_for(lock,0us,[]{return true;}));
    EXPECT_FALSE(ready.wait_for(lock,0us,[]{return false;}));
    lock.unlock();EXPECT_THROW(ready.wait_for(lock,1us,[]{return true;}),std::logic_error);
}
} // namespace
