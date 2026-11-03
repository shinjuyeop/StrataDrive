#include "diagnostics_delivery.hpp"
#include <gtest/gtest.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <poll.h>
#include <signal.h>
#include <unistd.h>
#include <array>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <thread>

namespace {
using namespace stratadrive::diagnostics;
void send_packet(int fd,const wire::Bytes& b) {
    if(send(fd,b.data(),b.size(),MSG_NOSIGNAL)!=static_cast<ssize_t>(b.size())) throw std::runtime_error("test datagram send");
}
wire::Bytes receive_packet(int fd) {
    pollfd p{fd,POLLIN,0}; if(poll(&p,1,5000)<=0) throw std::runtime_error("test datagram timeout");
    std::array<std::uint8_t,wire::kMaxPacket+1> bytes{}; const auto n=recv(fd,bytes.data(),bytes.size(),0);
    if(n<0 || n>static_cast<ssize_t>(wire::kMaxPacket)) throw std::runtime_error("test datagram receive");
    return {bytes.begin(),bytes.begin()+n};
}
void write_bytes(const std::filesystem::path& p,const wire::Bytes& bytes) {
    std::ofstream f(p,std::ios::binary); f.write(reinterpret_cast<const char*>(bytes.data()),static_cast<std::streamsize>(bytes.size()));
}
class Peer {
public:
    Peer(const std::filesystem::path& store,const std::filesystem::path& log,bool drop_ack) {
        int pair[2]{}; if(socketpair(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0,pair)!=0) throw std::runtime_error("test socketpair");
        pid_=fork();
        if(pid_<0) { close(pair[0]); close(pair[1]); throw std::runtime_error("test fork"); }
        if(pid_==0) {
            close(pair[0]);
            try {
                FileJournal journal(store.string()); Inbox in(journal); std::ofstream trace(log);
                trace<<"ordinal,result,watermark,ack_ready,ack_sent,condition,count,generation,cleared\n";
                for(;;) {
                    const auto packet=receive_packet(pair[1]); if(packet.empty()) break;
                    const auto ordinal=std::get<wire::Data>(wire::decode(packet)).sequence; const auto r=in.receive(packet);
                    const bool dropping=drop_ack && ordinal==2;
                    trace<<ordinal<<','<<static_cast<unsigned>(r.result)<<','<<r.watermark<<','<<r.ack.has_value()<<','<<(r.ack && !dropping)<<',';
                    if(in.ledger().records().empty()) trace<<"-1,0,0,0\n";
                    else { const auto& d=in.ledger().records()[0]; trace<<static_cast<unsigned>(d.condition)<<','<<d.count<<','<<d.generation<<','<<d.cleared<<'\n'; }
                    trace.flush();
                    if(!r.ack) _exit(91);
                    if(dropping) { write_bytes(log.parent_path()/"lost-ack.bin",*r.ack); _exit(0); }
                    send_packet(pair[1],*r.ack);
                }
                _exit(in.healthy()?0:92);
            } catch(...) { _exit(93); }
        }
        close(pair[1]); fd_=pair[0];
    }
    ~Peer() {
        if(fd_>=0) close(fd_);
        if(pid_>0) { kill(pid_,SIGKILL); waitpid(pid_,nullptr,0); }
    }
    int fd() const { return fd_; }
    int finish() {
        close(fd_); fd_=-1;
        const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
        int status=0;
        while(waitpid(pid_,&status,WNOHANG)==0) {
            if(std::chrono::steady_clock::now()>=deadline) throw std::runtime_error("test peer exit timeout");
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        pid_=-1; return WIFEXITED(status)?WEXITSTATUS(status):-1;
    }
private:
    pid_t pid_{-1}; int fd_{-1};
};
class DiagnosticsDeliveryProcess : public ::testing::Test {
protected:
    std::filesystem::path root,source,replica; unsigned capture{0};
    void SetUp() override {
        char name[]="/tmp/stratadrive-delivery-process-XXXXXX"; auto* p=mkdtemp(name); ASSERT_NE(p,nullptr); root=p; source=root/"source"; replica=root/"replica";
        const auto fixture=std::filesystem::path(STRATADRIVE_SOURCE_DIR)/"docs/test-plan/evidence/m9_startup_sources/normal/release/store";
        std::filesystem::copy(fixture,source,std::filesystem::copy_options::recursive); FileJournal::initialize(replica.string(),6001,{},3);
        std::filesystem::create_directory(root/"wire");
    }
    void TearDown() override { std::filesystem::remove_all(root); }
    void capture_packet(const wire::Bytes& b,const char* direction,unsigned round) {
        write_bytes(root/"wire"/(std::to_string(++capture)+"-r"+std::to_string(round)+"-"+direction+".bin"),b);
    }
    void transfer(Outbox& out,Peer& peer,unsigned round) {
        while(const auto packet=out.next()) {
            capture_packet(*packet,"data",round); send_packet(peer.fd(),*packet); const auto a=receive_packet(peer.fd());
            ASSERT_FALSE(a.empty()); capture_packet(a,"ack",round); ASSERT_EQ(out.acknowledge(a),Result::Accepted);
        }
    }
};
TEST_F(DiagnosticsDeliveryProcess, LostAckAndBothProcessRestartsKeepOriginalHistoryAndUnknownOnReplay) {
    {
        FileJournal journal(source.string()); Outbox out(journal); ASSERT_EQ(journal.committed().size(),19U); ASSERT_EQ(std::get<Event>(journal.committed()[1]).kind,Kind::Fault);
        Peer peer(replica,root/"round1.csv",true);
        auto packet=out.next(); ASSERT_TRUE(packet); capture_packet(*packet,"data",1); send_packet(peer.fd(),*packet);
        const auto a=receive_packet(peer.fd()); ASSERT_FALSE(a.empty()); capture_packet(a,"ack",1); ASSERT_EQ(out.acknowledge(a),Result::Accepted);
        packet=out.next(); ASSERT_TRUE(packet); capture_packet(*packet,"data",1); send_packet(peer.fd(),*packet);
        EXPECT_TRUE(receive_packet(peer.fd()).empty()); EXPECT_EQ(out.acknowledged(),1U); EXPECT_EQ(peer.finish(),0);
    }
    std::filesystem::copy(replica,root/"replica-lost-ack",std::filesystem::copy_options::recursive);
    {
        FileJournal journal(source.string()); Outbox out(journal); EXPECT_EQ(out.acknowledged(),0U);
        Peer peer(replica,root/"round2.csv",false); transfer(out,peer,2); ASSERT_FALSE(HasFatalFailure()); EXPECT_EQ(out.acknowledged(),19U); EXPECT_EQ(peer.finish(),0);
    }
    std::filesystem::copy(replica,root/"replica-delivered",std::filesystem::copy_options::recursive);
    {
        FileJournal journal(source.string()); Outbox out(journal); Peer peer(replica,root/"round3.csv",false);
        transfer(out,peer,3); ASSERT_FALSE(HasFatalFailure()); EXPECT_EQ(out.acknowledged(),19U); EXPECT_EQ(peer.finish(),0);
    }
    {
        FileJournal s(source.string()),d(replica.string()); Inbox in(d); ASSERT_EQ(s.committed().size(),d.committed().size()); ASSERT_EQ(in.ledger().records().size(),1U);
        for(std::size_t i=0;i<s.committed().size();++i) EXPECT_EQ(encode(s.committed()[i]),encode(d.committed()[i]));
        const auto& r=in.ledger().records()[0]; EXPECT_EQ(r.condition,Condition::Unknown); EXPECT_EQ(r.count,1U); EXPECT_EQ(r.generation,1U); EXPECT_FALSE(r.cleared); EXPECT_TRUE(in.healthy());
    }
    if(const auto* target=std::getenv("STRATADRIVE_M9_DELIVERY_EVIDENCE")) {
        ASSERT_FALSE(std::filesystem::exists(target)); std::filesystem::copy(root,target,std::filesystem::copy_options::recursive);
    }
}
} // namespace
