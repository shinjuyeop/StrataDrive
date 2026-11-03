#include "continuity_service_fixture.hpp"
#include <poll.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <sys/wait.h>

namespace {
using namespace continuity_fixture;
struct Checkpoint:Journal {
    FileJournal& file;unsigned cut,count{0};int pipe;
    Checkpoint(FileJournal& f,unsigned c,int p):file(f),cut(c),pipe(p){}
    Limits limits() const noexcept override{return file.limits();}const std::vector<Entry>& committed() const noexcept override{return file.committed();}
    bool writable() const noexcept override{return file.writable();}void invalidate() noexcept override{file.invalidate();}
    bool append(const Entry& entry) override{if(!file.append(entry))return false;if(++count==cut){const char done='C';if(write(pipe,&done,1)!=1)_exit(91);for(;;)pause();}return true;}
};
int connect_local(const std::filesystem::path& path){
    const auto fd=socket(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0);sockaddr_un address{};address.sun_family=AF_UNIX;const auto name=path.string();
    if(fd<0 || name.size()>=sizeof(address.sun_path))_exit(92);
    std::copy(name.begin(),name.end(),address.sun_path);
    if(connect(fd,reinterpret_cast<sockaddr*>(&address),sizeof(address)))_exit(93);
    return fd;
}
ServiceReply exchange(int fd,const ServiceRequest& r){const auto b=encode_service_request(r);if(send(fd,b.data(),b.size(),MSG_NOSIGNAL)!=static_cast<ssize_t>(b.size()))_exit(94);
    pollfd p{fd,POLLIN,0};if(poll(&p,1,5000)<=0)_exit(95);std::vector<std::uint8_t> response(128);const auto n=recv(fd,response.data(),response.size(),MSG_DONTWAIT);if(n<=0)_exit(96);response.resize(static_cast<std::size_t>(n));return decode_service_reply(response);}
bool wait_char(int fd,char expected){pollfd p{fd,POLLIN,0};char c=0;return poll(&p,1,5000)>0 && read(fd,&c,1)==1 && c==expected;}
TEST_F(ContinuityServiceTest, NativeUnixPeerAuthorizationAndFourSigkillCommitCutsPreserveTheSameFrozenOriginals) {
    baseline();fresh();const auto scoped=permit();const auto review=request();const auto original=encode(incident);const auto base=local->committed().size();
    const std::array<std::uint64_t,2> ack{{out[0]->acknowledged(),out[1]->acknowledged()}};close_files();
    const auto* configured=std::getenv("STRATADRIVE_CONTINUITY_SERVICE_TEST_DIR");const auto exports=configured?std::filesystem::path(configured):root/"exports";std::filesystem::create_directories(exports);
    for(const auto* name:{"release.csv","credits.csv"})std::filesystem::copy_file(root/name,exports/name,std::filesystem::copy_options::overwrite_existing);
    for(unsigned cut=1;cut<=4;++cut){const auto folder=exports/("cut-"+std::to_string(cut));std::filesystem::create_directories(folder);
        for(const auto* name:{"case","source-0","source-1","replica-0","replica-1"})std::filesystem::copy(root/name,folder/name,std::filesystem::copy_options::recursive);
        SCOPED_TRACE(cut);
        const auto socket_path=root/("service-"+std::to_string(cut)+".sock");int ready[2]{};ASSERT_EQ(pipe(ready),0);const auto server=fork();ASSERT_GE(server,0);
        if(server==0){close(ready[0]);try{
            FileJournal journal((folder/"case").string());Checkpoint journal_cut(journal,cut,ready[1]);Recorder recorder(journal_cut);
            std::vector<StreamState> frozen;for(unsigned i=0;i<2;++i){sources[i]=std::make_unique<FileJournal>((folder/("source-"+std::to_string(i))).string());replicas[i]=std::make_unique<FileJournal>((folder/("replica-"+std::to_string(i))).string());frozen.push_back({sources[i].get(),replicas[i].get(),ack[i],0,{}});}
            capture.frozen_states=frozen;capture.export_samples=folder;ContinuityService service(recorder,bindings,scoped,capture);
            const auto listener=socket(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0);sockaddr_un address{};address.sun_family=AF_UNIX;const auto name=socket_path.string();if(name.size()>=sizeof(address.sun_path))_exit(97);std::copy(name.begin(),name.end(),address.sun_path);
            if(listener<0 || bind(listener,reinterpret_cast<sockaddr*>(&address),sizeof(address)) || chmod(name.c_str(),0600) || listen(listener,4))_exit(98);
            const char up='R';if(write(ready[1],&up,1)!=1)_exit(99);
            for(;;){pollfd wait{listener,POLLIN,0};if(poll(&wait,1,5000)<=0)_exit(100);const auto peer=accept4(listener,nullptr,nullptr,SOCK_CLOEXEC);if(peer<0)_exit(101);
                pollfd packet{peer,POLLIN,0};if(poll(&packet,1,5000)<=0)_exit(102);(void)service.serve(peer);close(peer);}
        }catch(...){_exit(103);}}
        close(ready[1]);bool ok=wait_char(ready[0],'R');EXPECT_TRUE(ok)<<"listener ready";pid_t denied=-1;
        if(ok){denied=fork();if(denied==0){const auto fd=connect_local(socket_path);const auto denied_reply=exchange(fd,review);close(fd);_exit(denied_reply.status==ServiceStatus::Unauthorized?0:104);}
            int status=0;if(denied<0 || waitpid(denied,&status,0)!=denied || !WIFEXITED(status) || WEXITSTATUS(status)!=0)ok=false;EXPECT_TRUE(ok)<<"kernel peer denied status="<<status;}
        if(ok){const auto fd=connect_local(socket_path);auto bad=review;bad.capability[0]^=1;ok=exchange(fd,bad).status==ServiceStatus::Unauthorized;close(fd);EXPECT_TRUE(ok)<<"capability denial";}
        if(ok){const auto fd=connect_local(socket_path);const auto bytes=encode_service_request(review);std::ofstream raw(folder/"review.request",std::ios::binary);raw.write(reinterpret_cast<const char*>(bytes.data()),static_cast<std::streamsize>(bytes.size()));raw.close();
            ok=send(fd,bytes.data(),bytes.size(),MSG_NOSIGNAL)==static_cast<ssize_t>(bytes.size());
            if(ok && cut==4){pollfd p{fd,POLLIN,0};ok=poll(&p,1,5000)>0;std::vector<std::uint8_t> response(128);const auto n=ok?recv(fd,response.data(),response.size(),0):-1;
                if(n>0){response.resize(static_cast<std::size_t>(n));const auto approved=decode_service_reply(response);ok=approved.status==ServiceStatus::Accepted && approved.stage==3;
                    auto clear=review;clear.number=2;clear.revision=approved.revision;clear.operation=ServiceOperation::Clear;clear.disposition=ContinuityDisposition::None;
                    const auto clear_bytes=encode_service_request(clear);const auto clear_fd=connect_local(socket_path);ok=ok && send(clear_fd,clear_bytes.data(),clear_bytes.size(),MSG_NOSIGNAL)==static_cast<ssize_t>(clear_bytes.size());close(clear_fd);
                }else ok=false;
            }
            if(ok)ok=wait_char(ready[0],'C');
            EXPECT_TRUE(ok)<<"commit checkpoint";
            close(fd);
        }
        kill(server,SIGKILL);int status=0;ASSERT_EQ(waitpid(server,&status,0),server);close(ready[0]);ASSERT_TRUE(ok);ASSERT_TRUE(WIFSIGNALED(status));ASSERT_EQ(WTERMSIG(status),SIGKILL);
        FileJournal reopened((folder/"case").string());Recorder recorder(reopened);ASSERT_EQ(reopened.committed().size(),base+cut);const auto* record=recorder.ledger().find(incident.key);ASSERT_NE(record,nullptr);
        EXPECT_EQ(record->condition,Condition::Unknown);EXPECT_EQ(record->cleared,cut==4);EXPECT_EQ(record->count,1U);EXPECT_EQ(record->generation,1U);EXPECT_EQ(encode(recorder.ledger().events()[2]),original);
        std::ofstream(folder/"summary.json")<<"{\"stage\":"<<cut<<",\"server_pid\":"<<server<<",\"authorized_pid\":"<<getpid()<<",\"denied_pid\":"<<denied<<",\"uid\":"<<getuid()<<",\"signal\":9,\"watermark\":"<<reopened.committed().size()<<",\"condition\":0,\"cleared\":"<<(record->cleared?"true":"false")<<",\"source_acks\":["<<ack[0]<<','<<ack[1]<<"]}\n";
    }
}
} // namespace
