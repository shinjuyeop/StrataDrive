#include "epoch_store.hpp"

#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

#include <array>
#include <algorithm>
#include <cerrno>
#include <filesystem>
#include <limits>
#include <stdexcept>
#include <system_error>
#include <utility>

namespace stratadrive::session {
namespace {
constexpr std::array<unsigned char, 8> kMagic{'S', 'D', 'E', 'P', 'O', 'C', 'H', 1};
using Record = std::array<unsigned char, 16>;
[[noreturn]] void failure(const char* operation) {
    throw std::system_error(errno, std::generic_category(), operation);
}
class File {
public:
    explicit File(int descriptor) : fd(descriptor) { if (fd < 0) failure("EpochStore open"); }
    ~File() { close(fd); }
    File(const File&) = delete;
    File& operator=(const File&) = delete;
    const int fd;
};
void regular(int fd) {
    struct stat status{};
    if (fstat(fd, &status) != 0) failure("EpochStore fstat");
    if (!S_ISREG(status.st_mode) || status.st_nlink != 1) throw std::runtime_error("EpochStore requires private regular files");
}
void sync(int fd) {
    while (fsync(fd) != 0) { if (errno != EINTR) failure("EpochStore fsync"); }
}
Record record(std::uint32_t epoch) {
    Record bytes{};
    std::copy(kMagic.begin(), kMagic.end(), bytes.begin());
    for (unsigned int index = 0; index < 4; ++index) {
        bytes[8 + index] = static_cast<unsigned char>(epoch >> (8U*index));
        bytes[12 + index] = static_cast<unsigned char>((~epoch) >> (8U*index));
    }
    return bytes;
}
std::uint32_t read_epoch(int directory) {
    File file(openat(directory, "epoch", O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK));
    regular(file.fd);
    std::array<unsigned char, 17> bytes{};
    std::size_t total = 0;
    while (total < bytes.size()) {
        const auto count = read(file.fd, bytes.data() + total, bytes.size() - total);
        if (count < 0) { if (errno == EINTR) continue; failure("EpochStore read"); }
        if (count == 0) break;
        total += static_cast<std::size_t>(count);
    }
    if (total != 16 || !std::equal(kMagic.begin(), kMagic.end(), bytes.begin())) throw std::runtime_error("EpochStore corrupt record");
    std::uint32_t epoch = 0, inverse = 0;
    for (unsigned int index = 0; index < 4; ++index) {
        epoch |= static_cast<std::uint32_t>(bytes[8 + index]) << (8U*index);
        inverse |= static_cast<std::uint32_t>(bytes[12 + index]) << (8U*index);
    }
    if (inverse != ~epoch) throw std::runtime_error("EpochStore corrupt complement");
    return epoch;
}
void persist(const File& directory, std::uint32_t epoch) {
    // Caller holds the stable lock. An uncommitted temp from a crashed issuer
    // was never returned as a grant; only the committed record is authoritative.
    if (unlinkat(directory.fd, "pending", 0) != 0 && errno != ENOENT) failure("EpochStore remove pending");
    File file(openat(directory.fd, "pending", O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600));
    const auto bytes = record(epoch);
    std::size_t total = 0;
    while (total < bytes.size()) {
        const auto count = write(file.fd, bytes.data() + total, bytes.size() - total);
        if (count < 0) { if (errno == EINTR) continue; failure("EpochStore write"); }
        if (count == 0) throw std::runtime_error("EpochStore incomplete write");
        total += static_cast<std::size_t>(count);
    }
    sync(file.fd);
    if (renameat(directory.fd, "pending", directory.fd, "epoch") != 0) failure("EpochStore rename");
    sync(directory.fd); // grant becomes visible only after file AND directory commit
}
void valid_path(const std::string& path) {
    if (path.empty() || path.find('\0') != std::string::npos || std::filesystem::path(path).filename().empty()) {
        throw std::invalid_argument("EpochStore directory path");
    }
}
}  // namespace
EpochStore::EpochStore(std::string directory) : directory_(std::move(directory)) { valid_path(directory_); }
void EpochStore::initialize(const std::string& directory) {
    valid_path(directory);
    if (mkdir(directory.c_str(), 0700) != 0) failure("EpochStore explicit bootstrap mkdir");
    File dir(open(directory.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW));
    File lock(openat(dir.fd, "lock", O_RDWR | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600));
    if (flock(lock.fd, LOCK_EX | LOCK_NB) != 0) failure("EpochStore bootstrap lock");
    sync(lock.fd);
    persist(dir, 0);
    const auto parent = std::filesystem::path(directory).parent_path();
    File parent_dir(open(parent.empty() ? "." : parent.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC));
    sync(parent_dir.fd);
}
std::uint32_t EpochStore::issue() const {
    File dir(open(directory_.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW));
    File lock(openat(dir.fd, "lock", O_RDWR | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK));
    regular(lock.fd);
    if (flock(lock.fd, LOCK_EX | LOCK_NB) != 0) failure("EpochStore busy/lock failed");
    const auto previous = read_epoch(dir.fd);
    if (previous == std::numeric_limits<std::uint32_t>::max()) throw std::overflow_error("EpochStore exhausted; wrap forbidden");
    persist(dir, previous + 1);
    return previous + 1;
}
}  // namespace stratadrive::session
