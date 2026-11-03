#pragma once
#include "continuity_review_fixture.hpp"
#include "continuity_service.hpp"
#include "service_evidence.hpp"
#include "drive_receiver.hpp"
#include "brake_receiver.hpp"
#include <sys/socket.h>
#include <unistd.h>

namespace continuity_fixture {
class ContinuityServiceTest:public ContinuityReviewTest {
protected:
    struct Capture:ContinuityCapture {
        ContinuityServiceTest& test;bool available{true},held{false};unsigned acquires{0},samples{0},fail_sample{0};
        double speed{0},torque{0},pressure{100000};std::uint64_t age{0};bool inhibited{true};
        std::optional<std::vector<StreamState>> frozen_states;
        std::optional<std::filesystem::path> export_samples;bool throw_sample{false};
        explicit Capture(ContinuityServiceTest& t):test(t){}
        struct Cut:FrozenContinuity {
            Capture& owner;Event original;std::vector<StreamState> states;
            explicit Cut(Capture& c):owner(c),original(c.test.global),states(c.frozen_states?*c.frozen_states:c.test.streams()){c.held=true;}
            ~Cut() override{owner.held=false;}
            const Event& global() const noexcept override{return original;}
            const std::vector<StreamState>& streams() const noexcept override{return states;}
            ServiceEvidence sample() override{return owner.sample();}
        };
        std::unique_ptr<FrozenContinuity> acquire() override {++acquires;if(!available || held)return {};return std::make_unique<Cut>(*this);}
        ServiceEvidence sample(){
            EXPECT_TRUE(held);if(throw_sample)throw std::runtime_error("Actual capture unavailable");
            ++samples;const auto now=stamp(test.central.now+=1000000);
            central::NormalDriveReadinessInputs input;input.epoch=test.global.session.epoch;input.session_enable_ns=test.global.session_enable.ns;
            can::DriveMessage drive;drive.kind=can::DriveFrameKind::Actual;drive.epoch=input.epoch;drive.sequence=samples;
            drive.source_time_ns=now.ns-2000-age;drive.local_state=can::ActuatorLocalState::FailSafe;drive.origin=can::ActuatorOrigin::LocalProtection;
            drive.torque_nm=torque;drive.wheel_speed=can::DriveWheelSpeed{speed,now.ns-1000-age};
            can::BrakeMessage brake;brake.kind=can::BrakeFrameKind::Actual;brake.epoch=input.epoch;brake.sequence=samples;
            brake.source_time_ns=now.ns-3000-age;brake.local_state=drive.local_state;brake.origin=drive.origin;brake.pressure_pa=pressure;
            can::DriveTxState dt{can::DriveFrameKind::Actual,{}};can::BrakeTxState bt{can::BrakeFrameKind::Actual,{}};
            can::DriveReceiver dr({can::DriveFrameKind::Actual,{-500,500},100,500,30000000,80000000,30000000,{}});
            can::BrakeReceiver br({can::BrakeFrameKind::Actual,0,2000000});
            EXPECT_TRUE(dr.start_session(input.epoch,input.session_enable_ns));EXPECT_TRUE(br.start_session(input.epoch,input.session_enable_ns));
            const auto df=can::encode_drive_frame(drive,dt);const auto bf=can::encode_brake_frame(brake,bt);EXPECT_TRUE(df);EXPECT_TRUE(bf);
            if(export_samples && df && bf){
                const auto prefix=*export_samples/("sample-"+std::to_string(samples));
                std::ofstream a(prefix.string()+".drive",std::ios::binary);a.write(reinterpret_cast<const char*>(df->payload.data()),df->payload_length);
                std::ofstream b(prefix.string()+".brake",std::ios::binary);b.write(reinterpret_cast<const char*>(bf->payload.data()),bf->payload_length);
            }
            if(df){(void)dr.receive(*df,now.ns);input.rear.drive_actual=dr.current_sample(now.ns);}if(bf){(void)br.receive(*bf,now.ns);input.front.brake_actual=br.current_sample(now.ns);}
            auto evidence=capture_service_evidence(context(99),test.global.session,test.global.session_enable,input,now,inhibited);
            if(samples==fail_sample)evidence.normal_dispatch_inhibited=false;
            return evidence;
        }
    } capture{*this};
    ServicePermit permit(){ServicePermit p;p.uid=getuid();p.pid=getpid();p.capability.fill(0x42);p.actor=context(99);p.session=global.session;p.incident=incident.id;return p;}
    ServiceRequest request(std::uint64_t number=1,ServiceOperation op=ServiceOperation::Review){ServiceRequest r;r.capability=permit().capability;r.number=number;r.session=global.session;r.incident=incident.id;
        r.revision=writer->ledger().find(incident.key)->revision;r.operation=op;r.disposition=op==ServiceOperation::Review?ContinuityDisposition::AcceptUnknownHistory:ContinuityDisposition::None;return r;}
    ServiceReply packet(ContinuityService& service,const std::vector<std::uint8_t>& bytes){int fd[2]{};EXPECT_EQ(socketpair(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0,fd),0);
        EXPECT_EQ(send(fd[0],bytes.data(),bytes.size(),MSG_NOSIGNAL),static_cast<ssize_t>(bytes.size()));const auto reply=service.serve(fd[1]);
        std::vector<std::uint8_t> response(256);const auto n=recv(fd[0],response.data(),response.size(),MSG_DONTWAIT);EXPECT_GT(n,0);response.resize(n>0?static_cast<std::size_t>(n):0);
        close(fd[0]);close(fd[1]);EXPECT_EQ(encode_service_reply(reply),response);return reply;}
    ServiceReply call(ContinuityService& service,const ServiceRequest& r){return packet(service,encode_service_request(r));}
};
} // namespace continuity_fixture
