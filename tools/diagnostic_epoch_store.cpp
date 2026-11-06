#include "epoch_recorder.hpp"
#include <iostream>
#include <stdexcept>
#include <string>

namespace d=stratadrive::diagnostics;
namespace {
void status(const d::EpochRecorder& store) {
    std::cout<<"{\"segment\":"<<store.segment()<<",\"watermark\":"<<store.watermark()
        <<",\"complete\":"<<(store.ledger().complete()?"true":"false")<<",\"records\":[";
    bool first=true;
    for(const auto& r:store.ledger().records()) {
        if(!first)std::cout<<',';
        first=false;
        std::cout<<"{\"code\":"<<static_cast<unsigned>(r.key.code)<<",\"component\":"<<r.key.component
            <<",\"monitor\":"<<r.key.monitor<<",\"subject\":"<<r.key.subject
            <<",\"generation\":"<<r.generation<<",\"revision\":"<<r.revision<<",\"count\":"<<r.count
            <<",\"condition\":"<<static_cast<unsigned>(r.condition)<<",\"cleared\":"<<(r.cleared?"true":"false")<<'}';
    }
    std::cout<<"]}\n";
}
}
int main(int argc,char** argv) {
    try {
        if(argc<3)throw std::invalid_argument("usage: diagnostic_epoch_store init ROOT STORE_ID | append ROOT | inspect ROOT");
        const std::string command=argv[1];
        if(command=="init") {
            if(argc!=4)throw std::invalid_argument("init requires explicit store identity");
            const std::string value=argv[3];
            if(value.empty() || value.find_first_not_of("0123456789")!=std::string::npos)throw std::invalid_argument("store identity");
            std::size_t used=0;const auto id=std::stoull(value,&used);
            if(used!=value.size())throw std::invalid_argument("store identity");
            d::EpochRecorder::initialize(argv[2],id);d::EpochRecorder store(argv[2]);status(store);return 0;
        }
        if(argc!=3 || (command!="append" && command!="inspect"))throw std::invalid_argument("unknown command/arguments");
        d::EpochRecorder store(argv[2]);
        if(command=="append") {
            std::string line;
            while(std::getline(std::cin,line)) {
                if(line.empty() || line.size()>524288 || line.size()%2 || line.find_first_not_of("0123456789abcdef")!=std::string::npos)
                    throw std::invalid_argument("canonical lower-case hex entry required");
                std::vector<std::uint8_t> bytes;bytes.reserve(line.size()/2);
                for(std::size_t i=0;i<line.size();i+=2)bytes.push_back(static_cast<std::uint8_t>(std::stoul(line.substr(i,2),nullptr,16)));
                const auto entry=d::decode(bytes);if(d::encode(entry)!=bytes)throw std::invalid_argument("noncanonical diagnostic entry");
                d::Receipt receipt{};
                if(const auto* event=std::get_if<d::Event>(&entry))receipt=store.record(*event);
                else if(const auto* clear=std::get_if<d::Clear>(&entry))receipt=store.clear(*clear);
                else receipt=store.review(std::get<d::ContinuityReview>(entry));
                std::cout<<"{\"result\":"<<static_cast<unsigned>(receipt.result)<<",\"durable\":"<<(receipt.durable?"true":"false")
                    <<",\"watermark\":"<<receipt.watermark<<"}"<<std::endl;
                if(!receipt.durable)return 1;
            }
            if(!std::cin.eof())throw std::runtime_error("diagnostic input failed");
        }
        status(store);return store.ledger().complete()?0:1;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
