#pragma once

#include <array>
#include <cstdint>
#include <exception>
#include <functional>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>

namespace stratadrive::diagnostics {
enum class BootOperation : unsigned char { EpochInitialize=1, JournalInitialize, JournalOpen, EpochIssue };
enum class BootRole : unsigned char { Supervisor, Central, Front, Rear };

// Startup-only local incident spool. It deliberately has no application Epoch,
// DTC, Passed or Clear representation. No IO belongs in an owner runnable.
class BootstrapJournal {
public:
    static void initialize(const std::string& directory); // explicit, fresh only
    BootstrapJournal(const std::string& directory, BootRole, BootOperation);
    ~BootstrapJournal(); // an unfinished attempt stays unfinished, also on SIGKILL
    BootstrapJournal(const BootstrapJournal&)=delete;
    BootstrapJournal& operator=(const BootstrapJournal&)=delete;
    void succeeded();
    void failed(const std::string_view& reason);
private:
    void finish(unsigned char kind, const std::string_view& reason);
    int directory_{-1};
    std::array<unsigned char,320> begin_{};
    bool finished_{false};
};

template<class Function>
std::invoke_result_t<Function> record_bootstrap(const std::string& directory,
        BootRole role, BootOperation operation, Function&& work) {
    static_assert(!std::is_reference_v<std::invoke_result_t<Function>>);
    BootstrapJournal attempt(directory,role,operation);
    // Completion recording is outside this catch: an outcome commit failure is
    // an unresolved recording failure, never a second, contradictory outcome.
    if constexpr(std::is_void_v<std::invoke_result_t<Function>>) {
        try {std::invoke(std::forward<Function>(work));}
        catch(const std::exception& error) {attempt.failed(error.what());throw;}
        catch(...) {attempt.failed("non-standard exception");throw;}
        attempt.succeeded();
    } else {
        auto result=[&] {
            try {return std::invoke(std::forward<Function>(work));}
            catch(const std::exception& error) {attempt.failed(error.what());throw;}
            catch(...) {attempt.failed("non-standard exception");throw;}
        }();
        attempt.succeeded();return result;
    }
}
} // namespace stratadrive::diagnostics
