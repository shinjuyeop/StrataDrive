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
    explicit PlantIO(const std::string& path,bool create=false):fd_(open(path.c_str(),O_RDWR|O_CLOEXEC|(create?(O_CREAT|O_EXCL):0),0600)) {
        check(fd_>=0,"plant IO open");
        if(create){PlantState state;check(pwrite(fd_,&state,sizeof(state),0)==sizeof(state),"plant IO initialize");}
    }
    template<class F> bool update(F f) {
        if(flock(fd_,LOCK_EX|LOCK_NB)!=0) {check(errno==EWOULDBLOCK,"plant IO lock");return false;}
        PlantState s;const bool ok=pread(fd_,&s,sizeof(s),0)==sizeof(s) && s.magic==0x5344504c414e5401ULL;
        if(ok)f(s);
        const bool written=ok && pwrite(fd_,&s,sizeof(s),0)==sizeof(s);
        flock(fd_,LOCK_UN);check(written,"plant IO transfer");return true;
    }
    ~PlantIO(){close(fd_);}
};
}
