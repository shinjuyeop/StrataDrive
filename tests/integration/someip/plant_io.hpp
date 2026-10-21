#pragma once
#include "m4_owner_network.hpp"
#include "adapter_transport.hpp"
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#include <type_traits>

namespace stratadrive::someip {
// Host SIL sensor/actuator bus only. Never carries session/control/ACK/feedback.
// PhysicalOwner is the unique model owner; one writer per Leaf output slot.
struct PlantState {
    std::uint64_t magic=0x5344504c414e5401ULL;
    simulation::OwnerSensors sensors{};
    std::array<simulation::OwnerActuation,5> outputs{};
    std::uint32_t released_epoch=0;
};
static_assert(std::is_trivially_copyable_v<PlantState>);
class PlantIO {
    int fd_;
public:
    std::uint64_t attempts=0,busy=0,errors=0,last_error_ns=0,first_busy_ns=0,last_busy_ns=0;int last_errno=0;
    explicit PlantIO(const std::string& path,bool create=false):fd_(open(path.c_str(),O_RDWR|O_CLOEXEC|(create?(O_CREAT|O_EXCL):0),0600)) {
        check(fd_>=0,"plant IO open");
        if(create){PlantState state;check(pwrite(fd_,&state,sizeof(state),0)==sizeof(state),"plant IO initialize");}
    }
    template<class F> bool update(F f) {
        ++attempts;
        if(flock(fd_,LOCK_EX|LOCK_NB)!=0) {if(errno==EWOULDBLOCK){++busy;last_busy_ns=now();if(!first_busy_ns)first_busy_ns=last_busy_ns;return false;}++errors;last_errno=errno;last_error_ns=now();check(false,"plant IO lock");}
        PlantState s;const bool ok=pread(fd_,&s,sizeof(s),0)==sizeof(s) && s.magic==0x5344504c414e5401ULL;
        if(ok)f(s);
        const bool written=ok && pwrite(fd_,&s,sizeof(s),0)==sizeof(s);
        const int saved=errno;const int unlocked=flock(fd_,LOCK_UN);
        if(!written || unlocked){++errors;last_errno=unlocked?errno:saved;last_error_ns=now();check(false,"plant IO transfer");}return true;
    }
    ~PlantIO(){close(fd_);}
};
}
