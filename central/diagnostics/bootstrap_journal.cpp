#include "bootstrap_journal.hpp"

#include <fcntl.h>
#include <sys/random.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <algorithm>
#include <cerrno>
#include <filesystem>
#include <stdexcept>
#include <system_error>

namespace stratadrive::diagnostics {
namespace {
constexpr std::array<unsigned char,8> magic{'S','D','B','O','O','T',0,1};
[[noreturn]] void error(const char* operation) {throw std::system_error(errno,std::generic_category(),operation);}
class File {
public:
    explicit File(int value):fd(value) {if(fd<0)error("BootstrapJournal open");}
    ~File(){close(fd);}
    File(const File&)=delete;File& operator=(const File&)=delete;
    const int fd;
};
void sync(int fd) {while(fsync(fd)!=0)if(errno!=EINTR)error("BootstrapJournal fsync");}
void private_file(int fd) {
    struct stat s{};if(fstat(fd,&s)!=0)error("BootstrapJournal fstat");
    if(!S_ISREG(s.st_mode) || s.st_nlink!=1 || s.st_uid!=geteuid() || (s.st_mode&0077))
        throw std::runtime_error("BootstrapJournal requires owned private regular files");
}
void private_directory(int fd) {
    struct stat s{};if(fstat(fd,&s)!=0)error("BootstrapJournal directory fstat");
    if(!S_ISDIR(s.st_mode) || s.st_uid!=geteuid() || (s.st_mode&0077))
        throw std::runtime_error("BootstrapJournal requires owned private directory");
}
void put(std::array<unsigned char,320>& bytes,unsigned at,std::uint64_t value,unsigned size) {
    for(unsigned i=0;i<size;++i)bytes[at+i]=static_cast<unsigned char>(value>>(8U*i));
}
std::uint64_t monotonic() {
    timespec time{};if(clock_gettime(CLOCK_MONOTONIC,&time)!=0)error("BootstrapJournal clock");
    return static_cast<std::uint64_t>(time.tv_sec)*1000000000ULL+static_cast<std::uint64_t>(time.tv_nsec);
}
std::uint32_t crc(const std::array<unsigned char,320>& bytes) {
    std::uint32_t value=0xffffffffU;
    for(unsigned i=0;i<316;++i) {value^=bytes[i];for(unsigned bit=0;bit<8;++bit)value=(value>>1U)^((value&1U)?0xedb88320U:0U);}
    return ~value;
}
void commit(int directory,const char* name,const unsigned char* bytes,std::size_t size) {
    const std::string pending=std::string(name)+".pending";
    File out(openat(directory,pending.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600));
    std::size_t total=0;
    while(total<size) {const auto n=write(out.fd,bytes+total,size-total);if(n<0){if(errno==EINTR)continue;error("BootstrapJournal write");}if(n==0)throw std::runtime_error("BootstrapJournal short write");total+=static_cast<std::size_t>(n);}
    sync(out.fd);
    // linkat never overwrites a previous outcome. A crash can leave .pending;
    // readers retain it as incomplete evidence, never infer success from it.
    if(linkat(directory,pending.c_str(),directory,name,0)!=0)error("BootstrapJournal commit");
    if(unlinkat(directory,pending.c_str(),0)!=0)error("BootstrapJournal pending unlink");
    sync(directory);
}
void valid_path(const std::string& path) {
    if(path.empty() || path.find('\0')!=std::string::npos || std::filesystem::path(path).filename().empty())
        throw std::invalid_argument("BootstrapJournal directory path");
}
unsigned hex(char ch) {
    if(ch>='0' && ch<='9')return static_cast<unsigned>(ch-'0');
    if(ch>='a' && ch<='f')return static_cast<unsigned>(ch-'a'+10);
    throw std::runtime_error("BootstrapJournal kernel boot identity");
}
void identity(std::array<unsigned char,320>& bytes) {
    std::size_t total=0;
    while(total<16) {const auto n=getrandom(bytes.data()+32+total,16-total,0);if(n<0){if(errno==EINTR)continue;error("BootstrapJournal getrandom");}if(n==0)throw std::runtime_error("BootstrapJournal missing entropy");total+=static_cast<std::size_t>(n);}
    File boot(open("/proc/sys/kernel/random/boot_id",O_RDONLY|O_CLOEXEC|O_NOFOLLOW));
    std::array<char,37> text{};total=0;
    while(total<text.size()) {const auto n=read(boot.fd,text.data()+total,text.size()-total);if(n<0){if(errno==EINTR)continue;error("BootstrapJournal boot_id read");}if(n==0)break;total+=static_cast<std::size_t>(n);}
    if(total!=37 || text[36]!='\n')throw std::runtime_error("BootstrapJournal boot_id length");
    unsigned target=48;
    for(unsigned i=0;i<36;) {
        if(i==8 || i==13 || i==18 || i==23){if(text[i++]!='-')throw std::runtime_error("BootstrapJournal boot_id separator");continue;}
        bytes[target++]=static_cast<unsigned char>(hex(text[i])*16U+hex(text[i+1]));i+=2;
    }
}
} // namespace
void BootstrapJournal::initialize(const std::string& directory) {
    valid_path(directory);
    if(mkdir(directory.c_str(),0700)!=0)error("BootstrapJournal explicit mkdir");
    File root(open(directory.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW));
    commit(root.fd,"format",magic.data(),magic.size());
    const auto parent=std::filesystem::path(directory).parent_path();
    File parent_dir(open(parent.empty()?".":parent.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC));sync(parent_dir.fd);
}
BootstrapJournal::BootstrapJournal(const std::string& directory,BootRole role,BootOperation operation) {
    valid_path(directory);
    if(static_cast<unsigned>(role)>3 || static_cast<unsigned>(operation)<1 || static_cast<unsigned>(operation)>4)
        throw std::invalid_argument("BootstrapJournal role/operation");
    File root(open(directory.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW));private_directory(root.fd);
    File format(openat(root.fd,"format",O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK));private_file(format.fd);
    std::array<unsigned char,9> format_bytes{};
    const auto count=read(format.fd,format_bytes.data(),format_bytes.size());
    if(count!=8 || !std::equal(magic.begin(),magic.end(),format_bytes.begin()))throw std::runtime_error("BootstrapJournal corrupt format");
    std::copy(magic.begin(),magic.end(),begin_.begin());begin_[8]=1;begin_[9]=static_cast<unsigned char>(operation);begin_[10]=static_cast<unsigned char>(role);
    put(begin_,12,static_cast<std::uint64_t>(getpid()),4);const auto time=monotonic();put(begin_,16,time,8);put(begin_,24,time,8);identity(begin_);
    std::string id;constexpr char digits[]="0123456789abcdef";
    for(unsigned i=32;i<48;++i){id+=digits[begin_[i]>>4U];id+=digits[begin_[i]&15U];}
    if(mkdirat(root.fd,id.c_str(),0700)!=0)error("BootstrapJournal unique attempt mkdir");
    File attempt(openat(root.fd,id.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW));
    put(begin_,316,crc(begin_),4);commit(attempt.fd,"begin",begin_.data(),begin_.size());sync(root.fd);
    directory_=fcntl(attempt.fd,F_DUPFD_CLOEXEC,0);if(directory_<0)error("BootstrapJournal duplicate directory");
}
BootstrapJournal::~BootstrapJournal(){if(directory_>=0)close(directory_);}
void BootstrapJournal::finish(unsigned char kind,const std::string_view& reason) {
    if(finished_)throw std::logic_error("BootstrapJournal outcome already committed");
    auto bytes=begin_;bytes[8]=kind;put(bytes,24,monotonic(),8);
    const auto length=std::min<std::size_t>(reason.size(),240);put(bytes,64,length,2);bytes[66]=reason.size()>length?1:0;
    std::copy_n(reason.begin(),length,bytes.begin()+68);put(bytes,316,crc(bytes),4);
    commit(directory_,"outcome",bytes.data(),bytes.size());finished_=true;
}
void BootstrapJournal::succeeded(){finish(2,{});}
void BootstrapJournal::failed(const std::string_view& reason){finish(3,reason);}
} // namespace stratadrive::diagnostics
