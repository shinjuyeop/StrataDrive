#pragma once
// Diagnostic observer only. Fixed storage, original libc allocation behavior,
// relaxed observation index, no SDK annotations or replacement synchronization.
#include <dds/ddsrt/heap.h>
#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <sys/syscall.h>
#include <unistd.h>
#include <unwind.h>
namespace allocation_trace {
struct Record {std::uint64_t ns,tid;std::uintptr_t pointer,previous;std::size_t size;char kind;std::uintptr_t stack[9];};
inline Record records[65536]{};
inline std::atomic<unsigned> count{0};
inline thread_local bool tracing=false;
inline std::uint64_t now() {timespec t{};clock_gettime(CLOCK_MONOTONIC,&t);return std::uint64_t(t.tv_sec)*1000000000+t.tv_nsec;}
struct Cursor {Record* record;unsigned pos;};
inline _Unwind_Reason_Code unwind(_Unwind_Context* context,void* arg) {
    auto& cursor=*static_cast<Cursor*>(arg);
    if(cursor.pos==9)return _URC_END_OF_STACK;
    cursor.record->stack[cursor.pos++]=_Unwind_GetIP(context);return _URC_NO_REASON;
}
inline void record(char kind,void* pointer,void* previous,std::size_t size) {
    if(tracing)return;
    tracing=true;const unsigned i=count.fetch_add(1,std::memory_order_relaxed);
    if(i<65536){auto& r=records[i];r.ns=now();r.tid=syscall(SYS_gettid);r.pointer=reinterpret_cast<std::uintptr_t>(pointer);r.previous=reinterpret_cast<std::uintptr_t>(previous);r.size=size;r.kind=kind;Cursor c{&r,0};_Unwind_Backtrace(unwind,&c);}
    tracing=false;
}
inline void* allocate(std::size_t n){void* p=std::malloc(n);record('M',p,nullptr,n);return p;}
inline void* zero(std::size_t n,std::size_t size){void* p=std::calloc(n,size);record('C',p,nullptr,n*size);return p;}
inline void* resize(void* p,std::size_t n){record('R',p,nullptr,n);void* q=std::realloc(p,n);record('N',q,nullptr,n);return q;}
inline void release(void* p){record('F',p,nullptr,0);std::free(p);}
inline void install(){ddsrt_set_allocator({allocate,zero,resize,release});}
inline bool save(const std::string& path) {
    std::ofstream out(path);out<<"index,time_ns,tid,event,pointer,size,stack\n";
    const unsigned n=count.load(std::memory_order_relaxed);
    for(unsigned i=0;i<n && i<65536;++i){const auto& r=records[i];out<<i<<','<<r.ns<<','<<r.tid<<','<<r.kind<<",0x"<<std::hex<<r.pointer<<std::dec<<','<<r.size<<',';for(auto ip:r.stack)out<<"0x"<<std::hex<<ip<<';';out<<std::dec<<'\n';}
    return bool(out) && n<=65536;
}
}
