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
    explicit SolverJournal(std::size_t capacity=Capacity)
        :capacity_(capacity && capacity<=Capacity?capacity:0),
         entries_(capacity_?new Entry[capacity_]{}:nullptr),failed_(!capacity_) {}
    bool full() const {return size_==capacity_;}
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
        std::size_t first=0,last=size_;
        while(first<last) {const auto mid=first+(last-first)/2;
            if(entries_[mid].ticket<ticket)first=mid+1;else last=mid;}
        if(first<size_ && entries_[first].ticket==ticket)return &entries_[first];
        return nullptr;
    }
private:
    const std::size_t capacity_;
    std::unique_ptr<Entry[]> entries_;
    std::size_t size_=0;bool failed_=false;
};
}}
