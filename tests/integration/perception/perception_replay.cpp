// Text fixture replay only. This is not an IPC/wire protocol or a vehicle owner.
#include "perception_receiver.hpp"
#include <iostream>
#include <sstream>
#include <string>

int main() {
    using namespace stratadrive::central;
    PerceptionReceiver receiver;
    std::string line;
    while(std::getline(std::cin,line)) {
        std::istringstream in(line);
        char kind=0; in>>kind;
        bool accepted=false;
        std::uint64_t now=0;
        if(kind=='S') {
            std::uint32_t epoch=0;std::uint64_t clock=0;
            if(!(in>>epoch>>clock>>now)) return 2;
            accepted=receiver.start_session(epoch,clock,now);
        } else if(kind=='F') {
            PerceptionFrame f;std::string hash;
            unsigned valid=0;
            if(!(in>>now>>f.schema>>f.epoch>>f.clock_instance>>f.frame>>f.source_ns>>f.expires_ns
                 >>f.camera_id>>f.calibration_revision>>f.width>>f.height>>valid>>hash>>f.count) ||
                 hash.size()!=64 || f.count>kMaxDetections || valid>1) return 2;
            f.valid=valid!=0;
            for(std::size_t i=0;i<f.model_hash.size();++i) {
                const auto digit=[](char c)->int {
                    if(c>='0' && c<='9')return c-'0';
                    if(c>='a' && c<='f')return c-'a'+10;
                    return -1;
                };
                const int high=digit(hash[2*i]),low=digit(hash[2*i+1]);
                if(high<0 || low<0)return 2;
                f.model_hash[i]=static_cast<std::uint8_t>(high*16+low);
            }
            for(std::size_t i=0;i<f.count;++i) {
                auto& d=f.detections[i];
                if(!(in>>d.class_id>>d.score>>d.x1>>d.y1>>d.x2>>d.y2))return 2;
            }
            accepted=receiver.receive(f,now);
        } else if(kind=='P') {
            if(!(in>>now))return 2;
        } else return 2;
        std::string trailing;if(in>>trailing)return 2;
        const auto* snapshot=receiver.snapshot(now);
        std::cout<<"{\"accepted\":"<<(accepted?"true":"false")
                 <<",\"reason\":"<<static_cast<unsigned>(receiver.reason())
                 <<",\"available\":"<<(snapshot?"true":"false")
                 <<",\"count\":"<<(snapshot?snapshot->count:0)
                 <<",\"frame\":"<<(snapshot?snapshot->frame:0)
                 <<",\"source_ns\":"<<(snapshot?snapshot->source_ns:0)
                 <<",\"expires_ns\":"<<(snapshot?snapshot->expires_ns:0)<<"}\n";
    }
    return std::cin.eof()?0:2;
}
