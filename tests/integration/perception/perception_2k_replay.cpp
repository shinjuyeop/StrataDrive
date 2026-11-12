// Strict, finite text fixture adapter; not a network or production control loop.
#include "perception_2k_receiver.hpp"
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>

namespace {
bool hash_bytes(const std::string& hash,std::array<std::uint8_t,32>& out) {
    if(hash.size()!=64)return false;
    const auto digit=[](char c)->int {
        if(c>='0' && c<='9')return c-'0';
        if(c>='a' && c<='f')return c-'a'+10;
        return -1;
    };
    for(std::size_t i=0;i<out.size();++i) {
        const auto high=digit(hash[2*i]),low=digit(hash[2*i+1]);
        if(high<0 || low<0)return false;
        out[i]=static_cast<std::uint8_t>(high*16+low);
    }
    return true;
}
}
int main() {
    using namespace stratadrive::central;
    Native2kReceiver receiver;
    std::string line;
    std::cout<<std::setprecision(17);
    while(std::getline(std::cin,line)) {
        if(line.size()>100000)return 2;
        // Stream extraction to an unsigned type otherwise accepts negative text.
        std::istringstream tokens(line);std::string token;
        while(tokens>>token) if(!token.empty() && token.front()=='-')return 2;
        std::istringstream in(line);char kind=0;in>>kind;
        bool accepted=false;Native2kNow now{};
        if(kind=='S') {
            Native2kSession s;
            if(!(in>>s.epoch>>s.source_clock>>s.wall_clock>>s.source_enable_ns>>s.wall_enable_ns))return 2;
            accepted=receiver.start_session(s);
            // Rejected INIT must not mutate the receiver by polling a new domain.
            std::string trailing;if(in>>trailing)return 2;
            std::cout<<"{\"accepted\":"<<(accepted?"true":"false")<<",\"session\":true}\n";
            continue;
        }
        if(!(in>>now.source_ns>>now.wall_ns>>now.state_received_wall_ns))return 2;
        if(kind=='F') {
            Native2kFrame f;std::string hash;unsigned valid=0;
            if(!(in>>f.schema>>f.candidate>>f.epoch>>f.source_clock>>f.wall_clock>>f.frame>>f.source_ns>>f.expires_ns
                 >>f.received_wall_ns>>f.wall_expires_ns>>f.camera_id>>f.calibration_revision>>f.width>>f.height
                 >>valid>>hash>>f.count) || valid>1 || f.count>kMaxDetections || !hash_bytes(hash,f.model_hash))return 2;
            f.valid=valid==1;
            for(std::size_t i=0;i<f.count;++i) {
                auto& d=f.detections[i];
                if(!(in>>d.class_id>>d.score>>d.x1>>d.y1>>d.x2>>d.y2))return 2;
            }
            accepted=receiver.receive(f,now);
        } else if(kind=='U')receiver.unavailable(now);
        else if(kind!='P')return 2;
        std::string trailing;if(in>>trailing)return 2;
        const auto* f=receiver.snapshot(now);
        std::cout<<"{\"accepted\":"<<(accepted?"true":"false")
            <<",\"reason\":"<<static_cast<unsigned>(receiver.reason())
            <<",\"available\":"<<(f?"true":"false")<<",\"frame\":"<<(f?f->frame:0)
            <<",\"source_ns\":"<<(f?f->source_ns:0)<<",\"expires_ns\":"<<(f?f->expires_ns:0)
            <<",\"received_wall_ns\":"<<(f?f->received_wall_ns:0)<<",\"wall_expires_ns\":"<<(f?f->wall_expires_ns:0)
            <<",\"tracks\":[";
        const auto& tracks=receiver.tracks();
        for(std::size_t i=0;i<tracks.count;++i) {
            if(i)std::cout<<',';
            const auto& t=tracks.tracks[i];
            std::cout<<"{\"id\":"<<t.id<<",\"history\":[";
            for(std::size_t j=0;j<t.count;++j) {
                if(j)std::cout<<',';
                const auto& o=t.history[j];const auto& d=o.detection;
                std::cout<<"{\"frame\":"<<o.frame<<",\"source_ns\":"<<o.source_ns<<",\"class_id\":"<<d.class_id
                    <<",\"score\":"<<d.score<<",\"box\":["<<d.x1<<','<<d.y1<<','<<d.x2<<','<<d.y2<<"]}";
            }
            std::cout<<"]}";
        }
        std::cout<<"]}\n";
    }
    return std::cin.eof()?0:2;
}
