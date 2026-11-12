#include "perception_2k_ipc.hpp"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <stdexcept>
#include <sys/socket.h>
#include <unistd.h>

namespace stratadrive::central {
namespace {
constexpr std::array<std::uint8_t,8> magic{'S','2','K','P','I','P','C','1'};
struct Reader {
    const std::uint8_t* p;
    std::uint64_t u64() { std::uint64_t v=0;for(unsigned i=0;i<8;++i)v|=std::uint64_t(*p++)<<(8*i);return v; }
    std::uint32_t u32() { std::uint32_t v=0;for(unsigned i=0;i<4;++i)v|=std::uint32_t(*p++)<<(8*i);return v; }
    double real() {const auto bits=u64();double v;std::memcpy(&v,&bits,8);return v;}
};
struct Writer {
    std::uint8_t* p;
    void u64(std::uint64_t v) {for(unsigned i=0;i<8;++i){*p++=std::uint8_t(v);v>>=8;}}
    void u32(std::uint32_t v) {for(unsigned i=0;i<4;++i){*p++=std::uint8_t(v);v>>=8;}}
    void real(double v) {std::uint64_t bits;std::memcpy(&bits,&v,8);u64(bits);}
};
static_assert(sizeof(double)==8 && std::numeric_limits<double>::is_iec559,"binary64 Host IPC");
}
bool decode_perception_ipc(const std::uint8_t* bytes,std::size_t size,PerceptionIpcMessage& result) noexcept {
    if(!bytes || size<kPerceptionIpcHeader || size>kPerceptionIpcMax || std::memcmp(bytes,magic.data(),magic.size()))return false;
    Reader r{bytes+8};PerceptionIpcMessage m;
    if(r.u32()!=1)return false;
    const auto kind=r.u32();if(kind>2)return false;m.kind=static_cast<PerceptionIpcKind>(kind);
    m.sequence=r.u64();m.epoch=r.u32();if(r.u32()!=0)return false;
    m.source_clock=r.u64();m.wall_clock=r.u64();m.sender_wall_ns=r.u64();
    m.state_frame=r.u64();m.observed.source_ns=r.u64();m.observed.state_received_wall_ns=r.u64();
    if(!m.sequence || !m.epoch || !m.source_clock || !m.wall_clock)return false;
    if(!m.state_frame && (m.observed.source_ns || m.observed.state_received_wall_ns || kind!=0))return false;
    if(kind!=2) {if(size!=kPerceptionIpcHeader)return false;result=m;return true;}
    if(size<kPerceptionIpcResult)return false;
    auto& f=m.result;f.epoch=m.epoch;f.source_clock=m.source_clock;f.wall_clock=m.wall_clock;
    f.schema=r.u32();f.candidate=r.u32();f.frame=r.u64();f.source_ns=r.u64();f.expires_ns=r.u64();
    f.received_wall_ns=r.u64();f.wall_expires_ns=r.u64();
    f.camera_id=r.u32();f.calibration_revision=r.u32();f.width=r.u32();f.height=r.u32();
    const auto valid=r.u32();if(valid>1)return false;f.valid=valid==1;f.count=r.u32();
    if(f.count>kMaxDetections || size!=kPerceptionIpcResult+48*f.count)return false;
    std::memcpy(f.model_hash.data(),r.p,32);r.p+=32;
    for(std::size_t i=0;i<f.count;++i) {
        auto& d=f.detections[i];d.class_id=r.u32();if(r.u32()!=0)return false;
        d.score=r.real();d.x1=r.real();d.y1=r.real();d.x2=r.real();d.y2=r.real();
    }
    result=m;return true;
}
std::size_t encode_perception_ipc(const PerceptionIpcMessage& m,std::array<std::uint8_t,kPerceptionIpcMax>& bytes) noexcept {
    if(static_cast<unsigned>(m.kind)>2 || m.result.count>kMaxDetections)return 0;
    std::memcpy(bytes.data(),magic.data(),magic.size());Writer w{bytes.data()+8};
    w.u32(1);w.u32(static_cast<std::uint32_t>(m.kind));w.u64(m.sequence);w.u32(m.epoch);w.u32(0);
    w.u64(m.source_clock);w.u64(m.wall_clock);w.u64(m.sender_wall_ns);w.u64(m.state_frame);
    w.u64(m.observed.source_ns);w.u64(m.observed.state_received_wall_ns);
    if(m.kind!=PerceptionIpcKind::Result)return kPerceptionIpcHeader;
    const auto& f=m.result;w.u32(f.schema);w.u32(f.candidate);w.u64(f.frame);w.u64(f.source_ns);w.u64(f.expires_ns);
    w.u64(f.received_wall_ns);w.u64(f.wall_expires_ns);w.u32(f.camera_id);w.u32(f.calibration_revision);
    w.u32(f.width);w.u32(f.height);w.u32(f.valid?1:0);w.u32(static_cast<std::uint32_t>(f.count));
    std::memcpy(w.p,f.model_hash.data(),32);w.p+=32;
    for(std::size_t i=0;i<f.count;++i) {
        const auto& d=f.detections[i];w.u32(d.class_id);w.u32(0);w.real(d.score);w.real(d.x1);w.real(d.y1);w.real(d.x2);w.real(d.y2);
    }
    return kPerceptionIpcResult+48*f.count;
}
PerceptionIpcShadow::PerceptionIpcShadow(int fd,std::uint32_t epoch,std::uint64_t source,std::uint64_t wall)
    : fd_(fd),epoch_(epoch),source_clock_(source),wall_clock_(wall) {
    int type=0; socklen_t length=sizeof(type);ucred peer{};socklen_t peer_size=sizeof(peer);
    if(fd<3 || !epoch || !source || !wall || getsockopt(fd,SOL_SOCKET,SO_TYPE,&type,&length) || type!=SOCK_SEQPACKET ||
       getsockopt(fd,SOL_SOCKET,SO_PEERCRED,&peer,&peer_size) || peer.uid!=getuid())throw std::invalid_argument("private same-uid seqpacket descriptor required");
    const auto flags=fcntl(fd,F_GETFL,0);
    if(flags<0 || !(flags&O_NONBLOCK))throw std::invalid_argument("nonblocking inherited descriptor required");
}
PerceptionIpcShadow::~PerceptionIpcShadow() {close(fd_);}
bool PerceptionIpcShadow::observe_native_init(std::uint32_t epoch,std::uint64_t enable) noexcept {
    if(epoch!=epoch_ || !enable || (root_enable_ && root_enable_!=enable)) {view_.state_fault=true;return false;}
    root_enable_=enable;return true;
}
void PerceptionIpcShadow::clear_current(std::uint64_t wall) noexcept {
    if(view_.initialized)receiver_.unavailable({view_.state_source_ns,wall,view_.state_received_wall_ns});
}
void PerceptionIpcShadow::reject(PerceptionIpcFault fault,std::uint64_t wall) noexcept {
    ++view_.rejected;view_.transport_fault=fault;clear_current(wall);
}
void PerceptionIpcShadow::consume(const PerceptionIpcMessage& m,std::uint64_t wall) noexcept {
    if(m.epoch!=epoch_ || m.source_clock!=source_clock_ || m.wall_clock!=wall_clock_) {reject(PerceptionIpcFault::Identity,wall);return;}
    if(m.sequence<=view_.sequence) {reject(PerceptionIpcFault::Sequence,wall);return;}
    view_.sequence=m.sequence;
    if(m.sender_wall_ns>wall || wall-m.sender_wall_ns>=kPerceptionLifetimeNs) {reject(PerceptionIpcFault::TransportAge,wall);return;}
    if(!m.state_frame) {++view_.unavailable;clear_current(wall);return;}
    const auto& s=m.observed;
    if(view_.state_fault || s.state_received_wall_ns>m.sender_wall_ns ||
       (view_.state_frame && (m.state_frame<view_.state_frame || s.source_ns<view_.state_source_ns ||
        s.state_received_wall_ns<view_.state_received_wall_ns ||
        (m.state_frame==view_.state_frame && (s.source_ns!=view_.state_source_ns || s.state_received_wall_ns!=view_.state_received_wall_ns)) ||
        (m.state_frame>view_.state_frame && s.source_ns<=view_.state_source_ns)))) {
        view_.state_fault=true;reject(PerceptionIpcFault::State,wall);return;
    }
    view_.state_frame=m.state_frame;view_.state_source_ns=s.source_ns;view_.state_received_wall_ns=s.state_received_wall_ns;
    if(!view_.initialized && root_enable_ && s.state_received_wall_ns>=root_enable_ && wall-s.state_received_wall_ns<kPerceptionLifetimeNs) {
        view_.initialized=receiver_.start_session({epoch_,source_clock_,wall_clock_,s.source_ns,root_enable_});
        view_.source_enable_ns=s.source_ns;view_.wall_enable_ns=root_enable_;
    }
    if(!view_.initialized)return;
    const Native2kNow now{s.source_ns,wall,s.state_received_wall_ns};
    if(m.kind==PerceptionIpcKind::Result) {
        if(receiver_.receive(m.result,now))++view_.accepted_results;
        else ++view_.rejected;
    } else if(m.kind==PerceptionIpcKind::Unavailable) {
        ++view_.unavailable;receiver_.unavailable(now);
    } else ++view_.polls;
}
PerceptionIpcView PerceptionIpcShadow::poll(std::uint64_t wall) noexcept {
    if(wall<last_wall_) {view_.state_fault=true;reject(PerceptionIpcFault::State,wall);}
    last_wall_=wall;view_.observed_wall_ns=wall;
    std::array<std::uint8_t,kPerceptionIpcMax> bytes{};
    if(!view_.disconnected)for(unsigned i=0;i<4;++i) {
        const auto size=recv(fd_,bytes.data(),bytes.size(),MSG_DONTWAIT|MSG_TRUNC);
        if(size<0) {
            if(errno==EAGAIN || errno==EWOULDBLOCK || errno==EINTR)break;
            reject(PerceptionIpcFault::Io,wall);view_.disconnected=true;break;
        }
        if(size==0) {reject(PerceptionIpcFault::Disconnected,wall);view_.disconnected=true;break;}
        ++view_.received;PerceptionIpcMessage m;
        if(!decode_perception_ipc(bytes.data(),static_cast<std::size_t>(size),m))reject(PerceptionIpcFault::Encoding,wall);
        else consume(m,wall);
        if(i==3)++view_.budget_hits;
    }
    const auto* f=view_.initialized?receiver_.snapshot({view_.state_source_ns,wall,view_.state_received_wall_ns}):nullptr;
    if(view_.state_fault || view_.disconnected) {clear_current(wall);f=nullptr;}
    view_.reason=receiver_.reason();view_.available=f!=nullptr;
    view_.frame=f?f->frame:0;view_.source_ns=f?f->source_ns:0;view_.expires_ns=f?f->expires_ns:0;
    view_.received_wall_ns=f?f->received_wall_ns:0;view_.wall_expires_ns=f?f->wall_expires_ns:0;
    view_.count=f?f->count:0;view_.tracks=f?receiver_.tracks().count:0;
    return view_;
}
} // namespace stratadrive::central
