#pragma once
#include "native_admission.hpp"
#include "wall_signal.hpp"
#include <type_traits>
#include <cstring>
namespace stratadrive::m7_native {
// Local same-build IPC ABI; wire payloads themselves remain canonical v1/P05.
// Exactly one reader/writer per channel. Three exclusive slots, no seqlock or
// concurrent payload access. Release/acquire transfers slot ownership.
template<class T> struct SharedLatest {
    static_assert(std::is_trivially_copyable<T>::value,"shared POD");
    alignas(8) std::uint64_t middle=1;
    T slots[3]{};
};
template<class T> struct SharedWriter {
    unsigned back=2;
    void publish(SharedLatest<T>& channel,const T& value) {
        channel.slots[back]=value;
        back=unsigned(__atomic_exchange_n(&channel.middle,std::uint64_t(back|4),__ATOMIC_ACQ_REL)&3);
    }
};
template<class T> struct SharedReader {
    unsigned front=0;bool have=false;
    bool read(SharedLatest<T>& channel,T& value) {
        if(__atomic_load_n(&channel.middle,__ATOMIC_ACQUIRE)&4) {
            front=unsigned(__atomic_exchange_n(&channel.middle,std::uint64_t(front),__ATOMIC_ACQ_REL)&3);have=true;
        }
        if(have)value=channel.slots[front];
        return have;
    }
};
struct SharedPacket {std::uint64_t size=0;std::uint8_t bytes[512]{};};
struct SharedProof {
    std::uint64_t observed=0,enable=0,protection_since=0;
    std::uint64_t normal=0,selected=0,service=0,credit_mask=0,release_mask=0;
    SharedPacket actual[3],commands[3],release[8],credit[7],permission;
    std::uint64_t coil_source=0,coils=0,energy_end=0;
    double total_mechanical=0,balance=0,soc=0,chemical=0,motor_loss=0,auxiliary=0,ohmic=0,capacitor=0,circuit=0;
};
struct SharedReceipt {
    std::uint64_t frame=0,begin=0,end=0,applied=0,acquired_begin=0,acquired_end=0,oldest=0,coil_source=0,coils=0,sleeping=0;
    double torque=0,dt=0,wheel_begin=0,omega[4]{},means[320]{};
};
struct WallBridge {
    WallSignal signal{}; // original terminal latch at offset zero
    std::uint64_t abi=3,bytes=sizeof(WallBridge),actor=0,model_initial=0,session=0,generation=0,stop=0,server_trip=0;
    std::uint64_t model_step=10000000;
    char run[37]{}; // canonical CARLA run UUID, including terminator
    SharedLatest<SharedProof> proof;
    SharedLatest<SharedReceipt> receipt;
};
inline bool bridge_identity(const WallBridge& b,std::uint64_t application,std::uint64_t initial,
    std::uint64_t actor,std::uint64_t model,std::uint64_t session,std::uint64_t generation,const std::string& run,std::uint64_t step=10000000) {
    return run.size()==36 && b.signal.magic==wall_signal_magic && b.signal.initial==initial &&
        b.signal.application==application && b.abi==3 && b.bytes==sizeof(b) && b.actor==actor &&
        (step==10000000 || step==5000000) && b.model_step==step &&
        b.model_initial==model && b.session==session && b.generation==generation &&
        std::memcmp(b.run,run.c_str(),37)==0 && !wall_fault(&b.signal);
}
static_assert(sizeof(std::uint64_t)==8 && sizeof(double)==8 && __atomic_always_lock_free(8,nullptr),"local IPC ABI");
inline SharedPacket shared_packet(const Packet& p) {
    SharedPacket out;if(p){out.size=p->size;std::memcpy(out.bytes,p->bytes.data(),p->size);}return out;
}
inline bool restore(const SharedPacket& in,Packet& out) {
    if(in.size>512)return false;
    if(!in.size){out.reset();return true;}
    remote::OwnerPacket p;p.size=in.size;std::memcpy(p.bytes.data(),in.bytes,in.size);out=p;return true;
}
inline bool restore(const SharedProof& s,Input& out) {
    if(s.normal>1 || s.selected>255 || s.service>255 || s.credit_mask>255 || s.release_mask>255 || s.coils>15)return false;
    out.observed=s.observed;out.enable=s.enable;out.protection_since=s.protection_since;out.normal=s.normal;
    out.protection_selected_mask=s.selected;out.service_mask=s.service;out.credit_mask=s.credit_mask;out.release_mask=s.release_mask;
    for(unsigned i=0;i<3;++i)if(!restore(s.actual[i],out.actual[i]) || !restore(s.commands[i],out.commands[i]))return false;
    for(unsigned i=0;i<8;++i)if(!restore(s.release[i],out.release[i]))return false;
    for(unsigned i=0;i<7;++i)if(!restore(s.credit[i],out.credit[i]))return false;
    return restore(s.permission,out.permission);
}
}
