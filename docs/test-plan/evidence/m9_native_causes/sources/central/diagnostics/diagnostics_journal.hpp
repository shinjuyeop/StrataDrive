#pragma once
#include "diagnostics.hpp"
#include <memory>
#include <string>

namespace stratadrive::diagnostics {
// Linux local filesystem only. Explicit bootstrap, one lifetime flock owner,
// append-only data plus an atomically replaced fsynced commit watermark.
// No file operation in this class is suitable for an RT runnable.
class FileJournal final : public Journal {
public:
    static void initialize(const std::string& directory,std::uint64_t store_id,Limits limits = {},std::uint32_t registry_revision=1);
    explicit FileJournal(const std::string& directory);
    ~FileJournal() override;
    FileJournal(const FileJournal&)=delete;
    FileJournal& operator=(const FileJournal&)=delete;
    Limits limits() const noexcept override;
    const std::vector<Entry>& committed() const noexcept override;
    bool writable() const noexcept override;
    bool append(const Entry&) override;
    void invalidate() noexcept override;
    std::uint64_t store_id() const noexcept;
    std::uint32_t registry_revision() const noexcept;
    std::uint64_t uncommitted_bytes() const noexcept;
private:
    struct Impl; std::unique_ptr<Impl> impl_;
};
} // namespace stratadrive::diagnostics
