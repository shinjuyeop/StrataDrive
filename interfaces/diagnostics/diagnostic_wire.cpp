#include "diagnostic_wire.hpp"
#include <algorithm>
#include <array>
#include <stdexcept>

namespace stratadrive::diagnostics::wire {
namespace {
constexpr std::array<std::uint8_t,8> magic{'S','D','D','W','I','R',1,0};
constexpr std::size_t header=36;
std::uint32_t crc(const Bytes& bytes,std::size_t count) {
    std::uint32_t c=0xffffffff;
    for(std::size_t i=0;i<count;++i) {
        c^=bytes[i]; for(unsigned bit=0;bit<8;++bit) c=(c>>1)^((c&1)?0xedb88320U:0U);
    }
    return ~c;
}
void put(Bytes& b,std::uint64_t value,unsigned width) {
    for(unsigned i=0;i<width;++i) b.push_back(static_cast<std::uint8_t>(value>>(8*i)));
}
std::uint64_t get(const Bytes& b,std::size_t offset,unsigned width) {
    if(width>8 || offset>b.size() || width>b.size()-offset) throw std::invalid_argument("diagnostic wire bounds");
    std::uint64_t value=0; for(unsigned i=0;i<width;++i) value|=static_cast<std::uint64_t>(b[offset+i])<<(8*i);
    return value;
}
void context(std::uint64_t stream,std::uint64_t sequence,std::uint32_t registry) {
    if(!stream || !sequence || registry<1 || registry>4) throw std::invalid_argument("diagnostic wire context");
}
void dictionary(const Event& e,std::uint32_t registry) {
    const auto revision=code_registry_revision(e.key.code);
    if(e.schema!=1 || e.kind>Kind::Attempt || !revision || revision>registry || (e.kind==Kind::Attempt && registry<3))
        throw std::invalid_argument("diagnostic wire dictionary");
}
}
std::uint32_t event_crc(const Event& e) { const auto bytes=diagnostics::encode(e); return crc(bytes,bytes.size()); }
Bytes encode(const Message& message) {
    Bytes payload; std::uint64_t stream=0,sequence=0; std::uint32_t registry=0; std::uint8_t kind=0;
    if(const auto* d=std::get_if<Data>(&message)) {
        kind=1; stream=d->stream; sequence=d->sequence; registry=d->registry; dictionary(d->event,registry); payload=diagnostics::encode(d->event);
    } else {
        const auto& a=std::get<Ack>(message); kind=2; stream=a.stream; sequence=a.sequence; registry=a.registry; put(payload,a.event_crc,4);
    }
    context(stream,sequence,registry);
    if(payload.size()>kMaxPacket-header-4) throw std::invalid_argument("diagnostic wire payload");
    Bytes b(magic.begin(),magic.end()); put(b,kind,1); put(b,0,3); put(b,registry,4); put(b,stream,8); put(b,sequence,8); put(b,payload.size(),4);
    b.insert(b.end(),payload.begin(),payload.end()); put(b,crc(b,b.size()),4); return b;
}
Message decode(const Bytes& b) {
    if(b.size()<header+4 || b.size()>kMaxPacket || !std::equal(magic.begin(),magic.end(),b.begin()) ||
       get(b,9,3)!=0 || get(b,32,4)!=b.size()-header-4 || get(b,b.size()-4,4)!=crc(b,b.size()-4))
        throw std::invalid_argument("diagnostic wire frame");
    const auto registry=static_cast<std::uint32_t>(get(b,12,4)); const auto stream=get(b,16,8),sequence=get(b,24,8);
    context(stream,sequence,registry);
    if(b[8]==2 && b.size()==header+8) return Ack{stream,sequence,registry,static_cast<std::uint32_t>(get(b,header,4))};
    if(b[8]!=1 || b.size()==header+4 || b[header]!=0) throw std::invalid_argument("diagnostic wire kind/length");
    const auto entry=diagnostics::decode(Bytes(b.begin()+header,b.end()-4));
    const auto* event=std::get_if<Event>(&entry); if(!event) throw std::invalid_argument("diagnostic wire event only");
    dictionary(*event,registry); return Data{stream,sequence,registry,*event};
}
} // namespace stratadrive::diagnostics::wire
