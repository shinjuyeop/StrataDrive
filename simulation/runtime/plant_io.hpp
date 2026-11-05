#pragma once
#include "async_leaf_owner.hpp"
#include <cerrno>
#include <chrono>
#include <cstddef>
#include <fcntl.h>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <unistd.h>

namespace stratadrive::simulation {
// Host SIL only: each field has one writer. No authority/ACK/Actual transport.
struct PlantState {
    std::uint64_t magic=0x5344504c414e5401ULL;
    OwnerSensors sensors{};
    std::array<OwnerActuation,5> outputs{};
    std::uint32_t released_epoch=0;
};
static_assert(std::is_trivially_copyable_v<PlantState> && std::is_standard_layout_v<PlantState>);
class PlantIO {
    int fd_;
    static std::uint64_t now() { return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
    [[noreturn]] void fail(const char* message,int code) {
        ++errors;last_errno=code;last_error_ns=now();throw std::runtime_error(message);
    }
    bool transfer(std::size_t offset,void* value,std::size_t size,bool write) {
        ++attempts;
        struct flock lock{};lock.l_type=write?F_WRLCK:F_RDLCK;lock.l_whence=SEEK_SET;
        lock.l_start=static_cast<off_t>(offset);lock.l_len=static_cast<off_t>(size);
        // OFD locks also isolate two independently opened handles in one process.
        // Never hold a lock across callbacks, model work or other fields.
        if(fcntl(fd_,F_OFD_SETLK,&lock)!=0) {
            if(errno==EAGAIN || errno==EACCES) {++busy;last_busy_ns=now();if(!first_busy_ns)first_busy_ns=last_busy_ns;return false;}
            fail("plant IO lock",errno);
        }
        const auto count=write?pwrite(fd_,value,size,lock.l_start):pread(fd_,value,size,lock.l_start);
        const int saved=errno;lock.l_type=F_UNLCK;
        const int unlocked=fcntl(fd_,F_OFD_SETLK,&lock);
        if(unlocked)fail("plant IO unlock",errno);
        if(count!=static_cast<ssize_t>(size))fail("plant IO transfer",count<0?saved:EIO);
        return true;
    }
    template<class T> std::optional<T> read(std::size_t offset) {
        T value{};if(!transfer(offset,&value,sizeof(value),false))return std::nullopt;return value;
    }
    template<class T> bool write(std::size_t offset,const T& value) {
        return transfer(offset,const_cast<T*>(&value),sizeof(value),true);
    }
    static std::size_t output_offset(unsigned leaf) {
        if(leaf>=5)throw std::out_of_range("plant IO leaf");
        return offsetof(PlantState,outputs)+leaf*sizeof(OwnerActuation);
    }
public:
    std::uint64_t attempts=0,busy=0,errors=0,last_error_ns=0,first_busy_ns=0,last_busy_ns=0;int last_errno=0;
    explicit PlantIO(const std::string& path,bool create=false):fd_(open(path.c_str(),O_RDWR|O_CLOEXEC|(create?(O_CREAT|O_EXCL):0),0600)) {
        if(fd_<0)throw std::runtime_error("plant IO open");
        PlantState state{};std::uint64_t magic=0;
        const bool ok=create?pwrite(fd_,&state,sizeof(state),0)==sizeof(state):
            pread(fd_,&magic,sizeof(magic),0)==sizeof(magic) && magic==state.magic;
        if(!ok){close(fd_);throw std::runtime_error("plant IO initialize");}
    }
    PlantIO(const PlantIO&)=delete;PlantIO& operator=(const PlantIO&)=delete;
    std::optional<OwnerSensors> read_sensors() {return read<OwnerSensors>(offsetof(PlantState,sensors));}
    bool write_sensors(const OwnerSensors& value) {return write(offsetof(PlantState,sensors),value);}
    std::optional<OwnerActuation> read_output(unsigned leaf) {return read<OwnerActuation>(output_offset(leaf));}
    bool write_output(unsigned leaf,const OwnerActuation& value) {return write(output_offset(leaf),value);}
    std::optional<std::uint32_t> read_release() {return read<std::uint32_t>(offsetof(PlantState,released_epoch));}
    bool write_release(std::uint32_t value) {return write(offsetof(PlantState,released_epoch),value);}
    ~PlantIO(){close(fd_);}
};
}
