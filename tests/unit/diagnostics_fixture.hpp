#pragma once
#include "diagnostics.hpp"

namespace diagnostics_fixture {
using namespace stratadrive::diagnostics;
inline Stamp stamp(std::uint64_t ns=1000000000) { return {Domain::Simulation,7,ns,true,true}; }
inline Event session(std::uint64_t sequence=1,std::uint32_t epoch=1) {
    Event e; e.id={10,20,sequence}; e.session={10,epoch}; e.kind=Kind::Session; e.session_enable=stamp(); return e;
}
inline Event fault(std::uint64_t sequence=2,Code code=Code::SpeedInput,std::uint32_t epoch=1) {
    auto e=session(sequence,epoch); e.kind=Kind::Fault; e.key={code,1,2,3}; e.native_reason=1; e.latch=Latch::Set;
    e.occurrence={10,20,epoch,2,sequence}; e.times[static_cast<std::size_t>(Time::Detected)]=stamp(1000000000+sequence); return e;
}
inline Event proof(const Event& fault,std::uint64_t sequence=3,Proof kind=Proof::Input,std::uint32_t epoch=1) {
    auto e=fault; e.id.sequence=sequence; e.session.epoch=epoch; e.kind=Kind::Actual; e.proof=kind; return e;
}
inline Event passed(const Event& evidence,std::uint64_t sequence=4) {
    auto e=evidence; e.id.sequence=sequence; e.kind=Kind::Passed; e.proof_event=evidence.id; return e;
}
inline Clear clear(const Record& r,std::uint64_t sequence=1,std::uint32_t epoch=1) {
    Clear c; c.id={10,99,sequence}; c.session={10,epoch}; c.targets.push_back({r.key,r.revision});
    c.evidence={stamp(1010000000),stamp(),stamp(1010000000),stamp(1010000000),stamp(1010000000),0,0,100000,true,true}; return c;
}
class MemoryJournal : public Journal {
public:
    Limits config{}; bool healthy{true}, fail{false}; std::vector<Entry> entries;
    Limits limits() const noexcept override { return config; }
    const std::vector<Entry>& committed() const noexcept override { return entries; }
    bool writable() const noexcept override { return healthy; }
    void invalidate() noexcept override { healthy=false; }
    bool append(const Entry& e) override {
        if(fail || !healthy) { healthy=false; return false; }
        entries.push_back(e); return true;
    }
};
} // namespace diagnostics_fixture
