#include "epoch_store.hpp"
#include "bounded_rx_queue.hpp"
#include "steering_receiver.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"
#include "bms_receiver.hpp"

#include <gtest/gtest.h>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/wait.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <limits>
#include <system_error>
#include <vector>

namespace {
using namespace stratadrive;
class SessionTest : public ::testing::Test {
protected:
    void SetUp() override {
        std::array<char, 40> name{};
        const std::string pattern = "/tmp/stratadrive-session-XXXXXX";
        std::copy(pattern.begin(), pattern.end(), name.begin());
        const auto* created = mkdtemp(name.data());
        ASSERT_NE(created, nullptr); root = created; store = root / "store";
    }
    void TearDown() override { std::filesystem::remove_all(root); }
    void initialize() { session::EpochStore::initialize(store.string()); }
    void bytes(const std::vector<unsigned char>& data) {
        std::ofstream file(store / "epoch", std::ios::binary | std::ios::trunc);
        file.write(reinterpret_cast<const char*>(data.data()), static_cast<std::streamsize>(data.size()));
    }
    std::vector<unsigned char> record(std::uint32_t epoch) {
        std::vector<unsigned char> value{'S','D','E','P','O','C','H',1};
        for (unsigned int i = 0; i < 4; ++i) value.push_back(static_cast<unsigned char>(epoch >> (8U*i)));
        for (unsigned int i = 0; i < 4; ++i) value.push_back(static_cast<unsigned char>((~epoch) >> (8U*i)));
        return value;
    }
    std::filesystem::path root, store;
};
TEST_F(SessionTest, ExplicitBootstrapNeverOverwritesAnExistingDirectory) {
    initialize(); EXPECT_EQ(session::EpochStore(store.string()).issue(), 1U);
    EXPECT_THROW(initialize(), std::system_error);
    EXPECT_EQ(session::EpochStore(store.string()).issue(), 2U);
}
TEST_F(SessionTest, InstancesAndUnusedGrantsStillAdvanceDurableEpoch) {
    initialize(); { const session::EpochStore issuer(store.string()); EXPECT_EQ(issuer.issue(), 1U); }
    EXPECT_EQ(session::EpochStore(store.string()).issue(), 2U);
    EXPECT_EQ(session::EpochStore(store.string()).issue(), 3U);
}
TEST_F(SessionTest, MissingStoreRecordOrLockNeverReinitializes) {
    EXPECT_THROW(session::EpochStore(store.string()).issue(), std::system_error);
    initialize(); std::filesystem::remove(store / "epoch");
    EXPECT_THROW(session::EpochStore(store.string()).issue(), std::system_error);
    bytes(record(7)); std::filesystem::remove(store / "lock");
    EXPECT_THROW(session::EpochStore(store.string()).issue(), std::system_error);
}
TEST_F(SessionTest, CorruptMagicComplementLengthAndTrailingBytesFailClosed) {
    initialize();
    for (unsigned int fault = 0; fault < 4; ++fault) {
        auto data = record(7);
        if (fault == 0) data[0] ^= 1;
        else if (fault == 1) data[8] ^= 1;
        else if (fault == 2) data.resize(8);
        else data.push_back(0);
        bytes(data); EXPECT_THROW(session::EpochStore(store.string()).issue(), std::runtime_error);
    }
}
TEST_F(SessionTest, SymlinkStoreAndRecordAreRejected) {
    initialize(); const auto link = root / "link"; std::filesystem::create_directory_symlink(store, link);
    EXPECT_THROW(session::EpochStore(link.string()).issue(), std::system_error);
    std::filesystem::rename(store / "epoch", root / "record");
    std::filesystem::create_symlink(root / "record", store / "epoch");
    EXPECT_THROW(session::EpochStore(store.string()).issue(), std::system_error);
}
TEST_F(SessionTest, BusyLockReturnsAnErrorWithoutIssuing) {
    initialize(); const int fd = open((store / "lock").c_str(), O_RDWR | O_CLOEXEC);
    ASSERT_GE(fd, 0); ASSERT_EQ(flock(fd, LOCK_EX | LOCK_NB), 0);
    EXPECT_THROW(session::EpochStore(store.string()).issue(), std::system_error);
    close(fd); EXPECT_EQ(session::EpochStore(store.string()).issue(), 1U);
}
TEST_F(SessionTest, ExhaustionNeverWrapsToZeroOrOne) {
    initialize(); bytes(record(std::numeric_limits<std::uint32_t>::max()));
    EXPECT_THROW(session::EpochStore(store.string()).issue(), std::overflow_error);
    EXPECT_THROW(session::EpochStore(store.string()).issue(), std::overflow_error);
}
TEST_F(SessionTest, AbandonedPendingIsIgnoredAndWriteFailureDoesNotIssue) {
    initialize(); EXPECT_EQ(session::EpochStore(store.string()).issue(), 1U);
    { std::ofstream pending(store / "pending"); pending << "torn uncommitted data"; }
    EXPECT_EQ(session::EpochStore(store.string()).issue(), 2U);
    std::filesystem::create_directory(store / "pending");
    EXPECT_THROW(session::EpochStore(store.string()).issue(), std::system_error);
    std::filesystem::remove(store / "pending"); EXPECT_EQ(session::EpochStore(store.string()).issue(), 3U);
}
TEST_F(SessionTest, ConcurrentIndependentProcessesIssueUniqueDurableValues) {
    initialize(); std::array<int, 2> channel{}; ASSERT_EQ(pipe(channel.data()), 0);
    std::vector<pid_t> children;
    for (int index = 0; index < 8; ++index) {
        const auto child = fork(); ASSERT_GE(child, 0);
        if (child == 0) {
            close(channel[0]);
            for (int retry = 0; retry < 1000; ++retry) {
                try {
                    const auto epoch = session::EpochStore(store.string()).issue();
                    const auto count = write(channel[1], &epoch, sizeof(epoch));
                    _exit(count == sizeof(epoch) ? 0 : 3);
                } catch (const std::system_error& error) {
                    if (error.code().value() != EWOULDBLOCK) _exit(4);
                    usleep(1000);
                } catch (...) { _exit(5); }
            }
            _exit(6);
        }
        children.push_back(child);
    }
    close(channel[1]); std::array<std::uint32_t, 8> values{};
    std::size_t total = 0;
    while (total < sizeof(values)) {
        const auto count = read(channel[0], reinterpret_cast<char*>(values.data()) + total, sizeof(values) - total);
        ASSERT_GT(count, 0); total += static_cast<std::size_t>(count);
    }
    close(channel[0]);
    for (const auto child : children) { int status = 0; ASSERT_EQ(waitpid(child, &status, 0), child); EXPECT_TRUE(WIFEXITED(status)); EXPECT_EQ(WEXITSTATUS(status), 0); }
    std::sort(values.begin(), values.end());
    EXPECT_EQ(values, (std::array<std::uint32_t, 8>{1,2,3,4,5,6,7,8}));
    EXPECT_EQ(session::EpochStore(store.string()).issue(), 9U);
}
TEST(RxQueue, FifoWrapAndEmptyKeepBoundedOrder) {
    can::BoundedRxQueue<int, 3> queue; EXPECT_FALSE(queue.push(1)); ASSERT_TRUE(queue.start_session(1));
    for (int cycle = 0; cycle < 10; ++cycle) {
        ASSERT_TRUE(queue.push(cycle*2)); ASSERT_TRUE(queue.push(cycle*2+1));
        EXPECT_EQ(queue.pop(), cycle*2); EXPECT_EQ(queue.pop(), cycle*2+1); EXPECT_FALSE(queue.pop());
    }
    EXPECT_EQ(queue.size(), 0U); EXPECT_EQ(queue.fault(), can::RxQueueFault::None);
}
TEST(RxQueue, OverflowDiscardsBacklogAndRequiresNewEpoch) {
    can::BoundedRxQueue<int, 2> queue; ASSERT_TRUE(queue.start_session(7));
    ASSERT_TRUE(queue.push(1)); ASSERT_TRUE(queue.push(2)); EXPECT_FALSE(queue.push(3));
    EXPECT_EQ(queue.fault(), can::RxQueueFault::ApplicationOverflow); EXPECT_EQ(queue.size(), 0U);
    EXPECT_FALSE(queue.pop()); EXPECT_FALSE(queue.push(4)); EXPECT_FALSE(queue.start_session(7)); EXPECT_FALSE(queue.start_session(6));
    ASSERT_TRUE(queue.start_session(8)); EXPECT_TRUE(queue.push(5)); EXPECT_EQ(queue.pop(), 5);
}
TEST(RxQueue, KernelCounterChangeDiscardsBacklogAndDirtyEndpointCannotRecover) {
    can::BoundedRxQueue<int, 2> queue; ASSERT_TRUE(queue.start_session(1)); ASSERT_TRUE(queue.push(1));
    EXPECT_FALSE(queue.push(2, 4)); EXPECT_EQ(queue.fault(), can::RxQueueFault::KernelDrop); EXPECT_FALSE(queue.pop());
    ASSERT_TRUE(queue.start_session(2)); EXPECT_FALSE(queue.push(3, 4)); // new Epoch alone does not clean a socket
    ASSERT_TRUE(queue.start_session(3)); EXPECT_TRUE(queue.push(4, 0)); EXPECT_EQ(queue.pop(), 4);
}
TEST(SessionReceiver, ContinuityFaultIsLatchedAndPreservesExistingClockAndTimeoutFaults) {
    can::ActuatorReceiverState state({30000000, 80000000});
    state.mark_continuity_lost(0); EXPECT_EQ(state.health(), can::ActuatorReceiverHealth::NotInitialized);
    ASSERT_TRUE(state.start_session(1, 1000000000)); state.mark_continuity_lost(1001000000);
    EXPECT_EQ(state.begin_receive(1002000000), can::ActuatorReceiveDecision::ContinuityLost);
    EXPECT_EQ(state.poll(1100000000), can::ActuatorReceiverHealth::ContinuityError);
    ASSERT_TRUE(state.start_session(2, 1100000000)); state.mark_continuity_lost(1099999999);
    EXPECT_EQ(state.health(), can::ActuatorReceiverHealth::ClockError);
    ASSERT_TRUE(state.start_session(3, 1100000000)); state.mark_continuity_lost(1180000000);
    EXPECT_EQ(state.health(), can::ActuatorReceiverHealth::Timeout);
}
template <typename Message> void refresh(Message&) {}
void refresh(can::BmsMessage& message) {
    if (auto* v = std::get_if<can::BmsPowerRequest>(&message.content)) v->expires_at_ns = message.source_time_ns + 60000000;
    else if (auto* v = std::get_if<can::BmsPowerLimits>(&message.content)) v->input_time_ns = message.source_time_ns;
    else if (auto* v = std::get_if<can::BmsPowerStatus>(&message.content)) v->input_time_ns = message.source_time_ns;
    else if (auto* v = std::get_if<can::BmsDriveGrant>(&message.content)) {
        v->input_time_ns = v->power_status_source_time_ns = message.source_time_ns; v->expires_at_ns = message.source_time_ns + 60000000;
    } else {
        auto& battery = std::get<can::BmsBatteryState>(message.content);
        battery.soc->source_time_ns = battery.electrical->source_time_ns = battery.temperature->source_time_ns = message.source_time_ns;
    }
}
TEST_F(SessionTest, AllTwelveStreamsCloseOnContinuityLossAndRejectOldEpochAfterRestart) {
    initialize(); constexpr std::uint64_t start = 1000000000;
    const auto check = [&](auto& receiver, auto message, auto tx, auto encode) {
        const auto epoch = session::EpochStore(store.string()).issue();
        ASSERT_TRUE(receiver.start_session(epoch, start));
        message.epoch = epoch; message.source_time_ns = start; refresh(message);
        const auto first = encode(message, tx); ASSERT_TRUE(first);
        ASSERT_EQ(receiver.receive(*first, start).decision, can::ActuatorReceiveDecision::Accepted);
        ASSERT_TRUE(receiver.current_sample(start));
        receiver.mark_continuity_lost(start+1000000); EXPECT_FALSE(receiver.current_sample(start+1000000));
        message.sequence = 1; message.source_time_ns += 2000000; refresh(message);
        EXPECT_EQ(receiver.receive(*encode(message, tx), message.source_time_ns).decision, can::ActuatorReceiveDecision::ContinuityLost);
        EXPECT_EQ(receiver.last_accepted()->received_time_ns, start);
        EXPECT_FALSE(receiver.start_session(epoch, start+3000000));
        const auto next = session::EpochStore(store.string()).issue(); ASSERT_TRUE(receiver.start_session(next, start+3000000));
        message.sequence = 0; message.source_time_ns = start+4000000; refresh(message);
        tx.protection.counter = 200; // old transport sequence must not poison new-session P05 state
        EXPECT_EQ(receiver.receive(*encode(message, tx), message.source_time_ns).decision, can::ActuatorReceiveDecision::EpochMismatch);
        message.epoch = next; e2e::p05_protect_init(tx.protection);
        EXPECT_EQ(receiver.receive(*encode(message, tx), message.source_time_ns).decision, can::ActuatorReceiveDecision::Accepted);
        EXPECT_TRUE(receiver.current_sample(message.source_time_ns));
    };
    for (bool actual : {false,true}) {
        can::SteeringMessage s; s.kind = actual ? can::SteeringFrameKind::Actual : can::SteeringFrameKind::Command;
        s.angle_rad = 0.1; s.origin = can::ActuatorOrigin::NormalPath; s.local_state = can::ActuatorLocalState::Normal;
        can::SteeringReceiver sr({s.kind,-0.5,0.5}); check(sr,s,can::SteeringTxState{s.kind},can::encode_steering_frame);
        can::BrakeMessage b; b.kind = actual ? can::BrakeFrameKind::Actual : can::BrakeFrameKind::Command;
        b.pressure_pa = 1000; b.origin = s.origin; b.local_state = s.local_state;
        can::BrakeReceiver br({b.kind,0,2000000}); check(br,b,can::BrakeTxState{b.kind},can::encode_brake_frame);
        can::DriveMessage d; d.kind = actual ? can::DriveFrameKind::Actual : can::DriveFrameKind::Command;
        d.torque_nm = 10; d.origin = s.origin; d.local_state = s.local_state;
        can::DriveReceiver dr({d.kind,{-300,500},100,300}); check(dr,d,can::DriveTxState{d.kind},can::encode_drive_frame);
    }
    using can::BmsFrameKind;
    for (const auto kind : {BmsFrameKind::PowerRequest,BmsFrameKind::PowerStatus,BmsFrameKind::PowerLimits,
                           BmsFrameKind::BatteryState,BmsFrameKind::DriveBatteryLimits,BmsFrameKind::DrivePermission}) {
        can::BmsMessage m; m.kind = kind; m.local_state = can::ActuatorLocalState::Init; m.origin = can::ActuatorOrigin::NoAcceptedInput;
        if (kind == BmsFrameKind::PowerRequest) m.content = can::BmsPowerRequest{can::BmsPowerAction::KeepOff,0,0};
        else if (kind == BmsFrameKind::PowerStatus) m.content = can::BmsPowerStatus{can::BmsPowerState::Off,false,false,false,7,31,0,0,0,0};
        else if (kind == BmsFrameKind::PowerLimits || kind == BmsFrameKind::DriveBatteryLimits)
            m.content = can::BmsPowerLimits{1000,1000,can::BmsLimitReason::Nominal,can::BmsLimitReason::Nominal,0};
        else if (kind == BmsFrameKind::DrivePermission) m.content = can::BmsDriveGrant{can::BmsDrivePermission::Inhibit,0,0,0,0};
        else m.content = can::BmsBatteryState{can::BmsSocSample{0.5,0},can::BmsElectricalSample{400,10,0},can::BmsTemperatureSample{25,0}};
        can::BmsReceiver receiver({kind,{{0,1000},{-500,500},{-60,200},200000}});
        check(receiver,m,can::BmsTxState{kind},can::encode_bms_frame);
    }
}
}  // namespace
