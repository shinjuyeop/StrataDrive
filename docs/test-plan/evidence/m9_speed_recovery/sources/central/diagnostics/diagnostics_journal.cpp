#include "diagnostics_journal.hpp"

#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <cerrno>
#include <filesystem>
#include <limits>
#include <stdexcept>
#include <system_error>
#include <utility>

namespace stratadrive::diagnostics {
namespace {
using Bytes=std::vector<std::uint8_t>;
constexpr std::array<std::uint8_t,8> kManifest{'S','D','D','M','A','N',1,0};
constexpr std::array<std::uint8_t,8> kCommit{'S','D','D','C','M','T',1,0};
constexpr std::array<std::uint8_t,8> kFrame{'S','D','D','E','V','T',1,0};
constexpr std::uint64_t kMaxBytes=64*1024*1024;
constexpr std::uint32_t kMaxPayload=256*1024;
[[noreturn]] void failure(const char* what) { throw std::system_error(errno,std::generic_category(),what); }
class File {
public:
    explicit File(int fd):fd_(fd) { if(fd<0) failure("diagnostics open"); }
    ~File() { close(fd_); }
    File(const File&)=delete; File& operator=(const File&)=delete;
    int fd() const { return fd_; }
private: int fd_;
};
void path_ok(const std::string& p) {
    if(p.empty() || p.find('\0')!=std::string::npos || std::filesystem::path(p).filename().empty()) throw std::invalid_argument("diagnostics directory");
}
std::uint64_t size(int fd) {
    struct stat s{}; if(fstat(fd,&s)!=0) failure("diagnostics fstat");
    if(!S_ISREG(s.st_mode) || s.st_nlink!=1 || s.st_size<0) throw std::runtime_error("diagnostics private regular file required");
    return static_cast<std::uint64_t>(s.st_size);
}
void sync(int fd) { while(fsync(fd)!=0) if(errno!=EINTR) failure("diagnostics fsync"); }
void write_all(int fd,const Bytes& bytes) {
    std::size_t pos=0;
    while(pos<bytes.size()) {
        const auto n=write(fd,bytes.data()+pos,bytes.size()-pos);
        if(n<0) { if(errno==EINTR) continue; failure("diagnostics write"); }
        if(n==0) throw std::runtime_error("diagnostics short write");
        pos+=static_cast<std::size_t>(n);
    }
}
Bytes read_at(int fd,std::uint64_t offset,std::size_t count) {
    Bytes out(count); std::size_t pos=0;
    while(pos<count) {
        const auto n=pread(fd,out.data()+pos,count-pos,static_cast<off_t>(offset+pos));
        if(n<0) { if(errno==EINTR) continue; failure("diagnostics read"); }
        if(n==0) throw std::runtime_error("diagnostics truncated file");
        pos+=static_cast<std::size_t>(n);
    }
    return out;
}
std::uint32_t crc(const Bytes& b,std::size_t count) {
    std::uint32_t c=0xffffffff;
    for(std::size_t n=0;n<count;++n) {
        c^=b[n]; for(unsigned bit=0;bit<8;++bit) c=(c>>1)^((c&1)?0xedb88320U:0U);
    }
    return ~c;
}
void put(Bytes& b,std::uint64_t value,std::size_t width) {
    for(std::size_t n=0;n<width;++n) b.push_back(static_cast<std::uint8_t>(value>>(8*n)));
}
std::uint64_t get(const Bytes& b,std::size_t offset,std::size_t width) {
    if(offset>b.size() || width>b.size()-offset || width>8) throw std::runtime_error("diagnostics number bounds");
    std::uint64_t value=0; for(std::size_t n=0;n<width;++n) value|=static_cast<std::uint64_t>(b[offset+n])<<(8*n);
    return value;
}
void seal(Bytes& b) { put(b,crc(b,b.size()),4); }
void check(const Bytes& b,const std::array<std::uint8_t,8>& magic) {
    if(b.size()<12 || !std::equal(magic.begin(),magic.end(),b.begin()) || get(b,b.size()-4,4)!=crc(b,b.size()-4)) throw std::runtime_error("diagnostics checksum/magic");
}
Bytes manifest(std::uint64_t id,Limits limits) {
    Bytes b(kManifest.begin(),kManifest.end()); put(b,id,8);
    for(auto value : {limits.events,limits.records,limits.occurrences,limits.clears}) put(b,value,4);
    put(b,1,4); // code registry revision
    seal(b); return b;
}
Bytes commit(std::uint64_t sequence,std::uint64_t offset) {
    Bytes b(kCommit.begin(),kCommit.end()); put(b,sequence,8); put(b,offset,8); seal(b); return b;
}
void replace_commit(int dir,const Bytes& bytes) {
    // A leftover pending file never grants a commit. Keep the old watermark
    // authoritative until the new journal data and checkpoint are both synced.
    if(unlinkat(dir,"pending",0)!=0 && errno!=ENOENT) failure("diagnostics remove pending");
    File pending(openat(dir,"pending",O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600));
    write_all(pending.fd(),bytes); sync(pending.fd());
    if(renameat(dir,"pending",dir,"commit")!=0) failure("diagnostics commit rename");
    sync(dir);
}
Bytes small_file(int dir,const char* name,std::size_t length) {
    File file(openat(dir,name,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK));
    if(size(file.fd())!=length) throw std::runtime_error("diagnostics metadata size");
    return read_at(file.fd(),0,length);
}
} // namespace
struct FileJournal::Impl {
    File directory,lock,data;
    Limits limits{}; std::uint64_t id{0},offset{0},tail{0}; bool healthy{true};
    std::vector<Entry> entries;
    explicit Impl(const std::string& p):
        directory(open(p.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW)),
        lock(openat(directory.fd(),"lock",O_RDWR|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK)),
        data(openat(directory.fd(),"journal",O_RDWR|O_APPEND|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK)) {
        size(lock.fd());
        if(flock(lock.fd(),LOCK_EX|LOCK_NB)!=0) failure("diagnostics store busy");
        const auto m=small_file(directory.fd(),"manifest",40); check(m,kManifest);
        id=get(m,8,8); if(id==0 || get(m,32,4)!=1) throw std::runtime_error("diagnostics manifest version");
        limits={static_cast<std::uint32_t>(get(m,16,4)),static_cast<std::uint32_t>(get(m,20,4)),
            static_cast<std::uint32_t>(get(m,24,4)),static_cast<std::uint32_t>(get(m,28,4))};
        validate(limits); entries.reserve(limits.events+limits.clears);
        const auto checkpoint=small_file(directory.fd(),"commit",28); check(checkpoint,kCommit);
        const auto sequence=get(checkpoint,8,8); offset=get(checkpoint,16,8);
        const auto length=size(data.fd());
        if(length>kMaxBytes || offset>length || sequence>limits.events+limits.clears) throw std::runtime_error("diagnostics journal bounds");
        std::uint64_t cursor=0;
        for(std::uint64_t n=1;n<=sequence;++n) {
            if(offset-cursor<24) throw std::runtime_error("diagnostics frame truncated");
            auto header=read_at(data.fd(),cursor,20);
            if(!std::equal(kFrame.begin(),kFrame.end(),header.begin()) || get(header,8,8)!=n) throw std::runtime_error("diagnostics frame sequence/magic");
            const auto payload=get(header,16,4);
            if(payload>kMaxPayload || payload+24>offset-cursor) throw std::runtime_error("diagnostics frame length");
            const auto frame=read_at(data.fd(),cursor,static_cast<std::size_t>(payload+24)); check(frame,kFrame);
            entries.push_back(decode(Bytes(frame.begin()+20,frame.end()-4))); cursor+=payload+24;
        }
        if(cursor!=offset) throw std::runtime_error("diagnostics watermark mismatch");
        tail=length-offset; healthy=tail==0;
        struct stat gap{};
        if(fstatat(directory.fd(),"incomplete",&gap,AT_SYMLINK_NOFOLLOW)==0) healthy=false;
        else if(errno!=ENOENT) failure("diagnostics gap marker");
        // Preserve an uncommitted suffix byte-for-byte. This store is read-only
        // until an explicit reconciliation; opening never silently truncates it.
    }
};
void FileJournal::initialize(const std::string& p,std::uint64_t id,Limits limits) {
    path_ok(p); validate(limits); if(!id) throw std::invalid_argument("diagnostics store id");
    if(mkdir(p.c_str(),0700)!=0) failure("diagnostics explicit bootstrap");
    File directory(open(p.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW));
    File lock(openat(directory.fd(),"lock",O_RDWR|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600));
    if(flock(lock.fd(),LOCK_EX|LOCK_NB)!=0) failure("diagnostics bootstrap lock");
    File data(openat(directory.fd(),"journal",O_RDWR|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600));
    File m(openat(directory.fd(),"manifest",O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600));
    write_all(m.fd(),manifest(id,limits)); sync(m.fd()); sync(data.fd()); sync(lock.fd());
    replace_commit(directory.fd(),commit(0,0));
    const auto parent=std::filesystem::path(p).parent_path();
    File parent_dir(open(parent.empty()?".":parent.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC)); sync(parent_dir.fd());
}
FileJournal::FileJournal(const std::string& p) { path_ok(p); impl_=std::make_unique<Impl>(p); }
FileJournal::~FileJournal()=default;
Limits FileJournal::limits() const noexcept { return impl_->limits; }
const std::vector<Entry>& FileJournal::committed() const noexcept { return impl_->entries; }
bool FileJournal::writable() const noexcept { return impl_->healthy; }
std::uint64_t FileJournal::store_id() const noexcept { return impl_->id; }
std::uint64_t FileJournal::uncommitted_bytes() const noexcept { return impl_->tail; }
bool FileJournal::append(const Entry& entry) {
    auto& s=*impl_;
    if(!s.healthy) return false;
    try {
        if(s.entries.size()>=s.limits.events+s.limits.clears) throw std::runtime_error("diagnostics journal capacity");
        Entry retained=entry; auto payload=encode(entry);
        if(payload.size()>kMaxPayload || size(s.data.fd())!=s.offset || s.offset+payload.size()+24>kMaxBytes) throw std::runtime_error("diagnostics append bounds");
        Bytes frame(kFrame.begin(),kFrame.end()); put(frame,s.entries.size()+1,8); put(frame,payload.size(),4);
        frame.insert(frame.end(),payload.begin(),payload.end()); seal(frame);
        write_all(s.data.fd(),frame); sync(s.data.fd());
        replace_commit(s.directory.fd(),commit(s.entries.size()+1,s.offset+frame.size()));
        s.offset+=frame.size(); s.entries.push_back(std::move(retained)); return true;
    } catch(...) {
        invalidate();
        try { const auto length=size(s.data.fd()); s.tail=length>s.offset?length-s.offset:0; } catch(...) { s.tail=0; }
        return false;
    }
}
void FileJournal::invalidate() noexcept {
    auto& s=*impl_; s.healthy=false;
    try {
        const auto fd=openat(s.directory.fd(),"incomplete",O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);
        if(fd<0) return; // Existing marker or failed storage; never claim repaired.
        File marker(fd); write_all(marker.fd(),Bytes{'G','A','P',1}); sync(marker.fd()); sync(s.directory.fd());
    } catch(...) { /* The health flag remains false even if the disk cannot record its own failure. */ }
}
} // namespace stratadrive::diagnostics
