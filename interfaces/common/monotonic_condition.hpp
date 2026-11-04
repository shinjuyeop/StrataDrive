#pragma once
#include <cerrno>
#include <chrono>
#include <mutex>
#include <pthread.h>
#include <stdexcept>
#include <system_error>
#include <time.h>

namespace stratadrive::runtime {
// Linux monotonic wait, including on toolchains whose sanitizer does not
// intercept pthread_cond_clockwait used by std::condition_variable::wait_for.
// pthread_cond_timedwait observes the clock selected once at construction.
class MonotonicCondition {
    pthread_cond_t condition_{};
public:
    MonotonicCondition() {
        pthread_condattr_t attr{};int e=pthread_condattr_init(&attr);
        if(e)throw std::system_error(e,std::generic_category(),"condition attributes");
        e=pthread_condattr_setclock(&attr,CLOCK_MONOTONIC);
        if(!e)e=pthread_cond_init(&condition_,&attr);
        pthread_condattr_destroy(&attr);
        if(e)throw std::system_error(e,std::generic_category(),"monotonic condition");
    }
    MonotonicCondition(const MonotonicCondition&)=delete;
    MonotonicCondition& operator=(const MonotonicCondition&)=delete;
    ~MonotonicCondition(){pthread_cond_destroy(&condition_);}
    void notify_one() noexcept {pthread_cond_signal(&condition_);}
    template<class Predicate> bool wait_for(std::unique_lock<std::mutex>& lock,std::chrono::microseconds duration,Predicate ready) {
        if(!lock.owns_lock())throw std::logic_error("condition requires owned mutex");
        if(ready())return true;
        if(duration.count()<=0)return false;
        timespec deadline{};
        if(clock_gettime(CLOCK_MONOTONIC,&deadline))throw std::system_error(errno,std::generic_category(),"condition clock");
        const auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();
        deadline.tv_sec+=ns/1000000000;deadline.tv_nsec+=ns%1000000000;
        if(deadline.tv_nsec>=1000000000){++deadline.tv_sec;deadline.tv_nsec-=1000000000;}
        while(!ready()) {
            const int e=pthread_cond_timedwait(&condition_,lock.mutex()->native_handle(),&deadline);
            if(e==ETIMEDOUT)return ready();
            if(e)throw std::system_error(e,std::generic_category(),"condition wait");
        }
        return true;
    }
};
} // namespace stratadrive::runtime
