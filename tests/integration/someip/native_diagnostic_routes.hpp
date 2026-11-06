#pragma once
#include "someip/diagnostic_channel.hpp"
#include "someip/owner_message_binding.hpp"
#include "remote_diagnostics_context.hpp"
#include "producer_lifecycle.hpp"
#include "control_diagnostics.hpp"
#include "startup_diagnostics.hpp"
#include "native_diagnostics.hpp"
#include "owner_diagnostics.hpp"
#include "async_leaf_owner.hpp"
#include "async_zone_owner.hpp"
#include "latest_snapshot.hpp"
#include <filesystem>
#include <future>
#include <thread>

namespace stratadrive::someip {class Transport;}
namespace stratadrive::someip::test {
struct DiagnosticSource {unsigned producer;Ecu ecu;diagnostics::Component component;bool native;};
inline constexpr std::array<DiagnosticSource,9> diagnostic_sources{{
    {20,Ecu::Front,diagnostics::Component::Front,false},{21,Ecu::Rear,diagnostics::Component::Rear,false},
    {22,Ecu::Front,diagnostics::Component::Steering,false},{23,Ecu::Front,diagnostics::Component::Brake,false},
    {24,Ecu::Rear,diagnostics::Component::Drive,false},{30,Ecu::Front,diagnostics::Component::Front,true},
    {31,Ecu::Rear,diagnostics::Component::Rear,true},{32,Ecu::Rear,diagnostics::Component::Bms,true},
    {33,Ecu::Rear,diagnostics::Component::Power,true}}};
inline constexpr std::uint64_t diagnostic_run=8001;
inline constexpr diagnostic::Services context_services(unsigned z) {return {static_cast<std::uint16_t>(0x5e00+2*z),static_cast<std::uint16_t>(0x5e01+2*z)};}
inline constexpr std::uint64_t diagnostic_producer(unsigned slot) {return (static_cast<std::uint64_t>(slot/9)<<32)|diagnostic_sources[slot%9].producer;}
inline constexpr diagnostic::Services source_services(unsigned i) {const auto base=i<9?0x5e10:0x5e40;return {static_cast<std::uint16_t>(base+2*(i%9)),static_cast<std::uint16_t>(base+1+2*(i%9))};}
// Composition adapter for the existing native 3-ECU opt-in harness. Capture
// methods run solely on the actual ECU owner; worker owns all store/SDK IO.
class NativeDiagnosticRoutes {
public:
    static void bootstrap(const std::filesystem::path&);
    NativeDiagnosticRoutes(Ecu,const std::filesystem::path&,const std::string& tag);
    ~NativeDiagnosticRoutes();
    void configure(const std::shared_ptr<vsomeip::application>&);
    void registered();
    void start(Transport&);
    bool finish();
    void quiesce() noexcept {producing_=false;}
    bool finished() const noexcept {return finished_.load(std::memory_order_acquire);}
    bool drained() const noexcept {return finished() && passed_;}
    bool admitted(std::uint32_t epoch) const noexcept;
    void accepted_release(unsigned,std::uint32_t,std::uint64_t) noexcept;
    void central(const session::SessionCoordinator&,const central::VehicleCoordinator&,std::uint64_t);
    void zone(unsigned,const zone::AsyncZoneOwner&,bool gate,const remote::RunLeaseEvidence&,std::uint64_t);
    void leaf(unsigned,const simulation::AsyncLeafOwner&,bool gate,const remote::RunLeaseEvidence&,std::uint64_t);
private:
    struct Source {
        struct Evidence {remote::RunLeaseEvidence credit;std::uint64_t captured_ns;};
        struct Original {NativeObservation fault;unsigned monitor;std::optional<std::uint64_t> selected;};
        diagnostics::EventQueue queue;
        runtime::LatestSnapshot<Evidence> evidence;
        std::array<runtime::LatestSnapshot<Original>,2> original;
        std::array<std::optional<Original>,2> last_original;
        std::unique_ptr<diagnostics::OwnerDiagnostics> owner;
        std::unique_ptr<diagnostics::NativeDiagnostics> native;
        std::uint32_t epoch{0};std::atomic<std::uint32_t> admitted{0};
        const std::uint64_t producer;const unsigned logical;const diagnostics::Component component;bool continuity_emitted{false};
        Source(const DiagnosticSource&,std::uint64_t,bool reserve_continuity);
    };
    void bind(Source&,std::uint32_t,std::uint64_t,const remote::RunLeaseEvidence&,std::uint64_t);
    void original(Source&,unsigned,const std::optional<NativeObservation>&,std::optional<std::uint64_t>);
    void work();
    const Ecu ecu_;const std::filesystem::path folder_;const std::string tag_;
    unsigned slots_{9},generation_{1};std::uint64_t boot_ns_{0};
    std::unique_ptr<diagnostics::ProducerLifecycle> lifecycle_;
    std::array<std::unique_ptr<Source>,18> sources_;
    std::array<std::unique_ptr<diagnostic::Channel>,18> source_channels_;
    std::array<std::unique_ptr<diagnostic::Channel>,2> context_channels_;
    std::unique_ptr<diagnostics::EventQueue> startup_queue_,central_queue_;
    std::unique_ptr<diagnostics::StartupDiagnostics> startup_;
    std::unique_ptr<diagnostics::ControlDiagnostics> central_;
    bool central_restart_{false},central_continuity_{false};
    struct ReleaseAcks {std::uint32_t epoch{0};std::array<std::uint64_t,8> times{};};
    ReleaseAcks release_acks_;runtime::LatestSnapshot<ReleaseAcks> accepted_acks_;
    std::uint32_t central_epoch_{0};
    std::atomic<bool> producing_{true},finished_{true};std::thread worker_;bool passed_{false};
    std::promise<void> startup_ready_;
};
} // namespace stratadrive::someip::test
