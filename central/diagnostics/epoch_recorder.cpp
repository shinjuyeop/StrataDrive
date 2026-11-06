#include "epoch_recorder.hpp"
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#include <algorithm>
#include <cerrno>
#include <filesystem>
#include <iomanip>
#include <limits>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <system_error>

namespace stratadrive::diagnostics {
namespace {
using Bytes=std::vector<std::uint8_t>;
[[noreturn]] void failure(const char* message) {throw std::system_error(errno,std::generic_category(),message);}
struct File {
    int fd;
    explicit File(int value):fd(value) {if(fd<0)failure("epoch journal open");}
    ~File(){close(fd);}
    File(const File&)=delete;File& operator=(const File&)=delete;
};
void sync(int fd){while(fsync(fd)!=0)if(errno!=EINTR)failure("epoch journal fsync");}
void private_file(int fd,bool directory=false) {
    struct stat s{};if(fstat(fd,&s)!=0)failure("epoch journal stat");
    if(s.st_uid!=geteuid() || (s.st_mode&0077) || (directory?!S_ISDIR(s.st_mode):(!S_ISREG(s.st_mode) || s.st_nlink!=1)))
        throw std::runtime_error("epoch journal requires private owned files");
}
void put(Bytes& bytes,std::uint64_t value){for(unsigned i=0;i<8;++i)bytes.push_back(static_cast<std::uint8_t>(value>>(8*i)));}
std::uint64_t get(const Bytes& bytes,std::size_t offset) {
    if(offset>bytes.size() || bytes.size()-offset<8)throw std::runtime_error("epoch metadata truncated");
    std::uint64_t value=0;for(unsigned i=0;i<8;++i)value|=static_cast<std::uint64_t>(bytes[offset+i])<<(8*i);return value;
}
std::uint32_t crc(const Bytes& bytes) {
    std::uint32_t c=0xffffffff;for(auto b:bytes){c^=b;for(unsigned n=0;n<8;++n)c=(c>>1)^((c&1)?0xedb88320U:0U);}return ~c;
}
void write_file(int dir,const char* name,const Bytes& payload) {
    Bytes bytes{'S','D','E','P','O','C','H',1};bytes.insert(bytes.end(),payload.begin(),payload.end());put(bytes,crc(bytes));
    File file(openat(dir,name,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600));
    std::size_t at=0;while(at<bytes.size()) {
        const auto n=write(file.fd,bytes.data()+at,bytes.size()-at);
        if(n<0){if(errno==EINTR)continue;failure("epoch journal write");}
        if(n==0)throw std::runtime_error("epoch journal short write");
        at+=static_cast<std::size_t>(n);
    }
    sync(file.fd);sync(dir);
}
Bytes read_file(int dir,const char* name) {
    File file(openat(dir,name,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK));private_file(file.fd);
    struct stat s{};if(fstat(file.fd,&s)!=0)failure("epoch metadata stat");
    if(s.st_size<16 || s.st_size>8*1024*1024)throw std::runtime_error("epoch metadata size");
    Bytes bytes(static_cast<std::size_t>(s.st_size));std::size_t at=0;
    while(at<bytes.size()) {
        const auto n=read(file.fd,bytes.data()+at,bytes.size()-at);
        if(n<0){if(errno==EINTR)continue;failure("epoch metadata read");}
        if(n==0)throw std::runtime_error("epoch metadata short read");
        at+=static_cast<std::size_t>(n);
    }
    const auto expected=get(bytes,bytes.size()-8);bytes.resize(bytes.size()-8);
    const Bytes magic{'S','D','E','P','O','C','H',1};
    if(!std::equal(magic.begin(),magic.end(),bytes.begin()) || expected!=crc(bytes))throw std::runtime_error("epoch metadata checksum/schema");
    return Bytes(bytes.begin()+8,bytes.end());
}
bool exists(int dir,const char* name) {
    struct stat s{};if(fstatat(dir,name,&s,AT_SYMLINK_NOFOLLOW)==0)return true;
    if(errno!=ENOENT)failure("epoch marker stat");
    return false;
}
void validate(EpochRetention p) {
    validate(p.limits);
    if(!p.rotate_after_entries || p.rotate_after_entries>=p.limits.events || !p.maximum_segments || p.maximum_segments>10000)
        throw std::invalid_argument("epoch retention policy");
}
std::string name(std::uint64_t n){std::ostringstream s;s<<std::setw(8)<<std::setfill('0')<<n;return s.str();}
Bytes pointer(std::uint64_t generation,std::uint64_t base){Bytes b;put(b,generation);put(b,base);return b;}
void publish(int dir) {
    if(renameat(dir,"pending",dir,"current")!=0)failure("epoch pointer rename");
    sync(dir);
}
bool same_limits(Limits a,Limits b){return a.events==b.events && a.records==b.records && a.occurrences==b.occurrences && a.clears==b.clears;}
EventId id(const Entry& entry){return std::visit([](const auto& e){return e.id;},entry);}
}
struct EpochRecorder::Impl {
    std::string root;
    File directory,lock;
    EpochRetention policy{};
    std::uint64_t store_id{0},generation{1},base{0};
    std::unique_ptr<FileJournal> journal;
    std::unique_ptr<Recorder> writer;
    std::vector<std::uint64_t> predecessor_ends;
    std::unique_ptr<FileJournal> read_segment;
    std::uint64_t read_generation{0};
    explicit Impl(const std::string& path):root(path),directory(open(path.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)),
        lock(openat(directory.fd,"lock",O_RDWR|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK)) {
        private_file(directory.fd,true);private_file(lock.fd);
        if(flock(lock.fd,LOCK_EX|LOCK_NB)!=0)failure("epoch journal busy");
        const auto m=read_file(directory.fd,"manifest");
        if(m.size()!=56)throw std::runtime_error("epoch manifest size");
        for(std::size_t i=8;i<56;i+=8)if(get(m,i)>std::numeric_limits<std::uint32_t>::max())throw std::runtime_error("epoch policy range");
        store_id=get(m,0);policy={{static_cast<std::uint32_t>(get(m,8)),static_cast<std::uint32_t>(get(m,16)),
            static_cast<std::uint32_t>(get(m,24)),static_cast<std::uint32_t>(get(m,32))},static_cast<std::uint32_t>(get(m,40)),static_cast<std::uint32_t>(get(m,48))};
        validate(policy);
        if(!store_id || store_id>std::numeric_limits<std::uint64_t>::max()-policy.maximum_segments)throw std::runtime_error("epoch store identity");
        const auto current=read_file(directory.fd,"current");if(current.size()!=16)throw std::runtime_error("epoch pointer size");
        generation=get(current,0);base=get(current,8);
        if(!generation || generation>policy.maximum_segments)throw std::runtime_error("epoch generation bound");
        std::optional<EpochCheckpoint> expected;
        std::uint64_t count=0;
        for(std::uint64_t i=1;i<=generation;++i) {
            const auto folder=std::filesystem::path(root)/name(i);
            writer.reset();journal.reset();
            journal=std::make_unique<FileJournal>(folder.string());
            if(journal->store_id()!=store_id+i-1 || journal->registry_revision()!=4 || !same_limits(journal->limits(),policy.limits))
                throw std::runtime_error("epoch predecessor identity/policy");
            File segment(open(folder.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));private_file(segment.fd,true);
            if(i>1) {
                const auto bytes=read_file(segment.fd,"checkpoint");
                if(!expected || bytes!=encode_checkpoint(*expected))throw std::runtime_error("epoch state transfer mismatch");
                writer=std::make_unique<Recorder>(*journal,decode_checkpoint(bytes));
                if(journal->committed().empty())throw std::runtime_error("epoch missing first session");
                const auto* e=std::get_if<Event>(&journal->committed().front());
                if(!e || (e->kind!=Kind::Session && e->kind!=Kind::Attempt) || e->session.epoch<=expected->previous.epoch)
                    throw std::runtime_error("epoch first session mismatch");
            } else {
                if(exists(segment.fd,"checkpoint"))throw std::runtime_error("epoch unexpected first checkpoint");
                writer=std::make_unique<Recorder>(*journal);
            }
            if(i<generation) {
                if(!journal->writable())throw std::runtime_error("epoch incomplete predecessor");
                expected=writer->ledger().checkpoint();count+=journal->committed().size();predecessor_ends.push_back(count);
            }
        }
        if(count!=base)throw std::runtime_error("epoch watermark mismatch");
        if(exists(directory.fd,"pending") || exists(directory.fd,"incomplete"))writer->recording_gap();
    }
    std::uint64_t watermark() const noexcept{return base+journal->committed().size();}
    const FileJournal& predecessor(std::size_t index) {
        if(read_generation!=index+1) {
            read_segment.reset();read_generation=0;
            read_segment=std::make_unique<FileJournal>((std::filesystem::path(root)/name(index+1)).string());
            read_generation=index+1;
        }
        const auto start=index?predecessor_ends[index-1]:0;
        if(!read_segment->writable() || read_segment->store_id()!=store_id+index ||
           read_segment->registry_revision()!=4 || !same_limits(read_segment->limits(),policy.limits) ||
           read_segment->committed().size()!=predecessor_ends.at(index)-start)throw std::runtime_error("epoch retained stream changed");
        return *read_segment;
    }
    Entry committed(std::uint64_t ordinal) {
        if(!ordinal || ordinal>watermark())throw std::out_of_range("epoch committed ordinal");
        if(ordinal>base)return journal->committed().at(static_cast<std::size_t>(ordinal-base-1));
        const auto end=std::lower_bound(predecessor_ends.begin(),predecessor_ends.end(),ordinal);
        const auto index=static_cast<std::size_t>(end-predecessor_ends.begin());
        const auto start=index?predecessor_ends[index-1]:0;
        return predecessor(index).committed().at(static_cast<std::size_t>(ordinal-start-1));
    }
    void gap() noexcept {
        writer->recording_gap();
        try{if(!exists(directory.fd,"incomplete"))write_file(directory.fd,"incomplete",{});}catch(...){ }
    }
    std::optional<Receipt> duplicate(const Entry& entry) {
        // Keep receipt identity across reclaimed active windows. Cold lookup is
        // deliberately non-RT; retained disk bytes, not a guessed sequence floor.
        for(std::uint64_t i=1;i<=generation;++i) {
            const auto& source=i==generation?*journal:predecessor(static_cast<std::size_t>(i-1));
            for(const auto& prior:source.committed())if(id(prior)==id(entry)) {
                if(encode(prior)==encode(entry))return Receipt{Result::Duplicate,true,watermark()};
                gap();return Receipt{Result::Conflict,false,watermark()};
            }
        }
        return std::nullopt;
    }
    Receipt rotate(const Event& event,const EpochCheckpoint& checkpoint) {
        if(generation>=policy.maximum_segments){gap();return {Result::Capacity,false,watermark()};}
        const auto next=generation+1,total=watermark();
        predecessor_ends.reserve(static_cast<std::size_t>(next-1));
        const auto folder=std::filesystem::path(root)/name(next);
        // Durable intent before successor creation; a partial transfer never
        // masquerades as the original complete family on restart.
        write_file(directory.fd,"pending",pointer(next,total));
        FileJournal::initialize(folder.string(),store_id+next-1,policy.limits,4);
        File dir(open(folder.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
        write_file(dir.fd,"checkpoint",encode_checkpoint(checkpoint));
        auto successor=std::make_unique<FileJournal>(folder.string());
        auto recorder=std::make_unique<Recorder>(*successor,checkpoint);
        const auto receipt=recorder->record(event);
        if(!receipt.durable)throw std::runtime_error("epoch first transaction failed");
        if(renameat(directory.fd,"pending",directory.fd,"current")!=0)failure("epoch pointer rename");
        // Once renamed, even an unacknowledged directory-sync failure refers to
        // the successor. Never mark its immutable predecessor incomplete.
        writer.reset();journal=std::move(successor);writer=std::move(recorder);generation=next;base=total;
        predecessor_ends.push_back(total);
        sync(directory.fd);
        return {receipt.result,true,watermark()};
    }
};
void EpochRecorder::initialize(const std::string& root,std::uint64_t store_id,EpochRetention policy) {
    validate(policy);
    if(root.empty() || root.find('\0')!=std::string::npos || std::filesystem::path(root).filename().empty() ||
       !store_id || store_id>std::numeric_limits<std::uint64_t>::max()-policy.maximum_segments)throw std::invalid_argument("epoch root/id");
    if(mkdir(root.c_str(),0700)!=0)failure("epoch explicit bootstrap");
    File dir(open(root.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));
    File lock(openat(dir.fd,"lock",O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600));
    if(flock(lock.fd,LOCK_EX|LOCK_NB)!=0)failure("epoch bootstrap busy");
    sync(lock.fd);
    Bytes manifest;for(auto v:{store_id,static_cast<std::uint64_t>(policy.limits.events),static_cast<std::uint64_t>(policy.limits.records),
        static_cast<std::uint64_t>(policy.limits.occurrences),static_cast<std::uint64_t>(policy.limits.clears),
        static_cast<std::uint64_t>(policy.rotate_after_entries),static_cast<std::uint64_t>(policy.maximum_segments)})put(manifest,v);
    write_file(dir.fd,"manifest",manifest);write_file(dir.fd,"pending",pointer(1,0));
    FileJournal::initialize((std::filesystem::path(root)/name(1)).string(),store_id,policy.limits,4);publish(dir.fd);
    const auto parent=std::filesystem::path(root).parent_path();File p(open(parent.empty()?".":parent.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC));sync(p.fd);
}
EpochRecorder::EpochRecorder(const std::string& root):impl_(std::make_unique<Impl>(root)){}
EpochRecorder::~EpochRecorder()=default;
Receipt EpochRecorder::record(const Event& event) {
    auto& s=*impl_;
    try {
        if(const auto duplicate=s.duplicate(event))return *duplicate;
        if(!s.writer->ledger().complete())return {Result::NotReady,false,s.watermark()};
        if((event.kind==Kind::Session || event.kind==Kind::Attempt) && event.session.epoch>s.writer->ledger().session().epoch &&
           s.journal->committed().size()>=s.policy.rotate_after_entries) {
            std::optional<EpochCheckpoint> checkpoint;
            try{checkpoint=s.writer->ledger().checkpoint();}catch(const std::runtime_error&){/* Unreviewed gaps stay bounded. */}
            if(checkpoint) {
                Ledger validation(*checkpoint,s.policy.limits);
                const auto result=validation.record(event);
                if(result!=Result::Accepted){s.gap();return {result,false,s.watermark()};}
                return s.rotate(event,*checkpoint);
            }
        }
        auto receipt=s.writer->record(event);receipt.watermark=s.watermark();return receipt;
    }catch(...){s.gap();return {Result::StorageFailure,false,s.watermark()};}
}
Receipt EpochRecorder::clear(const Clear& event) {
    auto& s=*impl_;try{if(const auto old=s.duplicate(event))return *old;auto r=s.writer->clear(event);r.watermark=s.watermark();return r;}
    catch(...){s.gap();return {Result::StorageFailure,false,s.watermark()};}
}
Receipt EpochRecorder::review(const ContinuityReview& event) {
    auto& s=*impl_;try{if(const auto old=s.duplicate(event))return *old;auto r=s.writer->review(event);r.watermark=s.watermark();return r;}
    catch(...){s.gap();return {Result::StorageFailure,false,s.watermark()};}
}
void EpochRecorder::recording_gap() noexcept{impl_->gap();}
const Ledger& EpochRecorder::ledger() const noexcept{return impl_->writer->ledger();}
std::uint64_t EpochRecorder::segment() const noexcept{return impl_->generation;}
std::uint64_t EpochRecorder::watermark() const noexcept{return impl_->watermark();}
std::uint64_t EpochRecorder::store_id() const noexcept{return impl_->store_id;}
Entry EpochRecorder::committed(std::uint64_t ordinal) const {
    if(!ordinal || ordinal>watermark())throw std::out_of_range("epoch committed ordinal");
    try{return impl_->committed(ordinal);}catch(...){impl_->gap();throw;}
}
std::size_t EpochRecorder::drain(EventQueue& queue,std::size_t budget) {
    const auto health=[&]{const auto h=queue.health();if(h.dropped || h.identity_error)recording_gap();};
    health();Event e;std::size_t n=0;while(n<budget && queue.pop(e)){record(e);++n;}health();return n;
}
} // namespace stratadrive::diagnostics
