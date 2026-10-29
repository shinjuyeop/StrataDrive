#pragma once
#include "M7SolverTrace.h"
#include <cstddef>
#include <cstdint>
#include <memory>
namespace stratadrive { namespace m7_native {
// Single game-thread owner. Allocated at bind, bounded and never overwritten.
// Raw solver evidence survives observer reuse; serialization is a later query.
template<std::size_t Capacity> class SolverJournal {
public:
    struct Entry {std::uint64_t frame=0,ticket=0;M7SolverTrace trace{};};
    SolverJournal():entries_(new Entry[Capacity]{}) {}
    bool full() const {return size_==Capacity;}
    bool failed() const {return failed_;}
    std::size_t size() const {return size_;}
    bool append(std::uint64_t frame,std::uint64_t ticket,const M7SolverTrace& trace) {
        if(failed_ || full() || !frame || !ticket || trace.abi!=2 || trace.count>320 ||
           (size_ && (frame!=entries_[size_-1].frame+1 || ticket<=entries_[size_-1].ticket))) {
            failed_=true;return false;
        }
        entries_[size_++]={frame,ticket,trace};return true;
    }
    const Entry* find(std::uint64_t ticket) const {
        for(std::size_t i=0;i<size_;++i)if(entries_[i].ticket==ticket)return &entries_[i];
        return nullptr;
    }
private:
    std::unique_ptr<Entry[]> entries_;
    std::size_t size_=0;bool failed_=false;
};
}}
