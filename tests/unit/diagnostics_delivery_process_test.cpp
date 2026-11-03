#include "diagnostics_delivery.hpp"
#include "producer_lifecycle.hpp"
#include "diagnostics_fixture.hpp"
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
template<class F> int sender_process(F run) {
    const auto pid=fork(); if(pid<0) throw std::runtime_error("test sender fork");
    if(pid==0) { try { run(); _exit(::testing::Test::HasFailure()?94:0); } catch(...) { _exit(95); } }
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(15); int status=0;
    while(waitpid(pid,&status,WNOHANG)==0) {
        if(std::chrono::steady_clock::now()>=deadline) { kill(pid,SIGKILL); waitpid(pid,nullptr,0); return -1; }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    return WIFEXITED(status)?WEXITSTATUS(status):-1;
}
// Parent observes an fsynced transaction boundary before an actual SIGKILL.
// No child destructor/clean shutdown is allowed to repair either journal.
template<class F> int kill_at_commit(F run,const std::filesystem::path& log,const char* phase) {
    int pipefd[2]{};if(pipe(pipefd)!=0)throw std::runtime_error("crash pipe");
    const auto pid=fork();if(pid<0)throw std::runtime_error("crash fork");
    if(pid==0) {
        close(pipefd[0]);try {run();const char ready='R';if(write(pipefd[1],&ready,1)!=1)_exit(96);for(;;)pause();}catch(...){_exit(97);}
    }
    close(pipefd[1]);pollfd pending{pipefd[0],POLLIN,0};char ready=0;
    const bool committed=poll(&pending,1,5000)>0 && read(pipefd[0],&ready,1)==1 && ready=='R';close(pipefd[0]);
    kill(pid,SIGKILL);int status=0;waitpid(pid,&status,0);
    const int signal=committed && WIFSIGNALED(status)?WTERMSIG(status):0;
    std::ofstream(log,std::ios::app)<<phase<<','<<pid<<','<<committed<<','<<signal<<'\n';return signal;
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
                trace<<"ordinal,result,watermark,ack_ready,ack_sent,condition,count,generation,cleared,receiver_pid,sender_pid\n";
                for(;;) {
                    const auto packet=receive_packet(pair[1]); if(packet.empty()) break;
                    std::uint64_t ordinal=0;
                    try { ordinal=std::get<wire::Data>(wire::decode(packet)).sequence; } catch(const std::exception&) { /* Corrupt frame has no trusted ordinal. */ }
                    const auto r=in.receive(packet);
                    const bool dropping=drop_ack && ordinal==2;
                    trace<<ordinal<<','<<static_cast<unsigned>(r.result)<<','<<r.watermark<<','<<r.ack.has_value()<<','<<(r.ack && !dropping)<<',';
                    if(in.ledger().records().empty()) trace<<"-1,0,0,0";
                    else { const auto& d=in.ledger().records()[0]; trace<<static_cast<unsigned>(d.condition)<<','<<d.count<<','<<d.generation<<','<<d.cleared; }
                    trace<<','<<getpid()<<','<<getppid()<<'\n';
                    trace.flush();
                    if(!r.ack) {
                        if(in.healthy() && (r.result==Result::Invalid || r.result==Result::NotReady)) continue;
                        _exit(91);
                    }
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
    ASSERT_EQ(sender_process([&] {
        FileJournal journal(source.string()); Outbox out(journal); ASSERT_EQ(journal.committed().size(),19U); ASSERT_EQ(std::get<Event>(journal.committed()[1]).kind,Kind::Fault);
        Peer peer(replica,root/"round1.csv",true);
        auto packet=out.next(); ASSERT_TRUE(packet); capture_packet(*packet,"data",1); send_packet(peer.fd(),*packet);
        const auto a=receive_packet(peer.fd()); ASSERT_FALSE(a.empty()); capture_packet(a,"ack",1); ASSERT_EQ(out.acknowledge(a),Result::Accepted);
        packet=out.next(); ASSERT_TRUE(packet); capture_packet(*packet,"data",1); send_packet(peer.fd(),*packet);
        EXPECT_TRUE(receive_packet(peer.fd()).empty()); EXPECT_EQ(out.acknowledged(),1U); EXPECT_EQ(peer.finish(),0);
    }),0);
    std::filesystem::copy(replica,root/"replica-lost-ack",std::filesystem::copy_options::recursive);
    ASSERT_EQ(sender_process([&] {
        FileJournal journal(source.string()); Outbox out(journal); EXPECT_EQ(out.acknowledged(),0U);
        Peer peer(replica,root/"round2.csv",false);
        const auto future=wire::encode(wire::Data{6001,19,3,std::get<Event>(journal.committed()[18])});
        capture_packet(future,"data",2); send_packet(peer.fd(),future);
        auto corrupt=wire::encode(wire::Data{6001,1,3,std::get<Event>(journal.committed()[0])}); corrupt.back()^=1;
        capture_packet(corrupt,"corrupt",2); send_packet(peer.fd(),corrupt);
        // The next received ACK must still belong to the real ordinal1 retry.
        transfer(out,peer,2); ASSERT_FALSE(HasFatalFailure()); EXPECT_EQ(out.acknowledged(),19U); EXPECT_EQ(peer.finish(),0);
    }),0);
    std::filesystem::copy(replica,root/"replica-delivered",std::filesystem::copy_options::recursive);
    ASSERT_EQ(sender_process([&] {
        FileJournal journal(source.string()); Outbox out(journal); Peer peer(replica,root/"round3.csv",false);
        transfer(out,peer,3); ASSERT_FALSE(HasFatalFailure()); EXPECT_EQ(out.acknowledged(),19U); EXPECT_EQ(peer.finish(),0);
    }),0);
    {
        FileJournal s(source.string()),d(replica.string()); Inbox in(d); ASSERT_EQ(s.committed().size(),d.committed().size()); ASSERT_EQ(in.ledger().records().size(),1U);
        for(std::size_t i=0;i<s.committed().size();++i) EXPECT_EQ(encode(s.committed()[i]),encode(d.committed()[i]));
        const auto& r=in.ledger().records()[0]; EXPECT_EQ(r.condition,Condition::Unknown); EXPECT_EQ(r.count,1U); EXPECT_EQ(r.generation,1U); EXPECT_FALSE(r.cleared); EXPECT_TRUE(in.healthy());
    }
    if(const auto* target=std::getenv("STRATADRIVE_M9_DELIVERY_EVIDENCE")) {
        ASSERT_FALSE(std::filesystem::exists(target)); std::filesystem::copy(root,target,std::filesystem::copy_options::recursive);
    }
}
TEST_F(DiagnosticsDeliveryProcess, SigkillAtSourceReplicaAndMergedCommitCutsRetainsBytesAndNeverRecounts) {
    using diagnostics_fixture::session;using diagnostics_fixture::fault;
    const auto merged=root/"merged";FileJournal::initialize(merged.string(),9000,{},3);
    const auto fresh=root/"fresh";FileJournal::initialize(fresh.string(),6001,{},3);
    const auto s=session(),f=fault();std::ofstream(root/"cuts.csv")<<"phase,pid,committed,signal\n";
    ASSERT_EQ(kill_at_commit([&] {FileJournal j(fresh.string());Outbox out(j);if(!out.record(s).durable || !out.record(f).durable)throw std::runtime_error("source commit");},root/"cuts.csv","source"),SIGKILL);
    ASSERT_EQ(kill_at_commit([&] {
        FileJournal j(replica.string());Inbox in(j);
        if(!in.receive(wire::encode(wire::Data{6001,1,3,s})).ack || !in.receive(wire::encode(wire::Data{6001,2,3,f})).ack)throw std::runtime_error("replica commit");
    },root/"cuts.csv","replica"),SIGKILL);
    std::filesystem::copy(replica,root/"replica-before-reconcile",std::filesystem::copy_options::recursive);
    ASSERT_EQ(kill_at_commit([&] {
        FileJournal r(replica.string()),m(merged.string());MergedCollector in(m,{&r});
        if(m.committed().size()!=2 || in.ledger().find(f.key)->condition!=Condition::Unknown)throw std::runtime_error("merged reconcile");
    },root/"cuts.csv","merged"),SIGKILL);
    FileJournal j(fresh.string()),r(replica.string()),m(merged.string());Outbox out(j);MergedCollector in(m,{&r});
    EXPECT_EQ(in.ledger().find(f.key)->condition,Condition::Unknown);
    while(const auto packet=out.next()) {
        capture_packet(*packet,"data",4);const auto receipt=in.receive(*packet);ASSERT_TRUE(receipt.ack);capture_packet(*receipt.ack,"ack",4);EXPECT_EQ(receipt.result,Result::Duplicate);ASSERT_EQ(out.acknowledge(*receipt.ack),Result::Accepted);
    }
    ASSERT_EQ(m.committed().size(),2U);ASSERT_EQ(r.committed().size(),2U);ASSERT_EQ(j.committed().size(),2U);
    for(unsigned i=0;i<2;++i){EXPECT_EQ(encode(j.committed()[i]),encode(r.committed()[i]));EXPECT_EQ(encode(j.committed()[i]),encode(m.committed()[i]));}
    EXPECT_EQ(in.ledger().find(f.key)->condition,Condition::Unknown);EXPECT_EQ(in.ledger().find(f.key)->count,1U);EXPECT_EQ(in.ledger().find(f.key)->generation,1U);EXPECT_FALSE(in.ledger().find(f.key)->cleared);
    const auto& record=*in.ledger().find(f.key);
    std::ofstream(root/"restart-projection.csv")<<"condition,count,generation,cleared\n"<<static_cast<unsigned>(record.condition)<<','<<record.count<<','<<record.generation<<','<<record.cleared<<'\n';
    if(const auto* target=std::getenv("STRATADRIVE_M9_RESTART_EVIDENCE")) {ASSERT_FALSE(std::filesystem::exists(target));std::filesystem::copy(root,target,std::filesystem::copy_options::recursive);}
}
TEST_F(DiagnosticsDeliveryProcess, KilledVolatileQueueGetsFreshProducerAndExplicitUnverifiedContinuity) {
    const auto lifecycle=root/"producer-lifecycle",old=root/"old-source",fresh=root/"new-source";
    FileJournal::initialize(lifecycle.string(),9001,{},3);FileJournal::initialize(old.string(),6002,{},3);FileJournal::initialize(fresh.string(),6003,{},3);
    const ControlContext identity{10,9001,Domain::Monotonic,99,1};
    auto context=diagnostics_fixture::session();context.profile=1;context.session_enable={Domain::Monotonic,99,1000000000,true,true};
    auto lost=diagnostics_fixture::fault();lost.id.producer=30;lost.occurrence.producer=30;lost.session_enable=context.session_enable;
    lost.times[static_cast<unsigned>(Time::Detected)]={Domain::Monotonic,99,1000000002,true,true};
    write_bytes(root/"volatile-event.bin",encode(lost));std::ofstream(root/"cuts.csv")<<"phase,pid,committed,signal\n";
    ASSERT_EQ(kill_at_commit([&] {
        ProducerLifecycle life(lifecycle.string(),identity,100);FileJournal j(old.string());Outbox out(j);if(!out.record(context).durable)throw std::runtime_error("old context commit");
        EventQueue q(10,life.producer(30));if(!q.publish(lost))throw std::runtime_error("volatile queue publish");
    },root/"cuts.csv","volatile-queued"),SIGKILL);
    ProducerLifecycle life(lifecycle.string(),identity,101);ASSERT_TRUE(life.previous_unclean());ASSERT_EQ(life.generation(),2U);EXPECT_NE(life.producer(30),lost.id.producer);
    FileJournal prior(old.string()),j(fresh.string());CommittedReplay history(prior);ASSERT_EQ(prior.committed().size(),1U);Outbox out(j);
    context.id.sequence=2;context.session.epoch=2;ASSERT_TRUE(out.record(context).durable);
    const ControlContext producer{10,life.producer(30),Domain::Monotonic,99,1};
    const auto gap=continuity_fault(producer,30,2,Component::Front,2,context.session_enable.ns,101,1000000010);
    ASSERT_TRUE(out.record(gap).durable);EXPECT_TRUE(out.healthy());EXPECT_TRUE(out.ledger().unmapped());EXPECT_EQ(out.ledger().find(gap.key)->count,1U);
    for(const auto& entry:prior.committed())EXPECT_FALSE(std::get<Event>(entry).id==lost.id);
    for(const auto& entry:j.committed())EXPECT_FALSE(std::get<Event>(entry).id==lost.id);
    EXPECT_EQ(life.close(1000000020),Result::Accepted);
    if(const auto* target=std::getenv("STRATADRIVE_M9_VOLATILE_EVIDENCE")) {ASSERT_FALSE(std::filesystem::exists(target));std::filesystem::copy(root,target,std::filesystem::copy_options::recursive);}
}
} // namespace
