#include "m4_execution_watch.hpp"
#include <stdexcept>

namespace stratadrive::simulation {
M4ExecutionWatch::Guard::Guard(runtime::TaskScheduleConfig config):schedule(config),monitor(schedule),rows(config.jobs) {}
M4ExecutionWatch::M4ExecutionWatch(std::uint64_t enable,std::uint64_t stop) {
    if(stop<enable || stop-enable<20000000) throw std::invalid_argument("M4 guard window requires 20ms tail");
    const runtime::TaskScheduleConfig config{enable,2000000,4000000,static_cast<std::size_t>((stop-enable-20000000)/2000000+1)};
    for(std::size_t i=0;i<guards_.size();++i) {
        guards_[i]=std::make_unique<Guard>(config);
        for(std::size_t j=0;j<config.jobs;++j) guards_[i]->rows[j]={i,j,guards_[i]->schedule.release(j),guards_[i]->schedule.deadline(j),0,0,0,0};
    }
}
std::optional<std::size_t> M4ExecutionWatch::begin(std::size_t owner,std::uint64_t now,bool executing) {
    auto& g=*guards_.at(owner); const auto next=g.schedule.newest_released(now,g.next);
    if(!next) return std::nullopt;
    g.next=*next+1;
    if(!executing) return std::nullopt; // missed opportunity remains an unfinished slot
    g.rows[*next].start_ns=now; return next;
}
void M4ExecutionWatch::finish(std::size_t owner,std::optional<std::size_t> job,std::uint64_t end,std::uint64_t cpu) {
    if(!job) return;
    auto& g=*guards_.at(owner); g.rows[*job].end_ns=end; g.rows[*job].cpu_ns=cpu;
    if(!g.monitor.finish(*job,end)) throw std::logic_error("duplicate M4 guard completion");
}
std::array<std::optional<M4ExecutionFault>,10> M4ExecutionWatch::poll(std::size_t observer,std::uint64_t now) {
    std::array<std::optional<M4ExecutionFault>,10> found{};
    const auto first=observer==9?0U:9U,end=observer==9?9U:10U;
    if(observer!=8 && observer!=9) return found;
    for(auto i=first;i<end;++i) {
        auto& g=*guards_[i]; g.monitor.poll(now);
        if(!g.reported) { if(const auto f=g.monitor.first_fault()) { found[i]=M4ExecutionFault{i,*f}; g.reported=true; } }
    }
    return found;
}
std::vector<M4ExecutionRow> M4ExecutionWatch::rows() const {
    std::vector<M4ExecutionRow> rows;
    for(const auto& guard:guards_) for(auto row:guard->rows) { row.detected_ns=guard->monitor.detected(row.slot); rows.push_back(row); }
    return rows;
}
} // namespace stratadrive::simulation
