#pragma once
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

namespace stratadrive::someip {
inline constexpr std::uint16_t kService=0x5344,kInstance=1,kReady=0x10,kWork=0x20,kStatus=0x30;
inline constexpr std::array<std::uint8_t,4> kProbe{0x53,0x44,0,1};
inline bool probe(const std::uint8_t* p,std::size_t n) {
    return n==kProbe.size() && std::equal(kProbe.begin(),kProbe.end(),p);
}
// Numeric values are the SOME/IP wire message types, not an SDK enum ABI.
inline bool header(bool server,std::uint16_t service,std::uint16_t instance,
                   std::uint16_t method,std::uint8_t type,std::uint8_t version) {
    return service==kService && instance==kInstance && version==1 &&
        type==(server?0x00:0x80) && (method==kReady || method==kWork || method==kStatus);
}
inline bool payload(bool server,std::uint16_t method,const std::uint8_t* p,std::size_t n) {
    if(method==kReady || (server && method==kStatus)) return probe(p,n);
    // Work canonical decoding/route/type checks follow on the owner thread.
    // An empty work response is a protocol rejection, never an accepted result.
    return n<=512 && (n>0 || !server);
}
struct ProbeV2 {std::uint8_t kind,origin,lane;std::uint64_t nonce;};
inline std::array<std::uint8_t,16> probe_v2(ProbeV2 v) {
    std::array<std::uint8_t,16> b{0x53,0x44,0,2,v.kind,v.origin,v.lane,0};
    for(unsigned i=0;i<8;++i)b[8+i]=static_cast<std::uint8_t>(v.nonce>>(i*8));
    return b;
}
inline std::optional<ProbeV2> decode_probe_v2(const std::uint8_t* p,std::size_t n) {
    if(n!=16 || p[0]!=0x53 || p[1]!=0x44 || p[2]!=0 || p[3]!=2 ||
       (p[4]!=1 && p[4]!=2) || p[5]>1 || p[6]>1 || p[7]!=0)return {};
    std::uint64_t nonce=0;for(unsigned i=0;i<8;++i)nonce|=std::uint64_t(p[8+i])<<(8*i);
    if(!nonce)return {};
    return ProbeV2{p[4],p[5],p[6],nonce};
}

}
