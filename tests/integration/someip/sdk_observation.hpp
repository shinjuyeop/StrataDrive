#pragma once
// Diagnostic-only header injected into an isolated, pinned SDK build. Never
// linked into the standard SDK. One application per process; stop from owner.
#include "../../../interfaces/common/concurrent_trace_buffer.hpp"
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <memory>
#include <stdexcept>
#include <string>
#include <sched.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

namespace stratadrive::sdk_observation {
struct Stamp {
    std::uint64_t ns{}, cpu_ns{};
    long voluntary{}, involuntary{};
    int tid{}, cpu{};
};
inline Stamp stamp() noexcept {
    timespec wall{}, cpu{}; rusage usage{};
    const bool ok=clock_gettime(CLOCK_MONOTONIC,&wall)==0 &&
        clock_gettime(CLOCK_THREAD_CPUTIME_ID,&cpu)==0 && getrusage(RUSAGE_THREAD,&usage)==0;
    return {ok?std::uint64_t(wall.tv_sec)*1000000000+std::uint64_t(wall.tv_nsec):0,
            ok?std::uint64_t(cpu.tv_sec)*1000000000+std::uint64_t(cpu.tv_nsec):0,
            usage.ru_nvcsw,usage.ru_nivcsw,static_cast<int>(syscall(SYS_gettid)),sched_getcpu()};
}
struct Key {
    unsigned service{}, method{}, client{}, session{}, bytes{}, crc{};
};
struct Row { Stamp time; const char* stage{}; Key key; };
struct Buffer {
    static constexpr std::size_t capacity=262144;
    runtime::ConcurrentTraceBuffer<Row> rows{capacity};
    std::string path;
    explicit Buffer(std::string file):path(std::move(file)) {}
};
inline std::unique_ptr<Buffer> buffer;
inline void init() {
    if(const char* path=std::getenv("STRATADRIVE_SDK_TRACE")) {
        if(buffer || !*path)throw std::runtime_error("SDK observation requires one application and a trace path");
        buffer=std::make_unique<Buffer>(path); // fault pages before SDK threads
    }
}
inline unsigned be16(const std::uint8_t* p) noexcept {return (unsigned(p[0])<<8)|p[1];}
inline unsigned be32(const std::uint8_t* p) noexcept {return (be16(p)<<16)|be16(p+2);}
inline unsigned crc(const std::uint8_t* p,std::size_t n) noexcept {
    if(n<4)return 0;
    return unsigned(p[n-4])|(unsigned(p[n-3])<<8)|(unsigned(p[n-2])<<16)|(unsigned(p[n-1])<<24);
}
inline void record(const char* stage,Key key,Stamp time=stamp()) noexcept {
    if(buffer)buffer->rows.append({time,stage,key});
}
// Called only for complete SOME/IP messages, or a complete send buffer. TCP
// fragment assembly remains the SDK's responsibility. No allocations/IO here.
inline void wire(const char* stage,const std::uint8_t* p,std::size_t n,const Stamp& time=stamp()) noexcept {
    while(n>=16) {
        const auto length=be32(p+4);
        if(length<8 || length>n-8)return;
        record(stage,{be16(p),be16(p+2),be16(p+8),be16(p+10),length-8,crc(p+16,length-8)},time);
        p+=length+8;n-=length+8;
    }
}
template<class Message> inline Key key(const Message& m) {
    const auto p=m->get_payload();const auto n=p?p->get_length():0;
    return {m->get_service(),m->get_method(),m->get_client(),m->get_session(),n,p?crc(p->get_data(),n):0};
}
// Must run after ALL IO/dispatcher writers join. A killed process intentionally
// has no completed trace. Overflow, clock failure and missing flush fail audit.
inline void flush() {
    if(!buffer)return;
    std::ofstream out(buffer->path,std::ios::out);
    out<<"ns,cpu_ns,voluntary,involuntary,tid,cpu,stage,service,method,client,session,bytes,crc\n";
    bool clocks=true;
    for(std::size_t i=0;i<buffer->rows.size();++i) {
        const auto& r=buffer->rows[i];const auto& t=r.time;const auto& k=r.key;
        clocks=clocks && t.ns && t.cpu_ns && t.tid>0 && t.cpu>=0;
        out<<t.ns<<','<<t.cpu_ns<<','<<t.voluntary<<','<<t.involuntary<<','<<t.tid<<','<<t.cpu<<','<<r.stage<<','
           <<k.service<<','<<k.method<<','<<k.client<<','<<k.session<<','<<k.bytes<<','<<k.crc<<'\n';
    }
    out.close();
    std::ofstream meta(buffer->path+".json");
    meta<<"{\"capacity\":"<<Buffer::capacity<<",\"rows\":"<<buffer->rows.size()
        <<",\"complete\":"<<(!buffer->rows.overflowed() && clocks && out?"true":"false")<<"}\n";
    meta.close();
    if(!out || !meta)throw std::runtime_error("SDK observation flush failed");
}
}
