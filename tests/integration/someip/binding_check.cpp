// Standalone contract regression: no SDK, network, build/ or gtest dependency.
#include "binding.hpp"
#include <stdexcept>
#include <iostream>
using namespace stratadrive::someip;
void demand(bool b){if(!b)throw std::runtime_error("SOME/IP binding assertion");}
int main(){
    unsigned checks=0;
    for(bool server:{false,true})for(unsigned method:{0x10,0x20,0x30}) {
        demand(header(server,kService,kInstance,method,server?0:0x80,1));++checks;
        for(unsigned bad:{1,2,0x81,0xff}){demand(!header(server,kService,kInstance,method,bad,1));++checks;}
        demand(!header(server,kService,kInstance,method,server?0x80:0,1));++checks;
        for(unsigned version:{0,2,0xff}){demand(!header(server,kService,kInstance,method,server?0:0x80,version));++checks;}
        demand(!header(server,kService+1,kInstance,method,server?0:0x80,1));++checks;
        demand(!header(server,kService,kInstance+1,method,server?0:0x80,1));++checks;
    }
    for(unsigned m:{0,0x11,0x21,0x31,0x40,0xffff}){demand(!header(true,kService,kInstance,m,0,1));++checks;}
    demand(probe(kProbe.data(),kProbe.size()));++checks;
    for(unsigned i=0;i<4;++i)for(unsigned value=0;value<256;++value)if(value!=kProbe[i]) {
        auto b=kProbe;b[i]=value;demand(!probe(b.data(),b.size()));
        demand(!payload(true,kReady,b.data(),b.size()));demand(!payload(false,kReady,b.data(),b.size()));
        demand(!payload(true,kStatus,b.data(),b.size()));checks+=4;
    }
    std::array<unsigned char,513> b{};std::copy(kProbe.begin(),kProbe.end(),b.begin());
    for(unsigned n:{0,1,2,3,5,512,513}){demand(!probe(b.data(),n));++checks;}
    demand(!payload(true,kWork,b.data(),0));demand(!payload(true,kWork,b.data(),513));checks+=2;
    for(unsigned kind:{1,2})for(unsigned origin:{0,1})for(unsigned lane:{0,1}) {
        const auto p=probe_v2({static_cast<std::uint8_t>(kind),static_cast<std::uint8_t>(origin),static_cast<std::uint8_t>(lane),0x123456789abcdef0ULL});
        const auto q=decode_probe_v2(p.data(),p.size());demand(q && q->kind==kind && q->origin==origin && q->lane==lane && q->nonce==0x123456789abcdef0ULL);++checks;
        for(unsigned i=0;i<4;++i){auto b=p;b[i]^=1;demand(!decode_probe_v2(b.data(),b.size()));++checks;}
        for(unsigned i:{5,6,7}){auto b=p;b[i]=2;demand(!decode_probe_v2(b.data(),b.size()));++checks;}
        auto b=p;b[4]=0;demand(!decode_probe_v2(b.data(),b.size()));++checks;
        for(unsigned n:{0,4,15,17}){demand(!decode_probe_v2(p.data(),n));++checks;}
        b=p;for(unsigned i=8;i<16;++i)b[i]=0;demand(!decode_probe_v2(b.data(),b.size()));++checks;
    }
    std::cout<<checks<<" binding assertions passed\n";
}
