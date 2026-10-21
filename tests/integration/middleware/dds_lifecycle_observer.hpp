#pragma once
#include "dds_probe_qos.h"
#include <array>
#include <cassert>
#include <filesystem>
#include <fstream>
#include <sched.h>
#include <sys/resource.h>

namespace lifecycle_observer {
inline void qos(dds_entity_t entity, const std::string& path) {
    probe_qos_readback v{};
    const bool read=probe_read_qos(entity,&v), matches=read && probe_qos_matches(&v);
    std::ofstream out(path);
    out<<"read,matches,history,depth,reliability,blocking_ns,durability,samples,instances,per_instance\n"
       <<read<<','<<matches<<','<<v.history<<','<<v.depth<<','<<v.reliability<<','<<v.blocking<<','
       <<v.durability<<','<<v.samples<<','<<v.instances<<','<<v.per_instance<<'\n';
    out.close();assert(out && matches);
}
inline void threads(const std::string& prefix) {
    std::ofstream out(prefix+".threads.csv"), raw(prefix+".threads.raw");
    out<<"tid,name,policy,priority,nice,affinity\n";
    for(const auto& entry:std::filesystem::directory_iterator("/proc/self/task")) {
        const auto tid=std::stoi(entry.path().filename());
        std::ifstream name_file(entry.path()/"comm"),status(entry.path()/"status"),stat(entry.path()/"stat");
        std::string name;std::getline(name_file,name);
        sched_param parameter{};cpu_set_t mask;CPU_ZERO(&mask);
        const auto policy=sched_getscheduler(tid);
        if(policy<0 || sched_getparam(tid,&parameter) || sched_getaffinity(tid,sizeof(mask),&mask))continue;
        out<<tid<<','<<name<<','<<policy<<','<<parameter.sched_priority<<','<<getpriority(PRIO_PROCESS,tid)<<',';
        for(int cpu=0;cpu<CPU_SETSIZE;++cpu)if(CPU_ISSET(cpu,&mask))out<<cpu<<';';
        out<<'\n';raw<<"TASK "<<tid<<'\n'<<status.rdbuf()<<'\n'<<stat.rdbuf()<<'\n';
    }
    assert(out && raw);
}
struct ReaderStatus {
    dds_sample_rejected_status_t rejected{};
    dds_sample_lost_status_t lost{};
    void read(dds_entity_t reader,const std::string& path) {
        const auto a=dds_get_sample_rejected_status(reader,&rejected);
        const auto b=dds_get_sample_lost_status(reader,&lost);
        std::ofstream out(path);
        out<<"rejected_rc,lost_rc,rejected_total,lost_total,last_reason\n"
           <<a<<','<<b<<','<<rejected.total_count<<','<<lost.total_count<<','<<rejected.last_reason<<'\n';
        out.close();assert(out && a==0 && b==0);
    }
};
struct Event {
    std::uint64_t time,epoch,token,source,deadline,expiry;
    const char* kind;bool accepted;
};
struct Events {
    std::array<Event,2048> records{};unsigned size=0;
    void add(Event event) {assert(size<records.size());records[size++]=event;}
    static void write(std::ostream& out,const Event& e) {
        out<<e.time<<','<<e.kind<<','<<e.epoch<<','<<e.token<<','<<e.source<<','<<e.deadline<<','<<e.expiry<<','<<e.accepted<<'\n';
    }
    void save(std::ostream& out) {for(unsigned i=0;i<size;++i)write(out,records[i]);out.flush();assert(out);}
};
} // namespace lifecycle_observer
