#include "steering_rtos_fixture.hpp"
#include "pilot_bridge.h"
#include "runtime_support.hpp"
#include "actuator_socketcan.hpp"
#include "steering_receiver.hpp"
#include "steering_angle_codec.hpp"
#include "steering_response.hpp"

#include <cmath>
#include <map>
#include <sys/socket.h>

namespace stratadrive::simulation {
void run_steering_rtos_plant(const SteeringRtosPlantOptions& options) {
    using namespace runtime_support;
    const auto& scenario=options.scenario; const auto& interface_name=options.interface_name;
    const auto channel=options.channel; const auto enable=options.enable; const auto& directory=options.directory;
    constexpr std::uint64_t ms=1000000;
    if(channel<0 || enable<=now_ns() || !std::filesystem::is_directory(directory) ||
        (scenario!="normal" && scenario!="command-loss" && scenario!="corrupt" && scenario!="control-stall"))
        throw std::invalid_argument("RTOS plant configuration");
    socketcan::Endpoint commands(interface_name),actuals(interface_name,can::kSteeringActualId);
    can::SteeringTxState tx{can::SteeringFrameKind::Command};
    can::SteeringReceiver receiver({can::SteeringFrameKind::Actual,-.3,.3});
    if(!receiver.start_session(2,enable)) throw std::runtime_error("RTOS Actual INIT");
    SteeringResponse plant({-.3,.3,0,1,50*ms});
    if(!plant.begin(enable)) throw std::runtime_error("RTOS plant INIT");
    struct Physical { std::uint64_t time; double angle; bool held; };
    struct Actual { std::uint64_t time,source; double angle,expected; int decision; };
    std::vector<Physical> physical; physical.reserve(1000);
    std::vector<Actual> feedback; feedback.reserve(300);
    std::map<std::uint64_t,double> acquisitions;
    std::uint64_t next_command=enable,last_command=0,hold_at=0,guard_applied=0;
    std::uint32_t sequence=0;
    unsigned expired=0,sensor_drops=0,accepted=0,source_errors=0,kernel_drops=0;
    std::size_t physical_drops=0,feedback_drops=0;
    bool held=false;
    sleep_until(enable);
    while(true) {
        std::optional<PilotOutput> latest;
        bool guard_request=false;
        for(unsigned i=0;i<8;++i) {
            PilotOutput output{}; const auto size=recv(channel,&output,sizeof(output),MSG_DONTWAIT|MSG_TRUNC);
            if(size<0 && (errno==EAGAIN || errno==EWOULDBLOCK)) break;
            if(size!=sizeof(output) || output.hold>1 || !std::isfinite(output.target_rad)) throw std::runtime_error("RTOS output packet");
            if(output.hold) { held=true; if(output.reason==1) guard_request=true; }
            latest=output;
        }
        const auto now=now_ns();
        if(!plant.advance(now)) throw std::runtime_error("RTOS physical step");
        const auto health=receiver.poll(now);
        if(health==can::SteeringReceiverHealth::Timeout || health==can::SteeringReceiverHealth::ContinuityError) held=true;
        if(held) {
            if(!plant.hold(now)) throw std::runtime_error("RTOS hold");
            if(!hold_at) hold_at=now;
            if(guard_request && !guard_applied) guard_applied=now;
        }
        else if(latest) {
            if(now>latest->deadline_ns) ++expired;
            else if(!plant.set_target(latest->target_rad,now)) throw std::runtime_error("RTOS target");
        }
        const auto sensor=plant.capture();
        if(!sensor) throw std::runtime_error("RTOS acquisition");
        const PilotSensor packet{PILOT_SENSOR_MAGIC,sensor->model_epoch,sensor->sequence,sensor->source_time_ns,sensor->angle_rad};
        if(send(channel,&packet,sizeof(packet),MSG_DONTWAIT|MSG_NOSIGNAL)!=sizeof(packet)) ++sensor_drops;
        acquisitions.emplace(sensor->source_time_ns,sensor->angle_rad);
        if(now<enable+1600*ms && now>=next_command) {
            if(scenario!="command-loss" || now<enable+600*ms) {
                can::SteeringMessage message; message.epoch=2; message.sequence=sequence++; message.source_time_ns=now;
                message.angle_rad=now<enable+200*ms ? 0:.2;
                message.local_state=can::SteeringLocalState::Normal; message.origin=can::SteeringOrigin::NormalPath;
                auto frame=can::encode_steering_frame(message,tx);
                if(!frame) throw std::runtime_error("RTOS command encode");
                if(scenario=="corrupt" && now>=enable+600*ms) frame->payload[7]^=1;
                commands.send(socketcan::to_socketcan(*frame));
                if(scenario!="corrupt" || now<enable+600*ms) last_command=now;
            }
            next_command=next_wake(enable,10*ms,now);
        }
        for(unsigned i=0;i<8;++i) {
            const auto received=actuals.receive(); if(!received) break;
            kernel_drops+=received->dropped_frames;
            const auto arrival=now_ns(); const auto frame=socketcan::to_steering(received->frame);
            const auto decoded=can::decode_steering_frame(frame);
            if(!decoded) throw std::runtime_error("RTOS Actual CRC/layout");
            const auto decision=receiver.receive(frame,arrival);
            if(decision.decision==can::SteeringReceiveDecision::Accepted) ++accepted;
            double expected=0;
            if(decoded->angle_rad) {
                const auto found=acquisitions.find(decoded->source_time_ns);
                if(found==acquisitions.end() || std::abs(found->second-*decoded->angle_rad)>can::kAngleResolutionRad/2+1e-10) ++source_errors;
                else expected=found->second;
            }
            append_bounded(feedback,Actual{arrival,decoded->source_time_ns,decoded->angle_rad.value_or(0),expected,static_cast<int>(decision.decision)},feedback_drops);
        }
        append_bounded(physical,Physical{now,sensor->angle_rad,held},physical_drops);
        if(now>=enable+1620*ms) break;
        sleep_until(next_wake(enable,2*ms,now_ns()));
    }
    auto trace=open_output(directory/"plant.csv"); trace << "time_ns,angle_rad,held\n";
    for(const auto& row:physical) trace << row.time << ',' << row.angle << ',' << row.held << '\n';
    auto actual=open_output(directory/"actual.csv"); actual << "time_ns,source_ns,angle_rad,expected_rad,decision\n";
    for(const auto& row:feedback) actual << row.time << ',' << row.source << ',' << row.angle << ',' << row.expected << ',' << row.decision << '\n';
    auto meta=open_output(directory/"plant.json");
    meta << "{\"schema\":1,\"enable_ns\":" << enable << ",\"hold_applied_ns\":" << hold_at << ",\"guard_applied_ns\":" << guard_applied
         << ",\"last_valid_command_source_ns\":" << last_command << ",\"expired_outputs\":" << expired << ",\"sensor_drops\":" << sensor_drops
         << ",\"trace_drops\":" << physical_drops+feedback_drops << ",\"actual_accepted\":" << accepted << ",\"source_errors\":" << source_errors
         << ",\"kernel_drops\":" << kernel_drops << ",\"final_angle_rad\":" << plant.actual_angle_rad()
         << ",\"receiver_health\":" << static_cast<int>(receiver.health()) << "}\n";
}
} // namespace stratadrive::simulation
