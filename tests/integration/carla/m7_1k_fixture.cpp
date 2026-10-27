// Synthetic CAN/P05 fixture generator. Never a native ECU authority.
#include "steering_frame_codec.hpp"
#include "brake_frame_codec.hpp"
#include "drive_frame_codec.hpp"
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

using namespace stratadrive::can;
template <typename Frame>
void emit(const char* role, const Frame& frame, std::uint64_t time) {
    std::cout << '"' << role << "\":{\"can_id\":\"" << frame.can_id
              << "\",\"is_fd\":true,\"fd_flags\":\"0\",\"payload\":\"";
    for (unsigned i=0; i<frame.payload_length; ++i)
        std::cout << std::hex << std::setfill('0') << std::setw(2) << unsigned(frame.payload[i]);
    std::cout << std::dec << "\",\"oldest_ns\":\"" << time
              << "\",\"exclusive_expiry_ns\":\"" << time+60000000 << "\"}";
}
int main(int argc,char** argv) {
    if(argc!=8) return 2;
    try {
        const auto epoch=std::stoul(argv[1]), seq=std::stoul(argv[2]);
        const auto time=std::stoull(argv[3]);
        const double torque=std::stod(argv[4]), pressure=std::stod(argv[5]), angle=std::stod(argv[6]);
        const bool command=std::string(argv[7])=="command";
        SteeringMessage s; s.kind=SteeringFrameKind::Actual; s.epoch=epoch;s.sequence=seq;
        s.source_time_ns=time;s.causal_sequence=seq;s.local_state=ActuatorLocalState::Normal;
        s.origin=ActuatorOrigin::NormalPath;s.angle_rad=angle;
        BrakeMessage b;b.kind=BrakeFrameKind::Actual;b.epoch=epoch;b.sequence=seq;
        b.source_time_ns=time;b.causal_sequence=seq;b.local_state=ActuatorLocalState::Normal;
        b.origin=ActuatorOrigin::NormalPath;b.pressure_pa=pressure;
        DriveMessage d;d.kind=command?DriveFrameKind::Command:DriveFrameKind::Actual;
        d.epoch=epoch;d.sequence=seq;d.source_time_ns=time;d.causal_sequence=seq;
        d.local_state=ActuatorLocalState::Normal;d.origin=ActuatorOrigin::NormalPath;d.torque_nm=torque;
        SteeringTxState st{SteeringFrameKind::Actual};BrakeTxState bt{BrakeFrameKind::Actual};DriveTxState dt{d.kind};
        st.protection.counter=bt.protection.counter=dt.protection.counter=seq%256;
        auto sf=encode_steering_frame(s,st);auto bf=encode_brake_frame(b,bt);auto df=encode_drive_frame(d,dt);
        if(!sf || !bf || !df) return 3;
        std::cout << '{';emit("steering",*sf,time);std::cout << ',';emit("brake",*bf,time);
        std::cout << ',';emit("drive",*df,time);std::cout << "}\n";
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 4;}
}
