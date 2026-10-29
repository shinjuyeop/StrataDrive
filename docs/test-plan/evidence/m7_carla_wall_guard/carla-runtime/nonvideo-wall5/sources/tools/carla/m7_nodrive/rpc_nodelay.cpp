// Opt-in diagnostic shim for this isolated M7 loopback RPC endpoint only.
// No packet contents, credentials, deadlines, or application messages change.
#include <atomic>
#include <cerrno>
#include <cstdio>
#include <dlfcn.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
namespace {
std::atomic<unsigned> changed{0},already{0},errors{0};
void configure(int fd) {
    sockaddr_in address{};socklen_t size=sizeof(address);
    if(getpeername(fd,reinterpret_cast<sockaddr*>(&address),&size))return;
    if(address.sin_family!=AF_INET || ntohl(address.sin_addr.s_addr)!=INADDR_LOOPBACK)return;
    const auto remote=ntohs(address.sin_port);
    size=sizeof(address);
    if(getsockname(fd,reinterpret_cast<sockaddr*>(&address),&size))return;
    if(remote!=2200 && ntohs(address.sin_port)!=2200)return;
    int old=0;socklen_t length=sizeof(old);
    if(getsockopt(fd,IPPROTO_TCP,TCP_NODELAY,&old,&length)){++errors;return;}
    int enabled=1;
    if(setsockopt(fd,IPPROTO_TCP,TCP_NODELAY,&enabled,sizeof(enabled)))++errors;
    else if(old)++already;else ++changed;
}
__attribute__((destructor)) void report() {
    std::fprintf(stderr,"M7 loopback RPC TCP_NODELAY changed=%u already=%u errors=%u\n",changed.load(),already.load(),errors.load());
}
}
extern "C" int connect(int fd,const sockaddr* address,socklen_t size) {
    static const auto original=reinterpret_cast<int(*)(int,const sockaddr*,socklen_t)>(dlsym(RTLD_NEXT,"connect"));
    const int result=original(fd,address,size),saved=errno;
    if(result==0)configure(fd);
    // Nonblocking connect: setting this option does not require establishment.
    else if(saved==EINPROGRESS && address && size>=sizeof(sockaddr_in) && address->sa_family==AF_INET) {
        const auto* ip=reinterpret_cast<const sockaddr_in*>(address);
        if(ntohl(ip->sin_addr.s_addr)==INADDR_LOOPBACK && ntohs(ip->sin_port)==2200) {
            int old=0,enabled=1;socklen_t length=sizeof(old);
            if(getsockopt(fd,IPPROTO_TCP,TCP_NODELAY,&old,&length) || setsockopt(fd,IPPROTO_TCP,TCP_NODELAY,&enabled,sizeof(enabled)))++errors;
            else if(old)++already;else ++changed;
        }
    }
    errno=saved;return result;
}
extern "C" int accept(int fd,sockaddr* address,socklen_t* size) {
    static const auto original=reinterpret_cast<int(*)(int,sockaddr*,socklen_t*)>(dlsym(RTLD_NEXT,"accept"));
    const int result=original(fd,address,size),saved=errno;if(result>=0)configure(result);errno=saved;return result;
}
extern "C" int accept4(int fd,sockaddr* address,socklen_t* size,int flags) {
    static const auto original=reinterpret_cast<int(*)(int,sockaddr*,socklen_t*,int)>(dlsym(RTLD_NEXT,"accept4"));
    const int result=original(fd,address,size,flags),saved=errno;if(result>=0)configure(result);errno=saved;return result;
}
