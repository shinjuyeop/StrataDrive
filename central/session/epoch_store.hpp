#pragma once

#include <cstdint>
#include <string>

namespace stratadrive::session {
// Linux local-filesystem issuer, owned by the Central trusted session coordinator.
// Startup only: file locking/fsync must not run in a control/monitor cycle.
class EpochStore {
public:
    // Explicit bootstrap: directory must not exist. Existing/missing/corrupt
    // stores are never silently initialized or reset by issue().
    static void initialize(const std::string& directory);
    explicit EpochStore(std::string directory);
    std::uint32_t issue() const;
private:
    const std::string directory_;
};
}  // namespace stratadrive::session
